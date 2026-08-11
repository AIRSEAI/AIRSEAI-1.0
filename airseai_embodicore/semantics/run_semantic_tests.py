import csv
import json
import platform
from pathlib import Path

import torch
import torch.nn.functional as F

from mamba_v1_ref import selective_scan_ref, make_cpu_scan_inputs, to_device

OUT = Path("part1_semantics")
OUT.mkdir(parents=True, exist_ok=True)

def max_abs(a, b):
    return float((a.detach().cpu() - b.detach().cpu()).abs().max())

def mean_abs(a, b):
    return float((a.detach().cpu() - b.detach().cpu()).abs().mean())

def scan_run(cpu_inputs, device, initial_state=None):
    args = to_device(cpu_inputs, device)
    init = None if initial_state is None else initial_state.to(device)
    y, s = selective_scan_ref(*args, initial_state=init)
    return y.detach().cpu(), s.detach().cpu()

def legal_condition_reuse(device="cpu"):
    g = torch.Generator(device="cpu")
    g.manual_seed(23)

    batch, tdim, gdim, odim, steps = 4, 32, 48, 64, 10
    global_cond_cpu = torch.randn(batch, gdim, generator=g)
    W_cpu = 0.05 * torch.randn(odim, tdim + gdim, generator=g)
    bias_cpu = 0.05 * torch.randn(odim, generator=g)
    timestep_cpus = [torch.randn(batch, tdim, generator=g) for _ in range(steps)]

    global_cond = global_cond_cpu.to(device)
    W = W_cpu.to(device)
    bias = bias_cpu.to(device)
    W_t, W_g = W[:, :tdim], W[:, tdim:]
    cached_g = F.linear(F.mish(global_cond), W_g, bias=None)

    errs = []
    for t_cpu in timestep_cpus:
        t = t_cpu.to(device)
        full = F.linear(F.mish(torch.cat([t, global_cond], dim=-1)), W, bias=bias)
        cached = F.linear(F.mish(t), W_t, bias=bias) + cached_g
        errs.append((full - cached).abs().detach().cpu())

    e = torch.cat([x.flatten() for x in errs])
    return float(e.max()), float(e.mean())

def stale_condition_negative_control(device="cpu"):
    g = torch.Generator(device="cpu")
    g.manual_seed(41)

    batch, tdim, gdim, odim = 4, 32, 48, 64
    t_cpu = torch.randn(batch, tdim, generator=g)
    cond_a_cpu = torch.randn(batch, gdim, generator=g)
    cond_b_cpu = torch.randn(batch, gdim, generator=g)
    W_cpu = 0.05 * torch.randn(odim, tdim + gdim, generator=g)
    bias_cpu = 0.05 * torch.randn(odim, generator=g)

    t = t_cpu.to(device)
    cond_a = cond_a_cpu.to(device)
    cond_b = cond_b_cpu.to(device)
    W = W_cpu.to(device)
    bias = bias_cpu.to(device)
    W_t, W_g = W[:, :tdim], W[:, tdim:]

    correct_b = F.linear(F.mish(torch.cat([t, cond_b], dim=-1)), W, bias=bias)
    stale_a = (
        F.linear(F.mish(t), W_t, bias=bias)
        + F.linear(F.mish(cond_a), W_g, bias=None)
    )
    err = (correct_b - stale_a).abs().detach().cpu()
    return float(err.max()), float(err.mean())

