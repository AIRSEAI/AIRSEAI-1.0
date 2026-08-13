"""Metric 3D lift: hand pose in the *camera* frame from one RGB frame.

This is where the monocular scale ambiguity is broken. A single image
constrains hand depth only through apparent size, so knowing the *actual*
hand size is equivalent to knowing depth:

    z_error / z  ~=  hand_size_error / hand_size

Adult hand lengths span roughly 16-21 cm (+-13%), i.e. up to ~7 cm depth
error at 50 cm with an "average hand" assumption. Personalized calibration
(calibrate_user.py) removes this bias -- and doubles as the "individualized
data collection" feature: each user's profile makes *their* data metric.

Method (per detection):
  1. Scale the backend's hand-rooted 3D shape so its wrist->middle-fingertip
     bone chain equals the user's measured length:  kappa = L_user / L_model.
  2. solvePnP( scaled_shape, kps_2d, K )  ->  T_cam_hand  (OpenCV frame).
  3. Gates: reprojection error, plausible depth range.
  4. Optional: refine translation against a metric depth map (iPhone Pro
     LiDAR sceneDepth) -- then the hand-size prior only sets orientation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from .config import LiftCfg
from .detect2d import HandObs, polyline_length
from .ingest import Intrinsics
from .se3 import make_T

log = logging.getLogger("handtraj.lift")

WRIST = 0
MIDDLE_MCP = 9


@dataclass
class HandPose3D:
    side: str
    T_cam_hand: np.ndarray        # (4,4): hand-rooted frame -> OpenCV camera
    kps_cam: np.ndarray           # (21,3) meters, OpenCV camera frame
    kps_2d: np.ndarray            # (21,2) pixels (input, for QA/overlay)
    conf: float
    reproj_err_px: float
    kappa: float                  # personalization scale actually applied
    extras: dict = field(default_factory=dict)

    @property
    def wrist_cam(self) -> np.ndarray:
        return self.kps_cam[WRIST]


class Lifter:
    def __init__(self, cfg: LiftCfg, intr: Intrinsics, user_lengths: dict):
        self.cfg = cfg
        self.K = intr.K
        self.dist = np.asarray(intr.dist, dtype=float)
        self.img_wh = (intr.width, intr.height)
        self.user_lengths = user_lengths       # {'left': m, 'right': m}
        self._prev_rt = {}                     # side -> (rvec, tvec) warm start

    def lift(self, obs: HandObs, depth: Optional[np.ndarray] = None
             ) -> Optional[HandPose3D]:
        L_model = polyline_length(obs.kps_local)
        if L_model < 1e-4:
            return None
        kappa = self.user_lengths.get(obs.side, 0.185) / L_model
        obj = (obs.kps_local * kappa).astype(np.float64)
        img = obs.kps_2d.astype(np.float64).reshape(-1, 1, 2)

        prev = self._prev_rt.get(obs.side)
        try:
            if prev is not None:
                ok, rvec, tvec = cv2.solvePnP(
                    obj, img, self.K, self.dist, rvec=prev[0].copy(),
                    tvec=prev[1].copy(), useExtrinsicGuess=True,
                    flags=cv2.SOLVEPNP_ITERATIVE)
            else:
                ok, rvec, tvec = cv2.solvePnP(
                    obj, img, self.K, self.dist, flags=cv2.SOLVEPNP_SQPNP)
                if ok:  # refine
                    rvec, tvec = cv2.solvePnPRefineLM(
                        obj, img, self.K, self.dist, rvec, tvec)
        except cv2.error as e:
            log.debug("PnP failed: %s", e)
            return None
        if not ok:
            return None

        proj, _ = cv2.projectPoints(obj, rvec, tvec, self.K, self.dist)
        reproj = float(np.linalg.norm(
            proj.reshape(-1, 2) - obs.kps_2d, axis=1).mean())
        R, _ = cv2.Rodrigues(rvec)
        t = tvec.reshape(3)
        kps_cam = obj @ R.T + t

        # ---- optional metric-depth refinement (LiDAR) ----------------------
        if depth is not None:
            s = self._depth_scale(kps_cam, obs.kps_2d, depth)
            if s is not None:
                t = t * s
                kps_cam = kps_cam * s
                # NB: uniform scaling of a rigid PnP solution is a first-order
                # correction; good because hand extent << hand distance.

        z = kps_cam[WRIST][2]
        zmin, zmax = self.cfg.z_range_m
        if reproj > self.cfg.reproj_thresh_px or not (zmin < z < zmax):
            self._prev_rt.pop(obs.side, None)
            return None
        self._prev_rt[obs.side] = (rvec, tvec)

        return HandPose3D(side=obs.side, T_cam_hand=make_T(R, t),
                          kps_cam=kps_cam, kps_2d=obs.kps_2d,
                          conf=obs.conf, reproj_err_px=reproj, kappa=kappa)

    def _depth_scale(self, kps_cam, kps_2d, depth) -> Optional[float]:
        """Median ratio of measured to PnP depth at rigid palm landmarks.
        Depth maps (e.g. ARKit sceneDepth, 256x192) may be lower-res than the
        video; sample with proportional coordinates."""
        Hd, Wd = depth.shape[:2]
        Wi, Hi = self.img_wh
        ratios = []
        for j in (WRIST, MIDDLE_MCP, 5, 13, 17):        # palm: quasi-rigid
            u, v = kps_2d[j]
            us = int(round(u * Wd / Wi))
            vs = int(round(v * Hd / Hi))
            if 0 <= vs < Hd and 0 <= us < Wd:
                d = float(depth[vs, us]) * self.cfg.depth_scale
                zp = float(kps_cam[j][2])
                if 0.1 < d < 3.0 and zp > 0.05:
                    ratios.append(d / zp)
        if len(ratios) < 2:
            return None
        s = float(np.median(ratios))
        return s if 0.5 < s < 2.0 else None


def pinch_aperture_m(kps_cam: np.ndarray) -> float:
    """Thumb-tip to index-tip distance -- a UMI-style gripper-width signal
    for downstream policy learning."""
    return float(np.linalg.norm(kps_cam[4] - kps_cam[8]))
