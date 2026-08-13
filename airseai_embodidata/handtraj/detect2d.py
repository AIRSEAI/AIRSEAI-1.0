"""Per-frame hand detection: 2D keypoints + a local (hand-rooted) 3D shape.

All backends emit the same `HandObs`, so the geometry stages downstream are
backend-agnostic. 21 keypoints in MediaPipe ordering:

    0 wrist; 1-4 thumb (CMC,MCP,IP,TIP); 5-8 index (MCP,PIP,DIP,TIP);
    9-12 middle; 13-16 ring; 17-20 pinky.

`kps_local` is a metric-ish 3D hand *shape* in a hand-rooted frame with
camera-aligned axes -- it fixes articulation but not scale/translation.
lift3d.py turns it into a metric camera-frame pose via personalized PnP.

Backends:
    * MediaPipeBackend -- CPU, pip-installable, runs anywhere (default).
    * HamerBackend     -- GPU SOTA (MANO mesh); integration hook + notes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from .config import DetectorCfg

log = logging.getLogger("handtraj.detect")

# Wrist->middle-fingertip polyline (pose-invariant hand length): 0-9-10-11-12
HAND_LENGTH_CHAIN = [0, 9, 10, 11, 12]
BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
         (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
         (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def polyline_length(kps3d: np.ndarray, chain=HAND_LENGTH_CHAIN) -> float:
    """Sum of bone lengths along a chain -- invariant to articulation."""
    pts = kps3d[chain]
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


@dataclass
class HandObs:
    side: str                     # 'left' | 'right' (anatomical, of the user)
    kps_2d: np.ndarray            # (21,2) pixels
    kps_local: np.ndarray         # (21,3) meters, hand-rooted, cam-aligned axes
    conf: float                   # detection/handedness confidence [0,1]
    extras: dict = field(default_factory=dict)


class DetectorBase:
    def detect(self, frame_bgr: np.ndarray, t: float) -> List[HandObs]:
        raise NotImplementedError

    def close(self):
        pass


# ----------------------------------------------------------------- MediaPipe
class MediaPipeBackend(DetectorBase):
    """mediapipe.solutions.hands wrapper.

    Notes that matter for correctness:
    * MediaPipe's handedness label assumes a *mirrored* (selfie) image. The
      EmbodiData rear camera is unmirrored, so we flip the label
      (cfg.flip_handedness=True).
    * `multi_hand_world_landmarks` are metric-ish 3D landmarks for an
      *average* hand, origin near the hand centroid, axes aligned with the
      camera. Perfect input for personalized-PnP lifting.
    """

    def __init__(self, cfg: DetectorCfg):
        import mediapipe as mp  # deferred import: heavy
        self._mp = mp
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=cfg.max_hands,
            model_complexity=cfg.model_complexity,
            min_detection_confidence=cfg.min_det_conf,
            min_tracking_confidence=cfg.min_track_conf,
        )
        self._flip = cfg.flip_handedness

    def detect(self, frame_bgr, t):
        import cv2
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self._hands.process(rgb)
        out: List[HandObs] = []
        if not res.multi_hand_landmarks:
            return out
        for lm, wlm, handed in zip(res.multi_hand_landmarks,
                                   res.multi_hand_world_landmarks,
                                   res.multi_handedness):
            cls = handed.classification[0]
            label = cls.label.lower()          # mediapipe's mirrored label
            if self._flip:
                label = "left" if label == "right" else "right"
            kps2d = np.array([[p.x * w, p.y * h] for p in lm.landmark])
            kps3d = np.array([[p.x, p.y, p.z] for p in wlm.landmark])
            out.append(HandObs(side=label, kps_2d=kps2d, kps_local=kps3d,
                               conf=float(cls.score)))
        return out

    def close(self):
        self._hands.close()


# -------------------------------------------------------------------- HaMeR
class HamerBackend(DetectorBase):
    """Hook for HaMeR (Pavlakos et al., CVPR 2024) / WiLoR-style backends.

    Integration recipe (see GUIDE.md section 6.3):
      1. Run a hand detector (e.g. WiLoR's detector or ViTDet) -> boxes+side.
      2. Run HaMeR on crops -> MANO params; extract 21 OpenPose-ordered
         joints; remap to MediaPipe ordering (identical for these 21).
      3. Subtract the wrist (or centroid), return as `kps_local` in meters.
         HaMeR joints are metric for the *mean* MANO shape -- exactly like
         MediaPipe world landmarks, personalization still applies.
      4. conf = detector score.
    The rest of the pipeline is unchanged -- that is the point of HandObs.
    """

    def __init__(self, cfg: DetectorCfg):
        raise ImportError(
            "HamerBackend is an integration hook. Install HaMeR "
            "(github.com/geopavlakos/hamer) in a GPU env and implement "
            "detect() per the class docstring / GUIDE.md 6.3.")


# ------------------------------------------------------------ cache support
def detections_to_npz(path: Path, all_obs: List[List[HandObs]]):
    """Cache per-frame detections so the (slow) detector runs once."""
    idx, sides, k2, k3, conf = [], [], [], [], []
    for i, frame_obs in enumerate(all_obs):
        for o in frame_obs:
            idx.append(i)
            sides.append(0 if o.side == "left" else 1)
            k2.append(o.kps_2d)
            k3.append(o.kps_local)
            conf.append(o.conf)
    np.savez_compressed(
        path, frame_idx=np.array(idx, dtype=np.int32),
        side=np.array(sides, dtype=np.int8),
        kps_2d=np.array(k2).reshape(-1, 21, 2) if k2 else np.zeros((0, 21, 2)),
        kps_local=np.array(k3).reshape(-1, 21, 3) if k3 else np.zeros((0, 21, 3)),
        conf=np.array(conf, dtype=np.float32))


def detections_from_npz(path: Path, n_frames: int) -> List[List[HandObs]]:
    d = np.load(path)
    out: List[List[HandObs]] = [[] for _ in range(n_frames)]
    for i in range(len(d["frame_idx"])):
        fi = int(d["frame_idx"][i])
        if fi < n_frames:
            out[fi].append(HandObs(
                side="left" if d["side"][i] == 0 else "right",
                kps_2d=d["kps_2d"][i], kps_local=d["kps_local"][i],
                conf=float(d["conf"][i])))
    return out


def make_detector(cfg: DetectorCfg) -> DetectorBase:
    if cfg.backend == "mediapipe":
        return MediaPipeBackend(cfg)
    if cfg.backend == "hamer":
        return HamerBackend(cfg)
    raise ValueError(f"Unknown backend {cfg.backend}")
