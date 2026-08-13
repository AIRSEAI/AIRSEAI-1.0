"""Pipeline configuration (YAML-overridable dataclasses)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json

import yaml


@dataclass
class CameraCfg:
    # Intrinsics for the *exported video* resolution. If None, the pipeline
    # looks for episode calibration files, then falls back to a heuristic.
    fx: Optional[float] = None
    fy: Optional[float] = None
    cx: Optional[float] = None
    cy: Optional[float] = None
    calib_width: Optional[int] = None   # resolution the intrinsics refer to
    calib_height: Optional[int] = None
    dist_coeffs: list = field(default_factory=lambda: [0., 0., 0., 0., 0.])
    # 0 / 90 / 180 / 270: clockwise rotation applied to the sensor image to
    # produce the exported video (portrait capture is usually 90).
    video_rotation: int = 0


@dataclass
class SyncCfg:
    estimate_offset: bool = True     # gyro <-> pose-rate cross-correlation
    max_offset_s: float = 0.5
    resample_hz: float = 100.0
    stationary_window_s: float = 3.0   # protocol: still 3 s at start/end
    stationary_gyro_thresh: float = 0.15  # rad/s RMS


@dataclass
class DetectorCfg:
    backend: str = "mediapipe"       # "mediapipe" | "hamer"
    max_hands: int = 2
    min_det_conf: float = 0.5
    min_track_conf: float = 0.5
    model_complexity: int = 1
    # MediaPipe assumes selfie (mirrored) input; EmbodiData uses the rear
    # camera (unmirrored), so reported handedness must be flipped.
    flip_handedness: bool = True


@dataclass
class LiftCfg:
    user_profile: Optional[str] = None    # JSON with measured hand lengths
    default_hand_length_m: float = 0.185  # wrist -> middle fingertip
    reproj_thresh_px: float = 10.0        # gate on PnP reprojection error
    z_range_m: tuple = (0.12, 1.5)        # plausible hand depth from head
    depth_dir: Optional[str] = None       # optional per-frame metric depth
    depth_scale: float = 1.0              # units -> meters


@dataclass
class TrackCfg:
    sigma_accel: float = 8.0        # KF process noise (m/s^2) - hands are fast
    sigma_meas: float = 0.02        # KF measurement noise (m)
    gate_chi2: float = 16.27        # chi2 0.999, 3 dof
    max_fill_gap_frames: int = 10   # bridge gaps up to this length
    reinit_gap_frames: int = 30     # longer gap -> re-initialize filter
    oneeuro_min_cutoff: float = 1.5
    oneeuro_beta: float = 0.3
    orient_slerp_alpha: float = 0.6


@dataclass
class ExportCfg:
    out_subdir: str = "hand_annotation"
    write_csv: bool = True
    write_npz: bool = True
    overlay_video: bool = True
    overlay_trail_s: float = 3.0
    plot: bool = True
    world_convention: str = "arkit_yup"   # "arkit_yup" | "zup"


@dataclass
class ColumnsCfg:
    """Column-name candidates for robust CSV ingestion."""
    time: tuple = ("timestamp", "time", "t", "ts")
    acc: tuple = (("acc_x", "acc_y", "acc_z"),
                  ("accel_x", "accel_y", "accel_z"),
                  ("ax", "ay", "az"))
    gyro: tuple = (("gyro_x", "gyro_y", "gyro_z"),
                   ("rot_x", "rot_y", "rot_z"),
                   ("gx", "gy", "gz"))
    pos: tuple = (("tx", "ty", "tz"),
                  ("pos_x", "pos_y", "pos_z"),
                  ("x", "y", "z"))
    quat: tuple = (("qx", "qy", "qz", "qw"),
                   ("quat_x", "quat_y", "quat_z", "quat_w"))


@dataclass
class PipelineCfg:
    camera: CameraCfg = field(default_factory=CameraCfg)
    sync: SyncCfg = field(default_factory=SyncCfg)
    detector: DetectorCfg = field(default_factory=DetectorCfg)
    lift: LiftCfg = field(default_factory=LiftCfg)
    track: TrackCfg = field(default_factory=TrackCfg)
    export: ExportCfg = field(default_factory=ExportCfg)
    columns: ColumnsCfg = field(default_factory=ColumnsCfg)

    @staticmethod
    def load(path: Optional[str] = None) -> "PipelineCfg":
        cfg = PipelineCfg()
        if path:
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            for section, values in raw.items():
                target = getattr(cfg, section, None)
                if target is None or not isinstance(values, dict):
                    continue
                for k, v in values.items():
                    if hasattr(target, k):
                        setattr(target, k, v)
        return cfg

    def dump(self) -> dict:
        d = asdict(self)
        return json.loads(json.dumps(d, default=str))


def load_user_profile(path: Optional[str], default_len: float) -> dict:
    """Personalized hand lengths: {'left': m, 'right': m}. See calibrate_user.py."""
    if path and Path(path).exists():
        with open(path) as f:
            prof = json.load(f)
        hands = prof.get("hands", {})
        return {
            "user_id": prof.get("user_id", "unknown"),
            "left": float(hands.get("left", {}).get("hand_length_m", default_len)),
            "right": float(hands.get("right", {}).get("hand_length_m", default_len)),
        }
    return {"user_id": "default", "left": default_len, "right": default_len}
