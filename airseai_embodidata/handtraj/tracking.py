"""Temporal layer: left/right association, outlier gating, Kalman filtering,
RTS smoothing, gap filling, and light keypoint smoothing.

Per-frame monocular estimates are noisy and intermittent (occlusion, motion
blur, hands leaving the field of view). Physics is the missing constraint:
hands obey continuous dynamics. We enforce it with a constant-velocity
Kalman filter per hand on the *world-frame* wrist position -- filtering must
happen after ego-motion compensation, otherwise head motion aliases into
"hand velocity" -- followed by an offline Rauch-Tung-Striebel smoother
(post-processing means we get the non-causal smoother for free).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ._rot import Rotation, Slerp
from .config import TrackCfg
from .se3 import fix_quat_continuity

log = logging.getLogger("handtraj.tracking")


# ------------------------------------------------------------ Kalman filter
class ConstVelKF3D:
    """State [p(3), v(3)]; measurement p. Stores history for RTS smoothing."""

    def __init__(self, cfg: TrackCfg):
        self.cfg = cfg
        self.x: Optional[np.ndarray] = None
        self.P: Optional[np.ndarray] = None
        # histories (one entry per processed frame)
        self.xs, self.Ps, self.x_preds, self.P_preds, self.Fs = [], [], [], [], []

    def _mats(self, dt: float):
        F = np.eye(6)
        F[:3, 3:] = np.eye(3) * dt
        q = self.cfg.sigma_accel ** 2
        # white-noise-acceleration discretization
        Q = np.zeros((6, 6))
        Q[:3, :3] = np.eye(3) * (dt ** 4) / 4 * q
        Q[:3, 3:] = Q[3:, :3] = np.eye(3) * (dt ** 3) / 2 * q
        Q[3:, 3:] = np.eye(3) * (dt ** 2) * q
        return F, Q

    def init(self, p: np.ndarray):
        self.x = np.concatenate([p, np.zeros(3)])
        self.P = np.diag([1e-4] * 3 + [1.0] * 3)

    def step(self, dt: float, z: Optional[np.ndarray]) -> dict:
        """Predict (+update if z is not None and passes the gate)."""
        F, Q = self._mats(max(dt, 1e-4))
        x_pred = F @ self.x
        P_pred = F @ self.P @ F.T + Q
        H = np.zeros((3, 6)); H[:3, :3] = np.eye(3)
        R = np.eye(3) * self.cfg.sigma_meas ** 2
        accepted = False
        maha = np.nan
        if z is not None:
            S = H @ P_pred @ H.T + R
            innov = z - H @ x_pred
            maha = float(innov @ np.linalg.solve(S, innov))
            if maha < self.cfg.gate_chi2:
                Kg = P_pred @ H.T @ np.linalg.inv(S)
                self.x = x_pred + Kg @ innov
                self.P = (np.eye(6) - Kg @ H) @ P_pred
                accepted = True
        if not accepted:
            self.x, self.P = x_pred, P_pred
        self.xs.append(self.x.copy()); self.Ps.append(self.P.copy())
        self.x_preds.append(x_pred); self.P_preds.append(P_pred)
        self.Fs.append(F)
        return {"accepted": accepted, "mahalanobis": maha}

    def rts_smooth(self) -> np.ndarray:
        """Backward pass; returns smoothed states (N,6)."""
        n = len(self.xs)
        xs = np.array(self.xs); Ps = np.array(self.Ps)
        if n == 0:
            return xs
        x_s = xs.copy(); P_s = Ps.copy()
        for k in range(n - 2, -1, -1):
            F = self.Fs[k + 1]
            P_pred = self.P_preds[k + 1]
            C = Ps[k] @ F.T @ np.linalg.inv(P_pred)
            x_s[k] = xs[k] + C @ (x_s[k + 1] - self.x_preds[k + 1])
            P_s[k] = Ps[k] + C @ (P_s[k + 1] - P_pred) @ C.T
        return x_s


# --------------------------------------------------------- One-Euro filter
class OneEuro:
    """Adaptive low-pass for the 21 world keypoints (lag-light smoothing)."""

    def __init__(self, min_cutoff=1.5, beta=0.3, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, t: float, x: np.ndarray) -> np.ndarray:
        if self.x_prev is None:
            self.x_prev, self.dx_prev, self.t_prev = x, np.zeros_like(x), t
            return x
        dt = max(t - self.t_prev, 1e-4)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * np.linalg.norm(dx_hat, axis=-1,
                                                              keepdims=True)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


# ----------------------------------------------------------------- tracks
@dataclass
class TrackFrame:
    valid: bool = False
    source: str = "missing"       # detected | filled | missing
    conf: float = 0.0
    reproj_err: float = np.nan
    wrist_world: np.ndarray = None
    quat_world: np.ndarray = None            # hand orientation (x,y,z,w)
    kps_world: np.ndarray = None             # (21,3)
    kps_cam: np.ndarray = None
    kps_2d: np.ndarray = None
    wrist_cam: np.ndarray = None
    kappa: float = np.nan
    pinch_m: float = np.nan


class HandTrack:
    """One anatomical hand over the episode."""

    def __init__(self, side: str, n_frames: int, cfg: TrackCfg):
        self.side = side
        self.cfg = cfg
        self.frames: List[TrackFrame] = [TrackFrame() for _ in range(n_frames)]
        self.kf = ConstVelKF3D(cfg)
        self._kf_active = False
        self._last_seen = -10 ** 9
        self._kf_frame_ids: List[int] = []
        self._oneeuro = OneEuro(cfg.oneeuro_min_cutoff, cfg.oneeuro_beta)
        self.n_outliers = 0
        self.n_reinits = 0

    def update(self, idx: int, t: float, dt: float, meas: Optional[dict]):
        """meas: dict with wrist_world, quat_world, kps_world/cam/2d, ..."""
        fr = self.frames[idx]
        z = None if meas is None else meas["wrist_world"]

        if z is not None and not self._kf_active:
            self.kf.init(z)
            self._kf_active = True
        elif z is not None and idx - self._last_seen > self.cfg.reinit_gap_frames:
            # stale velocity after a long gap does more harm than good
            self.kf = ConstVelKF3D(self.cfg)
            self.kf.init(z)
            self._kf_frame_ids = []
            self.n_reinits += 1

        if self._kf_active:
            info = self.kf.step(dt, z)
            self._kf_frame_ids.append(idx)
            if z is not None and not info["accepted"]:
                self.n_outliers += 1
                meas = None          # treat as miss; KF already predicted
                z = None

        if meas is not None:
            fr.valid = True
            fr.source = "detected"
            fr.conf = meas["conf"]
            fr.reproj_err = meas["reproj_err"]
            fr.quat_world = meas["quat_world"]
            fr.kps_world = self._oneeuro(t, meas["kps_world"])
            fr.kps_cam = meas["kps_cam"]
            fr.kps_2d = meas["kps_2d"]
            fr.wrist_cam = meas["wrist_cam"]
            fr.kappa = meas["kappa"]
            fr.pinch_m = meas["pinch_m"]
            fr.wrist_world = fr.kps_world[0]
            self._last_seen = idx

    def finalize(self, frame_times: np.ndarray):
        """RTS-smooth wrist, fill short gaps, smooth orientation."""
        if not self._kf_frame_ids:
            return
        x_s = self.kf.rts_smooth()
        for state, idx in zip(x_s, self._kf_frame_ids):
            fr = self.frames[idx]
            gap = self._gap_length(idx)
            if fr.source == "detected":
                fr.wrist_world = state[:3]
            elif gap is not None and gap <= self.cfg.max_fill_gap_frames:
                fr.valid = True
                fr.source = "filled"
                fr.wrist_world = state[:3]
        self._smooth_orientation(frame_times)

    def _gap_length(self, idx: int) -> Optional[int]:
        """Length of the missing-run containing idx, bounded by detections."""
        lo = idx
        while lo > 0 and self.frames[lo - 1].source not in ("detected",):
            lo -= 1
            if idx - lo > 10 * self.cfg.max_fill_gap_frames:
                return None
        hi = idx
        n = len(self.frames)
        while hi < n - 1 and self.frames[hi + 1].source not in ("detected",):
            hi += 1
            if hi - idx > 10 * self.cfg.max_fill_gap_frames:
                return None
        if lo == 0 or hi == n - 1:
            return None              # unbounded gap (start/end): don't fill
        return hi - lo + 1

    def _smooth_orientation(self, frame_times):
        idxs = [i for i, f in enumerate(self.frames)
                if f.source == "detected" and f.quat_world is not None]
        if len(idxs) < 2:
            return
        qs = fix_quat_continuity(np.stack(
            [self.frames[i].quat_world for i in idxs]))
        # SLERP-interpolate orientation onto filled frames
        slerp = Slerp(frame_times[idxs], Rotation.from_quat(qs))
        for i, f in enumerate(self.frames):
            if f.valid:
                tq = float(np.clip(frame_times[i], frame_times[idxs[0]],
                                   frame_times[idxs[-1]]))
                f.quat_world = slerp(tq).as_quat()


# ------------------------------------------------------------- association
def _last_wrist_2d(track: HandTrack, idx: int, horizon: int = 15):
    for j in range(idx - 1, max(-1, idx - 1 - horizon), -1):
        f = track.frames[j]
        if f.source == "detected" and f.kps_2d is not None:
            return f.kps_2d[0]
    return None


def associate(obs_list, tracks: Dict[str, HandTrack], idx: int) -> dict:
    """Resolve per-frame detections to anatomical sides.

    MediaPipe handedness is usually right; failure modes are (a) two
    detections with the same label, (b) L/R flips during crossing or blur.
    Duplicates are re-assigned to the empty side when ambiguous; a swap test
    against each track's recent 2D wrist position undoes flagrant flips.
    Returns {'left': obs|None, 'right': obs|None} plus a flip count for QA.
    """
    out: Dict[str, Optional[object]] = {"left": None, "right": None}
    flips = 0
    by_side: Dict[str, list] = {"left": [], "right": []}
    for o in obs_list:
        by_side[o.side].append(o)
    for side in ("left", "right"):
        cands = sorted(by_side[side], key=lambda o: -o.conf)
        if not cands:
            continue
        out[side] = cands[0]
        # duplicate labels: move the runner-up to the empty side if plausible
        if len(cands) > 1:
            other = "left" if side == "right" else "right"
            if out[other] is None and cands[1].conf < 0.9:
                out[other] = cands[1]
                flips += 1
    # swap test vs. recent track positions (catches label flips)
    pl, pr = (_last_wrist_2d(tracks["left"], idx),
              _last_wrist_2d(tracks["right"], idx))
    if out["left"] is not None and out["right"] is not None \
            and pl is not None and pr is not None:
        d = np.linalg.norm
        keep = d(out["left"].kps_2d[0] - pl) + d(out["right"].kps_2d[0] - pr)
        swap = d(out["left"].kps_2d[0] - pr) + d(out["right"].kps_2d[0] - pl)
        if swap + 40.0 < keep:      # 40 px hysteresis: don't thrash
            out["left"], out["right"] = out["right"], out["left"]
            flips += 1
    return {"assigned": out, "flips": flips}
