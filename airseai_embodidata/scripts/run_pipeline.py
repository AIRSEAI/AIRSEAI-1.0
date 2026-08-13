#!/usr/bin/env python3
"""Process EmbodiData episodes into world-frame hand-trajectory annotations.

Examples:
    # one episode
    python scripts/run_pipeline.py episodes/E000123 \
        --user-profile profiles/weiyu.json

    # whole release, custom config, no overlay videos
    python scripts/run_pipeline.py EmbodiData-EgoVIM-v1.2/episodes --all \
        --config configs/pipeline.yaml --no-overlay

Outputs per episode (in <episode>/hand_annotation/):
    hands.csv, hands.npz, hand_annotation.json (QA), overlay.mp4,
    trajectory.png, detections.npz (cache -- delete to force re-detection)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handtraj.config import PipelineCfg          # noqa: E402
from handtraj.pipeline import run_episode        # noqa: E402
from handtraj import qa as qa_mod                # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="episode dir, or episodes root with --all")
    ap.add_argument("--all", action="store_true",
                    help="process every subdirectory containing a video")
    ap.add_argument("--config", help="configs/pipeline.yaml")
    ap.add_argument("--user-profile", help="profiles/<user>.json")
    ap.add_argument("--backend", choices=["mediapipe", "hamer"])
    ap.add_argument("--no-overlay", action="store_true")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--world", choices=["arkit_yup", "zup"])
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname).1s %(name)s: %(message)s")

    cfg = PipelineCfg.load(args.config)
    if args.user_profile:
        cfg.lift.user_profile = args.user_profile
    if args.backend:
        cfg.detector.backend = args.backend
    if args.no_overlay:
        cfg.export.overlay_video = False
    if args.no_plot:
        cfg.export.plot = False
    if args.world:
        cfg.export.world_convention = args.world

    root = Path(args.path)
    if args.all:
        episodes = sorted(
            d for d in root.iterdir()
            if d.is_dir() and (any(d.glob("*.mp4")) or any(d.glob("*.mov"))))
    else:
        episodes = [root]

    reports = []
    for ep_dir in episodes:
        try:
            res = run_episode(ep_dir, cfg)
            reports.append(res.qa_report)
            print(qa_mod.summary_line(res.qa_report))
        except Exception as e:
            logging.exception("Episode %s failed: %s", ep_dir.name, e)
            reports.append({"episode_id": ep_dir.name, "verdict": "ERROR",
                            "error": str(e)})

    if args.all and reports:
        out = root / "hand_annotation_summary.json"
        out.write_text(json.dumps(reports, indent=2))
        n = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
        for r in reports:
            n[r["verdict"]] = n.get(r["verdict"], 0) + 1
        print(f"\n{len(reports)} episodes: {n}")
        print(f"summary -> {out}")


if __name__ == "__main__":
    main()
