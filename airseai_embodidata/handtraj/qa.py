"""QA metrics per episode -- feeds the release-package qc_report habit of the
EmbodiData collection guide: every derived annotation ships with quality
evidence so bad episodes are caught before training or release.
"""
from __future__ import annotations

import numpy as np


def _track_stats(track, frame_times) -> dict:
    frames = track.frames
    n = len(frames)
    det = [f for f in frames if f.source == "detected"]
    valid = [f for f in frames if f.valid]
    stats = {
        "frames": n,
        "detected": len(det),
        "filled": sum(1 for f in frames if f.source == "filled"),
        "coverage": len(valid) / max(n, 1),
        "mean_conf": float(np.mean([f.conf for f in det])) if det else 0.0,
        "mean_reproj_px": float(np.mean([f.reproj_err for f in det]))
        if det else float("nan"),
        "kappa_cv": float("nan"),
        "jerk_rms": float("nan"),
        "outliers_gated": track.n_outliers,
        "kf_reinits": track.n_reinits,
        "max_gap_frames": 0,
    }
    if det:
        kappas = np.array([f.kappa for f in det if np.isfinite(f.kappa)])
        if len(kappas) > 3:
            stats["kappa_cv"] = float(kappas.std() / (kappas.mean() + 1e-9))
    # longest run of missing frames between first/last detection
    idxs = [i for i, f in enumerate(frames) if f.source == "detected"]
    if len(idxs) > 1:
        stats["max_gap_frames"] = int(np.max(np.diff(idxs)) - 1)
    # smoothness: RMS jerk of the smoothed wrist trajectory
    vi = [i for i, f in enumerate(frames) if f.valid]
    if len(vi) > 12:
        p = np.stack([frames[i].wrist_world for i in vi])
        t = frame_times[vi]
        dt = np.gradient(t)
        v = np.gradient(p, axis=0) / dt[:, None]
        a = np.gradient(v, axis=0) / dt[:, None]
        j = np.gradient(a, axis=0) / dt[:, None]
        stats["jerk_rms"] = float(np.sqrt((np.linalg.norm(j, axis=1) ** 2).mean()))
    return stats


def build_report(ep, tracks, sync_info, total_flips) -> dict:
    rep = {
        "episode_id": ep.episode_id,
        "n_frames": ep.n_frames,
        "fps": ep.fps,
        "duration_s": float(ep.frame_times[-1] - ep.frame_times[0])
        if ep.n_frames > 1 else 0.0,
        "frame_times_source": ep.frame_times_source,
        "sync": sync_info,
        "handedness_flips": int(total_flips),
        "hands": {s: _track_stats(tr, ep.frame_times)
                  for s, tr in tracks.items()},
    }
    warnings, failures = [], []
    if not sync_info["stationary"]["start"]["still"]:
        warnings.append("protocol: no stationary segment at start")
    if not sync_info["stationary"]["end"]["still"]:
        warnings.append("protocol: no stationary segment at end")
    if abs(sync_info.get("pose_imu_offset_s") or 0.0) > 0.01:
        warnings.append("pose and IMU clocks disagree by "
                        f"{1e3 * sync_info['pose_imu_offset_s']:.0f} ms -- "
                        "check the app export")
    if ep.frame_times_source == "fps_derived" and \
            (sync_info.get("video_start_corr") or 0.0) < 0.5:
        warnings.append("no per-frame timestamps and video<->gyro anchoring "
                        "weak -- timing may be off; export frames.csv")
    any_hand = False
    for s, h in rep["hands"].items():
        if h["detected"] > 0:
            any_hand = True
        if 0 < h["coverage"] < 0.3:
            warnings.append(f"{s} hand coverage only {h['coverage']:.0%}")
        if h["mean_reproj_px"] == h["mean_reproj_px"] and \
                h["mean_reproj_px"] > 6.0:
            warnings.append(f"{s} hand mean reprojection "
                            f"{h['mean_reproj_px']:.1f}px (intrinsics? blur?)")
        if h["kappa_cv"] == h["kappa_cv"] and h["kappa_cv"] > 0.15:
            warnings.append(f"{s} hand scale unstable (kappa CV "
                            f"{h['kappa_cv']:.2f}) -- depth estimates noisy")
    if not any_hand:
        failures.append("no hands detected in the whole episode")

    rep["warnings"] = warnings
    rep["failures"] = failures
    rep["verdict"] = ("FAIL" if failures else
                      "WARN" if warnings else "PASS")
    return rep


def summary_line(rep: dict) -> str:
    h = rep["hands"]
    return (f"[{rep['verdict']}] {rep['episode_id']}: "
            f"L {h['left']['coverage']:.0%} / R {h['right']['coverage']:.0%} "
            f"coverage, reproj L {h['left']['mean_reproj_px']:.1f}px "
            f"R {h['right']['mean_reproj_px']:.1f}px, "
            f"{len(rep['warnings'])} warnings")
