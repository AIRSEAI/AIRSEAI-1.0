"""Time synchronization and capture-protocol checks.

pose.csv and imu.csv are stamped by the same iOS host clock, so they should
already agree -- `estimate_offset` verifies that (a nonzero result flags an
export bug). The video is different: if the app did not log per-frame
timestamps, frame times must be *derived* (t_i = t0 + i/fps) and t0 is
unknown. `estimate_video_start` recovers t0 by correlating the video's
optical-flow angular speed against |gyro| -- rotation is the one signal both
sensors observe directly, no calibration target needed (classic camera-IMU
sync a la Mair et al.).

`stationary_check` verifies the capture protocol's 3-second still segments
at episode start/end.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from ._rot import Rotation
from .config import SyncCfg

log = logging.getLogger("handtraj.sync")


def pose_angular_speed(pose_t: np.ndarray, Ts: np.ndarray):
    """Angular speed (rad/s) of the camera from consecutive pose rotations."""
    Rs = Rotation.from_matrix(Ts[:, :3, :3])
    dR = (Rs[:-1].inv() * Rs[1:]).magnitude()          # geodesic angle
    dt = np.diff(pose_t)
    dt[dt <= 0] = np.nan
    w = dR / dt
    t_mid = 0.5 * (pose_t[:-1] + pose_t[1:])
    good = np.isfinite(w)
    return t_mid[good], w[good]


def _resample(t, x, grid):
    return np.interp(grid, t, x, left=np.nan, right=np.nan)


@dataclass
class SyncResult:
    offset_s: float     # lag maximizing corr(gyro(t), pose_rate(t + offset));
    peak_corr: float    # ~0 when both streams share a clock (expected here).
    reliable: bool      # subtract offset from pose stamps -> IMU clock.


def estimate_offset(imu_t, gyro, pose_t, Ts, cfg: SyncCfg) -> SyncResult:
    """Consistency check between the pose and IMU streams (see docstring)."""
    tg, wg = imu_t, np.linalg.norm(gyro, axis=1)
    tp, wp = pose_angular_speed(pose_t, Ts)
    t0 = max(tg[0], tp[0])
    t1 = min(tg[-1], tp[-1])
    if t1 - t0 < 2.0:
        return SyncResult(0.0, 0.0, False)
    dt = 1.0 / cfg.resample_hz
    grid = np.arange(t0, t1, dt)
    a = _resample(tg, wg, grid)
    b = _resample(tp, wp, grid)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m] - np.nanmean(a[m]), b[m] - np.nanmean(b[m])
    if len(a) < 10 or a.std() < 1e-6 or b.std() < 1e-6:
        return SyncResult(0.0, 0.0, False)
    max_lag = int(cfg.max_offset_s / dt)
    lags = np.arange(-max_lag, max_lag + 1)
    corr = np.array([
        np.dot(a[max(0, -l):len(a) - max(0, l)],
               b[max(0, l):len(b) - max(0, -l)])
        / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-12)
        for l in lags
    ])
    best = int(np.argmax(corr))
    offset = float(lags[best] * dt)   # shift pose stream by +offset to align
    peak = float(corr[best])
    reliable = peak > 0.4
    log.info("Sync offset %.1f ms (corr %.2f, %s)", offset * 1e3, peak,
             "reliable" if reliable else "LOW CONFIDENCE - keeping 0")
    return SyncResult(offset if reliable else 0.0, peak, reliable)


def visual_angular_speed(video_path, fps: float, max_frames: int = 2400,
                         target_width: int = 320):
    """Approximate camera angular speed (rad/s) per frame from sparse
    Lucas-Kanade optical flow: for a rotating camera, median pixel flow
    ~= f * omega, so omega ~= flow_px / f_scaled. Only relative shape
    matters for correlation, so the small-translation approximation is fine.
    Returns (t_video_relative, omega)."""
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    ok, prev = cap.read()
    if not ok:
        cap.release()
        return np.array([]), np.array([])
    scale = target_width / prev.shape[1]
    size = (target_width, int(prev.shape[0] * scale))
    f_scaled = 0.73 * target_width          # heuristic focal at this scale
    prev_g = cv2.cvtColor(cv2.resize(prev, size), cv2.COLOR_BGR2GRAY)
    ts, om = [], []
    i = 0
    while i < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(frame, size), cv2.COLOR_BGR2GRAY)
        pts = cv2.goodFeaturesToTrack(prev_g, maxCorners=120,
                                      qualityLevel=0.01, minDistance=8)
        if pts is not None and len(pts) >= 8:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_g, g, pts, None)
            good = st.reshape(-1).astype(bool)
            if good.sum() >= 8:
                flow = np.linalg.norm((nxt - pts).reshape(-1, 2)[good], axis=1)
                om.append(np.median(flow) * fps / f_scaled)
                ts.append((i + 0.5) / fps)
        prev_g = g
        i += 1
    cap.release()
    return np.asarray(ts), np.asarray(om)


@dataclass
class VideoStartResult:
    t0: float            # video start time on the host/IMU clock
    peak_corr: float
    reliable: bool


def estimate_video_start(video_path, fps, imu_t, gyro, cfg: SyncCfg,
                         search_pad_s: float = 5.0) -> VideoStartResult:
    """Recover the video's start time t0 on the IMU clock:
    argmax_t0  corr( omega_visual(t - t0), |gyro|(t) ).
    Fallback for episodes without per-frame timestamps."""
    tv, ov = visual_angular_speed(video_path, fps)
    if len(tv) < int(2 * fps):
        return VideoStartResult(float(imu_t[0]), 0.0, False)
    wg = np.linalg.norm(gyro, axis=1)
    ov_z = (ov - ov.mean()) / (ov.std() + 1e-9)
    best_t0, best_c = float(imu_t[0]), -np.inf
    for t0 in np.arange(imu_t[0] - search_pad_s,
                        imu_t[-1] - tv[-1] + search_pad_s, 0.005):
        a = np.interp(tv + t0, imu_t, wg, left=np.nan, right=np.nan)
        m = np.isfinite(a)
        if m.sum() < fps:
            continue
        az = (a[m] - a[m].mean()) / (a[m].std() + 1e-9)
        c = float(np.mean(az * ov_z[m]))
        if c > best_c:
            best_c, best_t0 = c, float(t0)
    reliable = best_c > 0.5
    log.info("Video start on IMU clock: %.3f s (corr %.2f, %s)", best_t0,
             best_c, "reliable" if reliable else "LOW CONFIDENCE")
    return VideoStartResult(best_t0, best_c, reliable)


def stationary_check(imu_t, gyro, cfg: SyncCfg) -> dict:
    """Protocol check: device still for ~3 s at episode start and end."""
    out = {}
    for name, sel in (("start", imu_t < imu_t[0] + cfg.stationary_window_s),
                      ("end", imu_t > imu_t[-1] - cfg.stationary_window_s)):
        w = np.linalg.norm(gyro[sel], axis=1)
        rms = float(np.sqrt((w ** 2).mean())) if sel.any() else float("nan")
        out[name] = {"gyro_rms": rms,
                     "still": bool(rms < cfg.stationary_gyro_thresh)}
    return out
