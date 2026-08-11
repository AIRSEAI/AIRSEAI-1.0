#!/usr/bin/env python3
import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default="part2_results")
    ap.add_argument("--zip", default="part2_real_traces.zip")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    zpath = Path(args.zip).resolve()

    required = [
        "environment.json",
        "checkpoint_manifest.json",
        "checkpoint_cfg.txt",
        "trace_manifest.json",
        "trace_equivalence.csv",
        "real_policy_traces.npz",
        "mixer_microtraces.npz",
        "stale_condition_action_error.csv",
        "summary.txt",
        "source_audit.txt",
        "source_audit.json",
    ]
    missing = [x for x in required if not (out / x).exists()]
    if missing:
        raise SystemExit("ERROR: missing outputs: " + ", ".join(missing))

    if zpath.exists():
        zpath.unlink()
    shutil.make_archive(str(zpath.with_suffix("")), "zip", root_dir=out.parent, base_dir=out.name)
    print(f"CREATED={zpath}")

if __name__ == "__main__":
    main()
