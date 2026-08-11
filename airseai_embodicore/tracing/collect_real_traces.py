#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tensor_np(x):
    return x.detach().float().cpu().numpy()


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def dict_to_device(obs, device):
    out = {}
    for k, v in obs.items():
        if not torch.is_tensor(v):
            v = torch.as_tensor(v)
        out[k] = v.unsqueeze(0).to(device)
    return out


def extract_feature(policy, obs_dict):
    from diffusion_policy_3d.common.pytorch_util import dict_apply

    nobs = policy.normalizer.normalize(obs_dict)
    if not policy.use_pc_color:
        nobs["point_cloud"] = nobs["point_cloud"][..., :3]

    value = next(iter(nobs.values()))
    B = value.shape[0]
    To = policy.n_obs_steps
    T = policy.horizon
    Da = policy.action_dim
    Do = policy.obs_feature_dim
    device = policy.device
    dtype = policy.dtype

    local_cond = None
    global_cond = None
    if not policy.obs_as_global_cond:
        raise RuntimeError("Part II expects obs_as_global_cond=True.")

    this_nobs = dict_apply(
        nobs, lambda x: x[:, :To, ...].reshape(-1, *x.shape[2:])
    )
    enc = policy.obs_encoder(this_nobs)
    if isinstance(enc, tuple):
        nobs_features = enc[0]
    else:
        nobs_features = enc

    if "cross_attention" in policy.condition_type:
        global_cond = nobs_features.reshape(B, policy.n_obs_steps, -1)
    else:
        global_cond = nobs_features.reshape(B, -1)

    cond_data = torch.zeros((B, T, Da), device=device, dtype=dtype)
    cond_mask = torch.zeros_like(cond_data, dtype=torch.bool)

    return {
        "nobs": nobs,
        "global_cond": global_cond,
        "cond_data": cond_data,
        "cond_mask": cond_mask,
        "local_cond": local_cond,
        "Da": Da,
        "To": To,
    }