def main():
    mps_built = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_built())
    mps_available = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())

    scan1 = make_cpu_scan_inputs(seed=7)
    scan2 = make_cpu_scan_inputs(seed=11)

    y1_cpu, s1_cpu = scan_run(scan1, "cpu")
    y2_reset_cpu, s2_reset_cpu = scan_run(scan2, "cpu")
    y2_carry_cpu, s2_carry_cpu = scan_run(scan2, "cpu", initial_state=s1_cpu)

    illegal_output_max = max_abs(y2_reset_cpu, y2_carry_cpu)
    illegal_output_mean = mean_abs(y2_reset_cpu, y2_carry_cpu)
    illegal_state_max = max_abs(s2_reset_cpu, s2_carry_cpu)
    illegal_state_mean = mean_abs(s2_reset_cpu, s2_carry_cpu)

    legal_cpu_max, legal_cpu_mean = legal_condition_reuse("cpu")
    stale_cpu_max, stale_cpu_mean = stale_condition_negative_control("cpu")

    cpu_mps_max = cpu_mps_mean = None
    legal_mps_max = legal_mps_mean = None
    stale_mps_max = stale_mps_mean = None

    if mps_available:
        y1_mps, _ = scan_run(scan1, "mps")
        cpu_mps_max = max_abs(y1_cpu, y1_mps)
        cpu_mps_mean = mean_abs(y1_cpu, y1_mps)
        legal_mps_max, legal_mps_mean = legal_condition_reuse("mps")
        stale_mps_max, stale_mps_mean = stale_condition_negative_control("mps")

    mps_consistency_pass = (
        mps_available
        and cpu_mps_max is not None
        and cpu_mps_max < 5e-4
        and cpu_mps_mean < 5e-5
    )
    legal_reuse_pass = legal_cpu_max < 1e-5
    illegal_scan_pass = illegal_output_max > 1e-4 and illegal_state_max > 1e-4
    stale_condition_pass = stale_cpu_max > 1e-4

    metrics = {
        "machine": platform.machine(),
        "torch_version": torch.__version__,
        "mps_built": mps_built,
        "mps_available": mps_available,
        "cpu_mps_reference_max_abs_error": cpu_mps_max,
        "cpu_mps_reference_mean_abs_error": cpu_mps_mean,
        "legal_policy_local_reuse_cpu_max_abs_error": legal_cpu_max,
        "legal_policy_local_reuse_cpu_mean_abs_error": legal_cpu_mean,
        "legal_policy_local_reuse_mps_max_abs_error": legal_mps_max,
        "legal_policy_local_reuse_mps_mean_abs_error": legal_mps_mean,
        "illegal_scan_state_carry_output_max_abs_error": illegal_output_max,
        "illegal_scan_state_carry_output_mean_abs_error": illegal_output_mean,
        "illegal_scan_state_carry_state_max_abs_error": illegal_state_max,
        "illegal_scan_state_carry_state_mean_abs_error": illegal_state_mean,
        "stale_condition_after_new_observation_cpu_max_abs_error": stale_cpu_max,
        "stale_condition_after_new_observation_cpu_mean_abs_error": stale_cpu_mean,
        "stale_condition_after_new_observation_mps_max_abs_error": stale_mps_max,
        "stale_condition_after_new_observation_mps_mean_abs_error": stale_mps_mean,
        "mps_consistency_pass": mps_consistency_pass,
        "legal_reuse_pass": legal_reuse_pass,
        "illegal_scan_state_carry_pass": illegal_scan_pass,
        "stale_condition_reset_pass": stale_condition_pass,
        "semantic_tests_pass": legal_reuse_pass and illegal_scan_pass and stale_condition_pass
    }

    (OUT / "semantic_test_metrics.json").write_text(json.dumps(metrics, indent=2))

    with (OUT / "legal_reuse.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test", "device", "max_abs_error", "mean_abs_error"])
        w.writerow(["policy_local_condition_contribution_reuse", "cpu", legal_cpu_max, legal_cpu_mean])
        if mps_available:
            w.writerow(["policy_local_condition_contribution_reuse", "mps", legal_mps_max, legal_mps_mean])

    with (OUT / "illegal_reuse.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test", "device", "max_abs_error", "mean_abs_error"])
        w.writerow(["carry_scan_state_across_independent_call_output", "cpu", illegal_output_max, illegal_output_mean])
        w.writerow(["carry_scan_state_across_independent_call_state", "cpu", illegal_state_max, illegal_state_mean])
        w.writerow(["reuse_stale_condition_after_new_observation", "cpu", stale_cpu_max, stale_cpu_mean])
        if mps_available:
            w.writerow(["reuse_stale_condition_after_new_observation", "mps", stale_mps_max, stale_mps_mean])

    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
