"""End-to-end episode processing: the "reverse SLAM" orchestrator.

Classic SLAM: a static world observed by a moving camera; solve the camera.
Here the camera solution already exists (ARKit VIO), and the quantity of
interest is a *moving* object observed from that moving camera. The problem
factorizes cleanly:

    T_world_hand(t) = T_world_cam(t) . T_cam_hand(t)
    ----------------   ---------------   --------------
    what we want       ego-motion        per-frame monocular
                       (ARKit / SLAM)    hand pose (PnP lift)

Stages
------
  1. ingest      episode files, intrinsics, timestamps      (ingest.py)
  2. sync        clock offset + stationary protocol checks  (sync.py)
  3. detect      per-frame 2D hands + local 3D shape        (detect2d.py)
  4. lift        metric T_cam_hand via personalized PnP     (lift3d.py)
  5. compose     T_world_hand = T_world_cam . T_cam_hand         (here)
  6. track       L/R association, KF + RTS, gap fill        (tracking.py)
  7. export/qa   csv/npz/json, overlay, report              (export.py, qa.py)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .config import PipelineCfg, load_user_profile
from .detect2d import (detections_from_npz, detections_to_npz, make_detector,
                       polyline_length)
from .egomotion import EgoMotion
from .ingest import Episode, load_episode
from .lift3d import Lifter, pinch_aperture_m
from .se3 import R_to_quat, transform_points
from .sync import estimate_offset, estimate_video_start, stationary_check
from .tracking import HandTrack, associate
from . import export as export_mod
from . import qa as qa_mod

log = logging.getLogger("handtraj.pipeline")


def _load_depth(depth_dir: Optional[Path], idx: int):
    """Optional per-frame metric depth (e.g. exported ARKit sceneDepth)."""
    if depth_dir is None:
        return None
    for pattern in (f"depth_{idx:06d}.npy", f"{idx:06d}.npy"):
        p = depth_dir / pattern
        if p.exists():
            return np.load(p)
    return None


class EpisodeResult:
    def __init__(self, episode: Episode, tracks: Dict[str, HandTrack],
                 ego: EgoMotion, sync_info: dict, qa_report: dict,
                 out_dir: Path):
        self.episode = episode
        self.tracks = tracks
        self.ego = ego
        self.sync_info = sync_info
        self.qa_report = qa_report
        self.out_dir = out_dir


def run_episode(ep_dir: str | Path, cfg: PipelineCfg,
                detector=None) -> EpisodeResult:
    t_start = time.time()
    ep = load_episode(ep_dir, cfg)
    out_dir = ep.path / cfg.export.out_subdir
    out_dir.mkdir(exist_ok=True)

    # ---- stage 2: sync ------------------------------------------------------
    # (a) pose vs IMU: both host-clock stamped -> consistency check only.
    sync = estimate_offset(ep.imu_t, ep.gyro, ep.pose_t,
                           ep.T_world_cam_arkit, cfg.sync) \
        if cfg.sync.estimate_offset else None
    stationary = stationary_check(ep.imu_t, ep.gyro, cfg.sync)
    # (b) video clock: only an issue when frame times were fps-derived; then
    # anchor the video start on the IMU clock via optical-flow <-> gyro.
    video_sync = None
    if ep.frame_times_source == "fps_derived":
        video_sync = estimate_video_start(ep.video_path, ep.fps,
                                          ep.imu_t, ep.gyro, cfg.sync)
        if video_sync.reliable:
            ep.frame_times = video_sync.t0 + np.arange(ep.n_frames) / ep.fps
    sync_info = {
        "pose_imu_offset_s": getattr(sync, "offset_s", 0.0),
        "pose_imu_corr": getattr(sync, "peak_corr", np.nan),
        "video_start_t0": getattr(video_sync, "t0", None),
        "video_start_corr": getattr(video_sync, "peak_corr", None),
        "frame_times_source": ep.frame_times_source,
        "stationary": stationary,
    }

    ego = EgoMotion(ep.pose_t, ep.T_world_cam_arkit,
                    video_rotation=cfg.camera.video_rotation,
                    world_convention=cfg.export.world_convention)

    # ---- stage 3: detect (cached) -------------------------------------------
    det_cache = out_dir / "detections.npz"
    if det_cache.exists():
        log.info("Using cached detections %s", det_cache)
        all_obs = detections_from_npz(det_cache, ep.n_frames)
    else:
        det = detector or make_detector(cfg.detector)
        all_obs: List[list] = [[] for _ in range(ep.n_frames)]
        for idx, t, frame in ep.frames():
            all_obs[idx] = det.detect(frame, t)
            if idx % 300 == 0:
                log.info("detect %d/%d", idx, ep.n_frames)
        det.close()
        detections_to_npz(det_cache, all_obs)

    # ---- stages 4-6: lift + compose + track ---------------------------------
    user = load_user_profile(cfg.lift.user_profile,
                             cfg.lift.default_hand_length_m)
    lifter = Lifter(cfg.lift, ep.intrinsics,
                    {"left": user["left"], "right": user["right"]})
    depth_dir = Path(cfg.lift.depth_dir) if cfg.lift.depth_dir else None

    tracks = {s: HandTrack(s, ep.n_frames, cfg.track) for s in ("left", "right")}
    total_flips = 0
    T_world_cam_per_frame = np.zeros((ep.n_frames, 4, 4))
    prev_t = None
    for idx in range(ep.n_frames):
        t = float(ep.frame_times[idx])
        dt = (t - prev_t) if prev_t is not None else 1.0 / ep.fps
        prev_t = t
        T_wc = ego.T_world_cam(t)
        T_world_cam_per_frame[idx] = T_wc

        assoc = associate(all_obs[idx], tracks, idx)
        total_flips += assoc["flips"]
        for side in ("left", "right"):
            obs = assoc["assigned"][side]
            meas = None
            if obs is not None and ego.in_range(t):
                pose3d = lifter.lift(obs, _load_depth(depth_dir, idx))
                if pose3d is not None:
                    T_wh = T_wc @ pose3d.T_cam_hand
                    kps_world = transform_points(T_wc, pose3d.kps_cam)
                    meas = {
                        "wrist_world": kps_world[0],
                        "quat_world": R_to_quat(T_wh[:3, :3]),
                        "kps_world": kps_world,
                        "kps_cam": pose3d.kps_cam,
                        "kps_2d": pose3d.kps_2d,
                        "wrist_cam": pose3d.wrist_cam,
                        "conf": pose3d.conf,
                        "reproj_err": pose3d.reproj_err_px,
                        "kappa": pose3d.kappa,
                        "pinch_m": pinch_aperture_m(pose3d.kps_cam),
                    }
            tracks[side].update(idx, t, dt, meas)

    for tr in tracks.values():
        tr.finalize(ep.frame_times)

    # ---- stage 7: QA + export ----------------------------------------------
    qa_report = qa_mod.build_report(ep, tracks, sync_info, total_flips)
    export_mod.write_outputs(ep, tracks, T_world_cam_per_frame, ego,
                             qa_report, cfg, out_dir, user)
    log.info("Episode %s done in %.1fs -> %s  [%s]",
             ep.episode_id, time.time() - t_start, out_dir,
             qa_report["verdict"])
    return EpisodeResult(ep, tracks, ego, sync_info, qa_report, out_dir)