class MixerRecorder:
    def __init__(self, model, enable=True):
        self.enable = enable
        self.records = defaultdict(list)
        self.handles = []
        self.step = -1

        candidates = []
        for name, module in model.named_modules():
            cname = module.__class__.__name__
            if cname in {"Mamba", "Mamba2", "Hydra"}:
                candidates.append((name, module))

        if not candidates:
            raise RuntimeError("No Mamba/Mamba2/Hydra mixer modules found.")

        idxs = sorted(set([0, len(candidates) // 2, len(candidates) - 1]))
        self.selected = [(i, candidates[i][0], candidates[i][1]) for i in idxs]

        if enable:
            for slot, name, module in self.selected:
                def pre_hook(mod, inp, slot=slot, name=name):
                    self.records[f"mixer{slot}__step"].append(self.step)
                    self.records[f"mixer{slot}__input"].append(tensor_np(inp[0]))
                def post_hook(mod, inp, output, slot=slot, name=name):
                    out = output[0] if isinstance(output, tuple) else output
                    self.records[f"mixer{slot}__output"].append(tensor_np(out))
                self.handles.append(module.register_forward_pre_hook(pre_hook))
                self.handles.append(module.register_forward_hook(post_hook))

    def close(self):
        for h in self.handles:
            h.remove()

    def manifest(self):
        return [
            {"slot": slot, "module_name": name, "class": module.__class__.__name__}
            for slot, name, module in self.selected
        ]


@torch.no_grad()
def traced_predict(policy, obs_dict, seed, mixer_recorder=None):
    ctx = extract_feature(policy, obs_dict)
    global_cond = ctx["global_cond"]
    cond_data = ctx["cond_data"]
    cond_mask = ctx["cond_mask"]
    local_cond = ctx["local_cond"]
    Da = ctx["Da"]
    To = ctx["To"]

    seed_all(seed)
    scheduler = policy.noise_scheduler
    model = policy.model

    trajectory = torch.randn(
        size=cond_data.shape,
        dtype=cond_data.dtype,
        device=cond_data.device,
    )
    scheduler.set_timesteps(policy.num_inference_steps)

    timesteps = []
    traj_in = []
    model_out = []
    traj_out = []

    for step_idx, t in enumerate(scheduler.timesteps):
        trajectory[cond_mask] = cond_data[cond_mask]
        if mixer_recorder is not None:
            mixer_recorder.step = step_idx

        tin = trajectory.clone()
        mout = model(
            sample=trajectory,
            timestep=t,
            local_cond=local_cond,
            global_cond=global_cond,
        )
        trajectory = scheduler.step(mout, t, trajectory).prev_sample

        timesteps.append(int(t.detach().cpu().item()) if torch.is_tensor(t) else int(t))
        traj_in.append(tensor_np(tin))
        model_out.append(tensor_np(mout))
        traj_out.append(tensor_np(trajectory))

    trajectory[cond_mask] = cond_data[cond_mask]
    naction_pred = trajectory[..., :Da]
    action_pred = policy.normalizer["action"].unnormalize(naction_pred)
    start = To - 1
    end = start + policy.n_action_steps
    action = action_pred[:, start:end]

    return {
        "global_cond": tensor_np(global_cond),
        "ddim_timestep": np.asarray(timesteps, dtype=np.int64),
        "trajectory_in": np.stack(traj_in, axis=1),
        "model_output": np.stack(model_out, axis=1),
        "trajectory_out": np.stack(traj_out, axis=1),
        "action_pred": tensor_np(action_pred),
        "action": tensor_np(action),
    }


@torch.no_grad()
def action_from_context(policy, ctx, global_cond, seed):
    seed_all(seed)
    nsample = policy.conditional_sample(
        ctx["cond_data"],
        ctx["cond_mask"],
        local_cond=ctx["local_cond"],
        global_cond=global_cond,
    )
    naction_pred = nsample[..., :ctx["Da"]]
    action_pred = policy.normalizer["action"].unnormalize(naction_pred)
    start = ctx["To"] - 1
    end = start + policy.n_action_steps
    return action_pred[:, start:end]


def stack_trace_dict(list_of_dicts):
    keys = list(list_of_dicts[0].keys())
    out = {}
    for k in keys:
        out[k] = np.concatenate([d[k] for d in list_of_dicts], axis=0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", default="part2_results")
    ap.add_argument("--trace-count", type=int, default=1000)
    ap.add_argument("--mixer-trace-count", type=int, default=64)
    ap.add_argument("--stale-pairs", type=int, default=100)
    ap.add_argument("--paper-action-steps", type=int, default=3)
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    ckpt = Path(args.checkpoint).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    dp3_root = repo / "3D-Diffusion-Policy"
    sys.path.insert(0, str(dp3_root))
    os.chdir(dp3_root)

    import dill
    import hydra
    from train import TrainDP3Workspace

    device = torch.device(f"cuda:{args.gpu}")
    torch.cuda.set_device(device)

    workspace = TrainDP3Workspace.create_from_checkpoint(str(ckpt))
    policy = workspace.ema_model if workspace.cfg.training.use_ema else workspace.model
    policy.eval().to(device)

    original_n_action_steps = int(policy.n_action_steps)
    policy.n_action_steps = int(args.paper_action_steps)

    dataset = hydra.utils.instantiate(workspace.cfg.task.dataset)
    n = len(dataset)
    if n < 2:
        raise RuntimeError("Dataset has fewer than 2 samples.")

    trace_count = min(args.trace_count, n)
    stale_pairs = min(args.stale_pairs, max(0, n - 1))
    mixer_trace_count = min(args.mixer_trace_count, trace_count)

    # Deterministic evenly spaced dataset indices.
    indices = np.linspace(0, n - 1, trace_count, dtype=np.int64)

    # Identify representative state mixers.
    recorder_probe = MixerRecorder(policy.model, enable=False)
    mixer_manifest = recorder_probe.manifest()

    all_traces = []
    mixer_store = defaultdict(list)
    equivalence_rows = []

    for j, idx in enumerate(indices):
        sample = dataset[int(idx)]
        obs = dict_to_device(sample["obs"], device)
        seed = 100000 + j

        # Official policy output.
        seed_all(seed)
        official = policy.predict_action(obs)

        # Instrumented semantically equivalent path.
        recorder = MixerRecorder(policy.model, enable=(j < mixer_trace_count))
        traced = traced_predict(
            policy, obs, seed=seed,
            mixer_recorder=recorder if j < mixer_trace_count else None
        )

        official_action = tensor_np(official["action"])
        official_pred = tensor_np(official["action_pred"])
        action_err = np.abs(official_action - traced["action"])
        pred_err = np.abs(official_pred - traced["action_pred"])
        equivalence_rows.append({
            "trace_id": j,
            "dataset_index": int(idx),
            "action_max_abs": float(action_err.max()),
            "action_mean_abs": float(action_err.mean()),
            "action_pred_max_abs": float(pred_err.max()),
            "action_pred_mean_abs": float(pred_err.mean()),
        })

        traced["dataset_index"] = np.asarray([[int(idx)]], dtype=np.int64)
        traced["seed"] = np.asarray([[seed]], dtype=np.int64)
        all_traces.append(traced)

        if j < mixer_trace_count:
            for k, values in recorder.records.items():
                if k.endswith("__step"):
                    mixer_store[k].append(np.asarray(values, dtype=np.int64)[None, :])
                else:
                    # values each contain batch dimension 1; concatenate over DDIM calls.
                    mixer_store[k].append(np.concatenate(values, axis=0)[None, ...])
        recorder.close()

    trace_np = stack_trace_dict(all_traces)
    np.savez_compressed(out / "real_policy_traces.npz", **trace_np)

    mixer_np = {}
    for k, vals in mixer_store.items():
        mixer_np[k] = np.concatenate(vals, axis=0)
    np.savez_compressed(out / "mixer_microtraces.npz", **mixer_np)

    with (out / "trace_equivalence.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(equivalence_rows[0].keys()))
        w.writeheader()
        w.writerows(equivalence_rows)

    # Real-checkpoint stale-condition negative control.
    stale_rows = []
    pair_indices = np.linspace(0, n - 2, stale_pairs, dtype=np.int64) if stale_pairs else []
    for j, idx in enumerate(pair_indices):
        sample_a = dataset[int(idx)]
        sample_b = dataset[int(idx) + 1]
        obs_a = dict_to_device(sample_a["obs"], device)
        obs_b = dict_to_device(sample_b["obs"], device)

        ctx_a = extract_feature(policy, obs_a)
        ctx_b = extract_feature(policy, obs_b)
        seed = 200000 + j

        correct_b = action_from_context(policy, ctx_b, ctx_b["global_cond"], seed)
        stale_b = action_from_context(policy, ctx_b, ctx_a["global_cond"], seed)

        diff = (correct_b - stale_b).abs().detach().cpu().numpy()
        stale_rows.append({
            "pair_id": j,
            "dataset_index_a": int(idx),
            "dataset_index_b": int(idx) + 1,
            "action_max_abs": float(diff.max()),
            "action_mean_abs": float(diff.mean()),
            "action_l2": float(np.linalg.norm(diff.reshape(-1), ord=2)),
        })

    if stale_rows:
        with (out / "stale_condition_action_error.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(stale_rows[0].keys()))
            w.writeheader()
            w.writerows(stale_rows)

    eq_max = max(r["action_max_abs"] for r in equivalence_rows)
    eq_mean = float(np.mean([r["action_mean_abs"] for r in equivalence_rows]))

    stale_max = max((r["action_max_abs"] for r in stale_rows), default=None)
    stale_mean = float(np.mean([r["action_mean_abs"] for r in stale_rows])) if stale_rows else None
    stale_l2_mean = float(np.mean([r["action_l2"] for r in stale_rows])) if stale_rows else None

    manifest = {
        "checkpoint": str(ckpt),
        "checkpoint_sha256": sha256(ckpt),
        "dataset_target": str(workspace.cfg.task.dataset._target_),
        "dataset_length": n,
        "trace_count": trace_count,
        "mixer_trace_count": mixer_trace_count,
        "stale_condition_pairs": stale_pairs,
        "num_inference_steps": int(policy.num_inference_steps),
        "horizon": int(policy.horizon),
        "n_obs_steps": int(policy.n_obs_steps),
        "checkpoint_n_action_steps": original_n_action_steps,
        "paper_n_action_steps": int(policy.n_action_steps),
        "action_dim": int(policy.action_dim),
        "condition_type": str(policy.condition_type),
        "mamba_version": str(policy.mamba_version),
        "mixer_modules": mixer_manifest,
        "trace_equivalence_action_max_abs": eq_max,
        "trace_equivalence_action_mean_abs": eq_mean,
        "stale_condition_action_max_abs_over_pairs": stale_max,
        "stale_condition_action_mean_abs_over_pairs": stale_mean,
        "stale_condition_action_l2_mean_over_pairs": stale_l2_mean,
    }
    (out / "trace_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Keep a small checkpoint/config manifest without serializing the checkpoint.
    cfg_text = str(workspace.cfg)
    (out / "checkpoint_manifest.json").write_text(json.dumps({
        "checkpoint": str(ckpt),
        "checkpoint_sha256": sha256(ckpt),
        "use_ema": bool(workspace.cfg.training.use_ema),
        "mamba_version": str(policy.mamba_version),
        "checkpoint_n_action_steps": original_n_action_steps,
        "paper_n_action_steps": int(policy.n_action_steps),
    }, indent=2))
    (out / "checkpoint_cfg.txt").write_text(cfg_text)

    # A strict tracer-equivalence check. Stale-condition magnitude is empirical,
    # so we record it rather than imposing a paper-oriented threshold here.
    tracer_pass = eq_max < 1e-5

    summary = f"""EmbodiCore Part II Summary
===========================

Checkpoint: {ckpt}
Checkpoint SHA256: {sha256(ckpt)}
Mamba version: {policy.mamba_version}
Dataset length: {n}

TRACE COLLECTION
----------------
Real policy invocations: {trace_count}
Mixer microtrace invocations: {mixer_trace_count}
DDIM inference steps: {policy.num_inference_steps}
Published-paper action steps used for tracing: {policy.n_action_steps}
Checkpoint action-step setting: {original_n_action_steps}

TRACER EQUIVALENCE
------------------
Max abs action error vs official predict_action: {eq_max}
Mean abs action error vs official predict_action: {eq_mean}
Tracer equivalence PASS: {tracer_pass}

REAL-CHECKPOINT RESET-BOUNDARY NEGATIVE CONTROL
-----------------------------------------------
Stale-condition pairs: {stale_pairs}
Max action abs error across pairs: {stale_max}
Mean action abs error across pairs: {stale_mean}
Mean action L2 across pairs: {stale_l2_mean}

INTERPRETATION
--------------
Part II provides real-checkpoint denoising/mixer/action traces for Part III.
The stale-condition experiment tests a real policy-level reset boundary using
identical diffusion noise for the correct and stale-condition runs.

Part II does not yet claim full-policy action error from illegal Mamba scan-state
carry; that requires the Part III lowered/bit-accurate stateful implementation.

OVERALL PART II: {'PASS' if tracer_pass else 'FAIL'}
"""
    (out / "summary.txt").write_text(summary)
    print(summary)

    if not tracer_pass:
        raise SystemExit(4)

if __name__ == "__main__":
    main()
