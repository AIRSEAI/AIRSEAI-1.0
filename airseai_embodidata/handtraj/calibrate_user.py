"""Per-user hand calibration -- the 'individualized' in individualized data
collection. One measurement per user, reused across every episode.

Protocol (2 minutes, once per user):
  1. Measure each hand with a ruler: distal wrist crease to the tip of the
     middle finger, hand flat. Record in meters.
  2. (Recommended) Record a 20 s validation episode: hand flat, palm toward
     the camera, held at a marked known distance (e.g. tape on a table edge,
     0.40 m from the phone), slowly rotating. Run with --validate to check
     the pipeline reproduces the known distance -- residual bias indicates
     intrinsics or measurement error.

Usage:
    python -m handtraj.calibrate_user --user weiyu \
        --left 0.181 --right 0.184 --out profiles/weiyu.json
    python -m handtraj.calibrate_user --validate episodes/CAL01 \
        --profile profiles/weiyu.json --known-distance 0.40
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def write_profile(user: str, left_m: float, right_m: float, out: Path):
    prof = {
        "schema": "embodidata.user_profile.v1",
        "user_id": user,
        "hands": {
            "left": {"hand_length_m": left_m},
            "right": {"hand_length_m": right_m},
        },
        "notes": "hand_length_m = distal wrist crease -> middle fingertip, "
                 "hand flat",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(prof, indent=2))
    print(f"wrote {out}")


def validate(episode_dir: str, profile: str, known_distance: float):
    from .config import PipelineCfg
    from .pipeline import run_episode

    cfg = PipelineCfg.load(None)
    cfg.lift.user_profile = profile
    cfg.export.overlay_video = False
    cfg.export.plot = False
    res = run_episode(episode_dir, cfg)
    zs = []
    for tr in res.tracks.values():
        zs += [f.wrist_cam[2] for f in tr.frames
               if f.source == "detected" and f.wrist_cam is not None]
    if not zs:
        print("validation FAILED: no hands detected")
        return
    zs = np.array(zs)
    med = float(np.median(zs))
    bias = med - known_distance
    print(f"median estimated distance: {med:.3f} m "
          f"(target {known_distance:.3f} m)")
    print(f"bias: {100 * bias:+.1f} cm  ({100 * bias / known_distance:+.1f}%)")
    if abs(bias / known_distance) > 0.05:
        print("-> bias > 5%: re-check hand measurement, intrinsics, and "
              "video_rotation before collecting data.")
    else:
        print("-> within 5%: profile looks good.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--user")
    ap.add_argument("--left", type=float, help="left hand length [m]")
    ap.add_argument("--right", type=float, help="right hand length [m]")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--validate", help="calibration episode dir")
    ap.add_argument("--profile", help="profile json for --validate")
    ap.add_argument("--known-distance", type=float, default=0.40)
    args = ap.parse_args()

    if args.validate:
        validate(args.validate, args.profile, args.known_distance)
    else:
        if not (args.user and args.left and args.right and args.out):
            ap.error("need --user --left --right --out (or --validate)")
        write_profile(args.user, args.left, args.right, args.out)


if __name__ == "__main__":
    main()
