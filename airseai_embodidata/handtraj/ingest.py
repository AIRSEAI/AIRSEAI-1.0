"""Episode ingestion for the EmbodiData-EgoVIM release layout.

Expected episode folder (per the v1.2 release spec):
    episodes/E000123/
        video.mp4
        imu.csv          timestamp, acc_x..z, gyro_x..z        (CoreMotion)
        pose.csv         timestamp, tx ty tz qx qy qz qw       (ARKit T_world_cam)
        meta.json, annotation.json, calibration/, keyframes/
        frames.csv       (optional) frame_idx, timestamp  -- per-frame times

Robust to column-name variants and ms-vs-s timestamps. Non-standard exports:
keep the raw file and add a mapping in configs/pipeline.yaml (per the guide's
"do not overwrite raw data" rule).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pandas as pd  # noqa: F401  (kept top-level: ingest is IO-centric)

from .config import PipelineCfg
from .se3 import pose_from_txyz_quat

log = logging.getLogger("handtraj.ingest")


# ------------------------------------------------------------------ helpers
def _find_col(df: pd.DataFrame, candidates) -> Optional[str]:
    lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def _find_cols(df: pd.DataFrame, candidate_groups) -> Optional[list]:
    for group in candidate_groups:
        cols = [_find_col(df, (c,)) for c in group]
        if all(cols):
            return cols
    return None


def _to_seconds(t: np.ndarray) -> np.ndarray:
    """Auto-detect ms / us / ns timestamps and convert to seconds."""
    t = np.asarray(t, dtype=float)
    if len(t) < 2:
        return t
    dt = float(np.median(np.diff(t)))
    for scale in (1e9, 1e6, 1e3):          # ns, us, ms
        if dt > 0.5 * scale / 1e3:          # dt bigger than 0.5ms in that unit
            log.info("Timestamps look like 1/%g s; converting.", scale)
            return t / scale
    return t


# -------------------------------------------------------------------- types
@dataclass
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    dist: np.ndarray = field(default_factory=lambda: np.zeros(5))

    @property
    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0, self.cx],
                         [0, self.fy, self.cy],
                         [0, 0, 1.0]])

    def scaled(self, w: int, h: int) -> "Intrinsics":
        """Rescale intrinsics to the actual decoded frame size."""
        sx, sy = w / self.width, h / self.height
        return Intrinsics(self.fx * sx, self.fy * sy,
                          self.cx * sx, self.cy * sy, w, h, self.dist)

    def rotated(self, rot_deg: int) -> "Intrinsics":
        """Intrinsics after rotating the image clockwise by rot_deg."""
        if rot_deg % 360 == 0:
            return self
        W, H = self.width, self.height
        if rot_deg % 360 == 90:    # (x,y) -> (H-1-y, x)
            return Intrinsics(self.fy, self.fx, H - 1 - self.cy, self.cx,
                              H, W, self.dist)
        if rot_deg % 360 == 180:
            return Intrinsics(self.fx, self.fy, W - 1 - self.cx, H - 1 - self.cy,
                              W, H, self.dist)
        if rot_deg % 360 == 270:   # (x,y) -> (y, W-1-x)
            return Intrinsics(self.fy, self.fx, self.cy, W - 1 - self.cx,
                              H, W, self.dist)
        raise ValueError(f"Unsupported rotation {rot_deg}")


@dataclass
class Episode:
    path: Path
    episode_id: str
    video_path: Path
    n_frames: int
    fps: float
    width: int
    height: int
    frame_times: np.ndarray          # (N,) seconds, pose clock (pre-sync)
    frame_times_source: str          # frames_csv | pose_1to1 | fps_derived
    imu_t: np.ndarray                # (M,)
    acc: np.ndarray                  # (M,3)
    gyro: np.ndarray                 # (M,3)
    pose_t: np.ndarray               # (P,)
    T_world_cam_arkit: np.ndarray    # (P,4,4) ARKit camera pose in ARKit world
    intrinsics: Intrinsics
    meta: dict = field(default_factory=dict)

    def frames(self):
        """Yield (idx, timestamp, frame_bgr)."""
        cap = cv2.VideoCapture(str(self.video_path))
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok or idx >= len(self.frame_times):
                    break
                yield idx, float(self.frame_times[idx]), frame
                idx += 1
        finally:
            cap.release()


# ------------------------------------------------------------------ loaders
def _load_imu(path: Path, cfg: PipelineCfg):
    df = pd.read_csv(path)
    tcol = _find_col(df, cfg.columns.time)
    acols = _find_cols(df, cfg.columns.acc)
    gcols = _find_cols(df, cfg.columns.gyro)
    if not (tcol and acols and gcols):
        raise ValueError(f"imu.csv columns not recognized: {list(df.columns)}")
    t = _to_seconds(df[tcol].to_numpy())
    acc = df[acols].to_numpy(dtype=float)
    gyro = df[gcols].to_numpy(dtype=float)
    good = np.isfinite(t) & np.isfinite(acc).all(1) & np.isfinite(gyro).all(1)
    order = np.argsort(t[good])
    return t[good][order], acc[good][order], gyro[good][order]


def _load_pose(path: Path, cfg: PipelineCfg):
    df = pd.read_csv(path)
    tcol = _find_col(df, cfg.columns.time)
    pcols = _find_cols(df, cfg.columns.pos)
    qcols = _find_cols(df, cfg.columns.quat)
    if not (tcol and pcols and qcols):
        raise ValueError(f"pose.csv columns not recognized: {list(df.columns)}")
    t = _to_seconds(df[tcol].to_numpy())
    pos = df[pcols].to_numpy(dtype=float)
    quat = df[qcols].to_numpy(dtype=float)
    good = (np.isfinite(t) & np.isfinite(pos).all(1) & np.isfinite(quat).all(1)
            & (np.linalg.norm(quat, axis=1) > 1e-6))
    t, pos, quat = t[good], pos[good], quat[good]
    order = np.argsort(t)
    t, pos, quat = t[order], pos[order], quat[order]
    quat = quat / np.linalg.norm(quat, axis=1, keepdims=True)
    Ts = np.stack([pose_from_txyz_quat(p, q) for p, q in zip(pos, quat)])
    return t, Ts


def _load_intrinsics(ep_dir: Path, cfg: PipelineCfg,
                     vid_w: int, vid_h: int) -> Intrinsics:
    cam = cfg.camera
    if cam.fx is not None:
        intr = Intrinsics(cam.fx, cam.fy or cam.fx,
                          cam.cx if cam.cx is not None else (cam.calib_width or vid_w) / 2,
                          cam.cy if cam.cy is not None else (cam.calib_height or vid_h) / 2,
                          cam.calib_width or vid_w, cam.calib_height or vid_h,
                          np.asarray(cam.dist_coeffs, dtype=float))
    else:
        intr = None
        calib_dir = ep_dir / "calibration"
        if calib_dir.exists():
            for f in sorted(calib_dir.glob("*.json")):
                try:
                    d = json.loads(f.read_text())
                    fx = d.get("fx") or d.get("focal_length_x") or \
                        (d.get("intrinsics") or {}).get("fx")
                    if fx is None and "camera_matrix" in d:
                        K = np.asarray(d["camera_matrix"], float).reshape(3, 3)
                        fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
                    else:
                        fy = d.get("fy", fx)
                        cx = d.get("cx"); cy = d.get("cy")
                    w = int(d.get("width", d.get("image_width", vid_w)))
                    h = int(d.get("height", d.get("image_height", vid_h)))
                    if fx:
                        intr = Intrinsics(float(fx), float(fy or fx),
                                          float(cx if cx is not None else w / 2),
                                          float(cy if cy is not None else h / 2),
                                          w, h)
                        log.info("Intrinsics from %s", f.name)
                        break
                except Exception as e:  # keep scanning other files
                    log.debug("calibration file %s unusable: %s", f.name, e)
        if intr is None:
            # Heuristic: iPhone wide camera hFOV ~ 69 deg -> fx ~ 0.73 * W.
            fx = 0.73 * max(vid_w, vid_h)
            intr = Intrinsics(fx, fx, vid_w / 2, vid_h / 2, vid_w, vid_h)
            log.warning("No calibration found. Using heuristic fx=%.0f. "
                        "Metric accuracy will suffer -- export real intrinsics "
                        "from ARKit (camera.intrinsics).", fx)
    intr = intr.rotated(cfg.camera.video_rotation)
    if (intr.width, intr.height) != (vid_w, vid_h):
        intr = intr.scaled(vid_w, vid_h)
    return intr


def load_episode(ep_dir: str | Path, cfg: PipelineCfg) -> Episode:
    ep_dir = Path(ep_dir)
    video = next((p for p in [ep_dir / "video.mp4", ep_dir / "video.mov",
                              ep_dir / "video.avi"] if p.exists()), None)
    if video is None:
        cand = sorted(list(ep_dir.glob("*.mp4")) + list(ep_dir.glob("*.mov"))
                      + list(ep_dir.glob("*.avi")))
        if not cand:
            raise FileNotFoundError(f"No video in {ep_dir}")
        video = cand[0]

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    imu_t, acc, gyro = _load_imu(ep_dir / "imu.csv", cfg)
    pose_t, Ts = _load_pose(ep_dir / "pose.csv", cfg)

    # --- per-frame timestamps: best available source -----------------------
    frames_csv = ep_dir / "frames.csv"
    if frames_csv.exists():
        fdf = pd.read_csv(frames_csv)
        tcol = _find_col(fdf, cfg.columns.time)
        frame_times = _to_seconds(fdf[tcol].to_numpy())[:n_frames]
        source = "frames_csv"
    elif abs(len(pose_t) - n_frames) <= 2:
        # ARKit logs one pose per ARFrame -> rows line up with video frames.
        frame_times = pose_t[:n_frames].copy()
        source = "pose_1to1"
    else:
        frame_times = pose_t[0] + np.arange(n_frames) / fps
        source = "fps_derived"   # sync.py can still refine a constant offset
    log.info("Frame timestamps: %s (video %dx%d @%.1ffps, %d frames; "
             "%d poses, %d imu samples)", source, vid_w, vid_h, fps,
             n_frames, len(pose_t), len(imu_t))

    meta = {}
    meta_path = ep_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            pass

    return Episode(
        path=ep_dir,
        episode_id=meta.get("episode_id", ep_dir.name),
        video_path=video, n_frames=n_frames, fps=float(fps),
        width=vid_w, height=vid_h,
        frame_times=np.asarray(frame_times, float),
        frame_times_source=source,
        imu_t=imu_t, acc=acc, gyro=gyro,
        pose_t=pose_t, T_world_cam_arkit=Ts,
        intrinsics=_load_intrinsics(ep_dir, cfg, vid_w, vid_h),
        meta=meta,
    )
