#!/usr/bin/env python3
import argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    roots = [
        repo / "3D-Diffusion-Policy" / "data" / "outputs",
        repo / "data" / "outputs",
    ]
    cands = []
    for root in roots:
        if root.exists():
            cands.extend(root.rglob("*.ckpt"))

    cands = sorted(set(cands), key=lambda p: p.stat().st_mtime, reverse=True)

    if not cands:
        print("NEED_CHECKPOINT")
        print("No .ckpt found under the official Mamba-Policy output directories.")
        raise SystemExit(2)

    print("CHECKPOINT_CANDIDATES")
    for i, p in enumerate(cands[:50]):
        print(f"{i:02d}  {p}")

    latest = next((p for p in cands if p.name == "latest.ckpt"), cands[0])
    print()
    print(f"AUTO_SELECTED={latest}")

if __name__ == "__main__":
    main()
