"""Outputs: hands.csv, hands.npz, hand_annotation.json, overlay video, plots.

Design goal: everything a downstream consumer (policy training, skill
analysis, dataset release) needs, with per-frame validity/provenance so no
one ever trains on silently-interpolated garbage.

The overlay video doubles as the pipeline's strongest self-check: smoothed
*world-frame* wrist trails are re-projected into each frame through the
per-frame camera pose. If conventions/sync/lift are right, the trail sticks
to where the hand actually went in the scene while the head moves freely.
Any frame-convention bug makes the trail swim -- instantly visible.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import cv2
import numpy as np

from .detect2d import BONES
from .se3 import T_inv

log = logging.getLogger("handtraj.export")

SIDE_COLORS = {"left": (255, 160, 40), "right": (60, 220, 60)}  # BGR


# ------------------------------------------------------------------- tables
def write_outputs(ep, tracks, T_world_cam, ego, qa_report, cfg, out_dir: Path,
                  user_profile: dict):
    exp = cfg.export
    if exp.write_csv:
        _write_csv(ep, tracks, out_dir / "hands.csv")
    if exp.write_npz:
        _write_npz(ep, tracks, T_world_cam, out_dir / "hands.npz")
    ann = {
        "schema": "embodidata.hand_annotation.v1",
        "episode_id": ep.episode_id,
        "user": user_profile,
        "world_convention": exp.world_convention,
        "frame_times_source": ep.frame_times_source,
        "intrinsics": {"fx": ep.intrinsics.fx, "fy": ep.intrinsics.fy,
                       "cx": ep.intrinsics.cx, "cy": ep.intrinsics.cy,
                       "width": ep.intrinsics.width,
                       "height": ep.intrinsics.height},
        "config": cfg.dump(),
        "qa": qa_report,
    }
    (out_dir / "hand_annotation.json").write_text(json.dumps(ann, indent=2))
    if exp.overlay_video:
        _write_overlay(ep, tracks, T_world_cam, cfg,
                       out_dir / "overlay.mp4")
    if exp.plot:
        try:
            _write_plot(ep, tracks, T_world_cam, out_dir / "trajectory.png")
        except Exception as e:   # matplotlib optional
            log.warning("plot skipped: %s", e)


def _write_csv(ep, tracks, path: Path):
    cols = ["frame", "t", "side", "valid", "source", "conf", "reproj_px",
            "wx", "wy", "wz", "qx", "qy", "qz", "qw",
            "cx", "cy", "cz", "pinch_m", "kappa"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for side, tr in tracks.items():
            for i, fr in enumerate(tr.frames):
                if not fr.valid:
                    continue
                q = fr.quat_world if fr.quat_world is not None else [np.nan] * 4
                c = fr.wrist_cam if fr.wrist_cam is not None else [np.nan] * 3
                w.writerow([i, f"{ep.frame_times[i]:.6f}", side, 1, fr.source,
                            f"{fr.conf:.3f}", f"{fr.reproj_err:.2f}",
                            *[f"{v:.5f}" for v in fr.wrist_world],
                            *[f"{v:.6f}" for v in q],
                            *[f"{v:.5f}" for v in c],
                            f"{fr.pinch_m:.5f}", f"{fr.kappa:.4f}"])
    log.info("wrote %s", path)


def _stack_or_nan(frames, attr, shape):
    out = np.full((len(frames),) + shape, np.nan)
    for i, fr in enumerate(frames):
        v = getattr(fr, attr)
        if v is not None:
            out[i] = v
    return out


def _write_npz(ep, tracks, T_world_cam, path: Path):
    data = {
        "frame_times": ep.frame_times,
        "T_world_cam": T_world_cam,
    }
    for side, tr in tracks.items():
        p = side[0]  # l / r
        data[f"{p}_valid"] = np.array([f.valid for f in tr.frames], bool)
        data[f"{p}_source"] = np.array(
            [{"missing": 0, "detected": 1, "filled": 2}[f.source]
             for f in tr.frames], np.int8)
        data[f"{p}_wrist_world"] = _stack_or_nan(tr.frames, "wrist_world", (3,))
        data[f"{p}_quat_world"] = _stack_or_nan(tr.frames, "quat_world", (4,))
        data[f"{p}_kps_world"] = _stack_or_nan(tr.frames, "kps_world", (21, 3))
        data[f"{p}_kps_cam"] = _stack_or_nan(tr.frames, "kps_cam", (21, 3))
        data[f"{p}_kps_2d"] = _stack_or_nan(tr.frames, "kps_2d", (21, 2))
        data[f"{p}_conf"] = np.array([f.conf for f in tr.frames], np.float32)
        data[f"{p}_pinch_m"] = np.array([f.pinch_m for f in tr.frames],
                                        np.float32)
    np.savez_compressed(path, **data)
    log.info("wrote %s", path)


def to_lerobot_arrays(npz_path: Path, side: str = "right") -> dict:
    """Minimal bridge to policy training (LeRobot-style keys): wrist pose +
    pinch aperture as the end-effector 'action' stream, in the world frame.
    Full conversion (episode chunking, video frames, stats) per GUIDE.md 9.
    """
    d = np.load(npz_path)
    p = side[0]
    valid = d[f"{p}_valid"]
    return {
        "timestamp": d["frame_times"][valid],
        "observation.ee_pos": d[f"{p}_wrist_world"][valid],
        "observation.ee_quat": d[f"{p}_quat_world"][valid],
        "observation.gripper": d[f"{p}_pinch_m"][valid],
        "observation.head_pose": d["T_world_cam"][valid],
    }


# ------------------------------------------------------------------ overlay
def _project(K, T_cam_world, pts_world):
    pc = pts_world @ T_cam_world[:3, :3].T + T_cam_world[:3, 3]
    z = pc[:, 2].copy()
    ok = z > 0.05
    z[~ok] = np.nan
    u = K[0, 0] * pc[:, 0] / z + K[0, 2]
    v = K[1, 1] * pc[:, 1] / z + K[1, 2]
    return np.stack([u, v], 1), ok


def _write_overlay(ep, tracks, T_world_cam, cfg, path: Path):
    K = ep.intrinsics.K
    trail_n = int(cfg.export.overlay_trail_s * ep.fps)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                         ep.fps, (ep.width, ep.height))
    if not vw.isOpened():
        log.warning("VideoWriter failed for %s -- overlay skipped", path)
        return
    for idx, t, frame in ep.frames():
        T_cw = T_inv(T_world_cam[idx])
        for side, tr in tracks.items():
            col = SIDE_COLORS[side]
            fr = tr.frames[idx]
            # 2D skeleton
            if fr.source == "detected" and fr.kps_2d is not None:
                for a, b in BONES:
                    pa, pb = fr.kps_2d[a], fr.kps_2d[b]
                    cv2.line(frame, tuple(np.int32(pa)), tuple(np.int32(pb)),
                             col, 2)
                cv2.putText(frame, f"{side[0].upper()} {fr.conf:.2f}",
                            tuple(np.int32(fr.kps_2d[0] + [0, 25])),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            # world-frame wrist trail re-projected into this frame
            lo = max(0, idx - trail_n)
            pts = [tr.frames[j].wrist_world
                   for j in range(lo, idx + 1) if tr.frames[j].valid]
            if len(pts) >= 2:
                uv, ok = _project(K, T_cw, np.stack(pts))
                uv = uv[ok & np.isfinite(uv).all(1)]
                for a, b in zip(uv[:-1], uv[1:]):
                    cv2.line(frame, tuple(np.int32(a)), tuple(np.int32(b)),
                             col, 3)
        cv2.putText(frame, f"frame {idx}  t={t:.2f}s", (12, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        vw.write(frame)
    vw.release()
    log.info("wrote %s", path)


def _write_plot(ep, tracks, T_world_cam, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(13, 5))
    ax3 = fig.add_subplot(1, 2, 1, projection="3d")
    axt = fig.add_subplot(1, 2, 2)
    head = T_world_cam[:, :3, 3]
    ax3.plot(*head.T, "k--", lw=1, alpha=0.6, label="head")
    axt.plot(head[:, 0], head[:, 2], "k--", lw=1, alpha=0.6, label="head")
    for side, tr in tracks.items():
        pts = np.array([f.wrist_world for f in tr.frames if f.valid])
        if not len(pts):
            continue
        c = "tab:orange" if side == "left" else "tab:green"
        ax3.plot(*pts.T, color=c, lw=1.5, label=f"{side} wrist")
        axt.plot(pts[:, 0], pts[:, 2], color=c, lw=1.5, label=f"{side} wrist")
    ax3.set_title(f"{ep.episode_id}: world-frame trajectories")
    ax3.legend(); axt.legend()
    axt.set_aspect("equal", adjustable="datalim")
    axt.set_xlabel("x [m]"); axt.set_ylabel("z [m]")
    axt.set_title("top view")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    log.info("wrote %s", path)
