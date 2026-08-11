#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path

def git_head(repo):
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default="part2_results")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    dp3 = repo / "3D-Diffusion-Policy" / "diffusion_policy_3d" / "policy" / "dp3.py"
    cfg = repo / "3D-Diffusion-Policy" / "diffusion_policy_3d" / "config" / "dp3_mamba.yaml"

    text = dp3.read_text(errors="ignore")
    cfgtext = cfg.read_text(errors="ignore")

    checks = {
        "global_cond_before_conditional_sample": text.find("global_cond = nobs_features") < text.find("self.conditional_sample("),
        "ddim_loop": bool(re.search(r"for\s+t\s+in\s+scheduler\.timesteps", text)),
        "model_receives_global_cond": "global_cond=global_cond" in text,
        "trajectory_scheduler_update": "scheduler.step" in text and ".prev_sample" in text,
        "config_mamba_v1": "mamba_version: mambavision_v1" in cfgtext,
        "config_ddim_10": bool(re.search(r"num_inference_steps:\s*10", cfgtext)),
    }

    report = {
        "mamba_policy_commit": git_head(repo),
        "checks": checks,
        "pass": all(checks.values()),
    }
    (out / "source_audit.json").write_text(json.dumps(report, indent=2))
    (out / "source_audit.txt").write_text(
        "\n".join([f"{k}: {v}" for k, v in checks.items()])
        + f"\nSOURCE_AUDIT_PASS: {report['pass']}\n"
    )
    print(json.dumps(report, indent=2))
    if not report["pass"]:
        raise SystemExit(3)

if __name__ == "__main__":
    main()
