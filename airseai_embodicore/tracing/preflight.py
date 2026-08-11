#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def git_head(repo):
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", default="part2_results")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    ckpt = Path(args.checkpoint).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if not (repo / ".git").exists():
        raise SystemExit(f"ERROR: not a git repository: {repo}")
    if not ckpt.is_file():
        raise SystemExit(f"ERROR: checkpoint not found: {ckpt}")

    import torch

    env = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu_count": torch.cuda.device_count(),
        "gpus": [
            torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
        ],
        "mamba_policy_commit": git_head(repo),
        "checkpoint": str(ckpt),
        "checkpoint_sha256": sha256(ckpt),
    }
    (out / "environment.json").write_text(json.dumps(env, indent=2))

    print(json.dumps(env, indent=2))
    if platform.system() != "Linux":
        raise SystemExit("ERROR: Part II must run on Linux.")
    if not torch.cuda.is_available():
        raise SystemExit("ERROR: CUDA is not available.")
    print("PREFLIGHT_PASS")

if __name__ == "__main__":
    main()
