"""Synthetic end-to-end verification of the reverse-SLAM geometry.

Simulates what physically happens during capture, then checks the pipeline
inverts it:

  1. A hand moves along a known 3D trajectory in the world.
  2. A head-mounted camera bobs/rotates along its own known trajectory
     (stored in ARKit convention, like pose.csv).
  3. Each frame, hand keypoints are projected into the moving camera with
     known intrinsics + 0.7 px pixel noise -- these play the role of
     MediaPipe detections (kps_2d + hand-rooted kps_local).
  4. Pipeline stages (lift -> compose -> track -> RTS) recover the
     world-frame wrist trajectory. It must match ground truth to a few mm.

This isolates the geometry/composition/filtering math from the neural
detector, so a conventions bug (ARKit vs OpenCV, quaternion order, timestamp
misalignment) fails loudly here. Run:  python tests/test_synthetic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handtraj.config import PipelineCfg
from handtraj.detect2d import HandObs, polyline_length
from handtraj.egomotion import EgoMotion, R_ARKITCAM_CVCAM
from handtraj.ingest import Intrinsics
from handtraj.lift3d import Lifter
from handtraj.se3 import (PoseInterpolator, ate_rmse, make_T, quat_to_R,
                          R_to_quat, transform_points, T_inv)
from handtraj.sync import estimate_offset
from handtraj.tracking import HandTrack, associate
from handtraj.config import SyncCfg

rng = np.random.default_rng(7)

# ---------------------------------------------------------------- synthetic
# A hand-shaped 21-point model (meters, hand-rooted frame, MediaPipe order).
def make_hand_points():
    pts = np.zeros((21, 3))
    pts[0] = [0, 0, 0]                                    # wrist
    finger_x = {1: -0.035, 5: -0.02, 9: 0.0, 13: 0.02, 17: 0.038}
    finger_y0 = {1: 0.025, 5: 0.085, 9: 0.088, 13: 0.082, 17: 0.072}
    seg = {1: 0.031, 5: 0.028, 9: 0.031, 13: 0.028, 17: 0.022}
    for base in (1, 5, 9, 13, 17):
        for k in range(4):
            j = base + k
            pts[j] = [finger_x[base] * (1 + 0.15 * k),
                      finger_y0[base] + seg[base] * k,
                      -0.01 * k * (0.5 if base == 1 else 1.0)]
    return pts


def lookat_R_wc_cv(cam_pos, target, up=np.array([0., 1., 0.])):
    """World rotation of an OpenCV camera looking at `target`."""
    z = target - cam_pos
    z = z / np.linalg.norm(z)                # optical axis (cv +z forward)
    x = np.cross(z, up); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)       # columns = cam axes in world


def simulate(n_frames=240, fps=30.0, noise_px=0.7):
    K = np.array([[1400., 0, 960.], [0, 1400., 720.], [0, 0, 1.]])
    intr = Intrinsics(1400., 1400., 960., 720., 1920, 1440)
    hand_local = make_hand_points()
    L = polyline_length(hand_local)

    t = np.arange(n_frames) / fps
    # ground-truth wrist trajectory (a "wipe the table" style motion)
    wrist_gt = np.stack([
        0.18 * np.sin(2 * np.pi * 0.45 * t),
        1.05 + 0.05 * np.sin(2 * np.pi * 0.8 * t + 1.0),
        0.45 + 0.08 * np.cos(2 * np.pi * 0.3 * t)], axis=1)
    # hand orientation slowly varying
    hand_yaw = 0.4 * np.sin(2 * np.pi * 0.2 * t)

    # head trajectory: bobbing + looking at the workspace center
    head_pos = np.stack([
        0.03 * np.sin(2 * np.pi * 0.9 * t),
        1.55 + 0.02 * np.sin(2 * np.pi * 1.3 * t),
        0.95 + 0.03 * np.sin(2 * np.pi * 0.5 * t + 0.7)], axis=1)
    target = np.array([0.0, 1.0, 0.35])

    pose_hz = 60.0
    tp = np.arange(0, t[-1] + 1 / pose_hz, 1 / pose_hz)
    head_pos_p = np.stack([np.interp(tp, t, head_pos[:, k]) for k in range(3)], 1)

    Ts_arkit, obs_frames, kps_world_gt = [], [], []
    for i, ti in enumerate(tp):
        R_wc_cv = lookat_R_wc_cv(head_pos_p[i], target)
        # store in ARKit camera convention, as pose.csv would
        Ts_arkit.append(make_T(R_wc_cv @ R_ARKITCAM_CVCAM, head_pos_p[i]))
    Ts_arkit = np.stack(Ts_arkit)

    for i in range(n_frames):
        R_wc_cv = lookat_R_wc_cv(head_pos[i], target)
        T_wc = make_T(R_wc_cv, head_pos[i])
        cy, sy = np.cos(hand_yaw[i]), np.sin(hand_yaw[i])
        R_wh = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ \
            np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0.]])
        pts_w = hand_local @ R_wh.T + wrist_gt[i]
        kps_world_gt.append(pts_w)
        pts_c = transform_points(T_inv(T_wc), pts_w)
        uv = pts_c[:, :2] / pts_c[:, 2:3] * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
        uv += rng.normal(0, noise_px, uv.shape)
        # kps_local: what a perfect articulation net would output -- the hand
        # shape in a hand-rooted, camera-aligned frame (centered like MP).
        pts_c_rooted = pts_c - pts_c.mean(0)
        obs_frames.append([HandObs(side="right", kps_2d=uv,
                                   kps_local=pts_c_rooted, conf=0.95)])
    return (t, wrist_gt, np.array(kps_world_gt), tp, Ts_arkit, intr, L,
            obs_frames)


# --------------------------------------------------------------------- tests
def test_reverse_slam_recovery():
    (t, wrist_gt, kpsw_gt, tp, Ts_arkit, intr, L, obs_frames) = simulate()
    cfg = PipelineCfg()
    ego = EgoMotion(tp, Ts_arkit, video_rotation=0,
                    world_convention="arkit_yup")
    lifter = Lifter(cfg.lift, intr, {"left": L, "right": L})
    tracks = {s: HandTrack(s, len(t), cfg.track) for s in ("left", "right")}

    from handtraj.lift3d import pinch_aperture_m
    from handtraj.se3 import R_to_quat as r2q
    drop = set(rng.choice(len(t), size=12, replace=False))  # occlusions
    for i in range(len(t)):
        T_wc = ego.T_world_cam(t[i])
        assoc = associate([] if i in drop else obs_frames[i], tracks, i)
        for side in ("left", "right"):
            obs = assoc["assigned"][side]
            meas = None
            if obs is not None:
                p3 = lifter.lift(obs)
                assert p3 is not None, f"PnP failed at frame {i}"
                kw = transform_points(T_wc, p3.kps_cam)
                T_wh = T_wc @ p3.T_cam_hand
                meas = {"wrist_world": kw[0], "quat_world": r2q(T_wh[:3, :3]),
                        "kps_world": kw, "kps_cam": p3.kps_cam,
                        "kps_2d": p3.kps_2d, "wrist_cam": p3.wrist_cam,
                        "conf": p3.conf, "reproj_err": p3.reproj_err_px,
                        "kappa": p3.kappa,
                        "pinch_m": pinch_aperture_m(p3.kps_cam)}
            tracks[side].update(i, float(t[i]), 1 / 30.0, meas)
    for tr in tracks.values():
        tr.finalize(t)

    tr = tracks["right"]
    valid = np.array([f.valid for f in tr.frames])
    est = np.stack([f.wrist_world if f.valid else np.full(3, np.nan)
                    for f in tr.frames])
    cov = valid.mean()
    assert cov > 0.95, f"coverage {cov:.2%}"

    # NOTE kps_local is hand-*centroid*-rooted (like MediaPipe), while GT
    # wrist is landmark 0; both wrist positions are directly comparable.
    err = np.linalg.norm(est[valid] - wrist_gt[valid], axis=1)
    rmse_mm = 1000 * np.sqrt((err ** 2).mean())
    p95_mm = 1000 * np.percentile(err, 95)
    print(f"[reverse-slam] coverage {cov:.1%}  wrist RMSE {rmse_mm:.2f} mm  "
          f"p95 {p95_mm:.2f} mm  (0.7 px noise, 12 dropped frames)")
    assert rmse_mm < 8.0, f"wrist RMSE {rmse_mm:.1f} mm too high"

    # wrong hand size -> proportional depth bias (shows why personalization
    # matters): simulate a user whose hand is 10% larger than assumed
    lifter_bad = Lifter(cfg.lift, intr, {"right": L * 0.9, "left": L * 0.9})
    p3 = lifter_bad.lift(obs_frames[0][0])
    z_bad = p3.wrist_cam[2]
    p3ok = Lifter(cfg.lift, intr, {"right": L, "left": L}).lift(obs_frames[0][0])
    z_ok = p3ok.wrist_cam[2]
    bias = abs(z_bad - z_ok) / z_ok
    print(f"[personalization] 10% hand-size error -> {100 * bias:.1f}% "
          f"depth bias ({1000 * abs(z_bad - z_ok):.0f} mm at "
          f"{z_ok:.2f} m)")
    assert 0.06 < bias < 0.14


def test_sync_offset_recovery():
    (t, _, _, tp, Ts_arkit, *_rest) = simulate(n_frames=420)
    # synthesize gyro from the pose track itself, shifted by a known offset
    from handtraj.sync import pose_angular_speed
    tm, w = pose_angular_speed(tp, Ts_arkit)
    true_offset = 0.12
    imu_t = np.arange(tm[0], tm[-1], 1 / 200.0)
    wmag = np.interp(imu_t - true_offset, tm, w)  # IMU leads pose by 120 ms
    gyro = np.zeros((len(imu_t), 3))
    gyro[:, 0] = wmag + rng.normal(0, 0.02, len(imu_t))
    res = estimate_offset(imu_t, gyro, tp, Ts_arkit, SyncCfg())
    print(f"[sync] true offset -120.0 ms, recovered "
          f"{1000 * res.offset_s:+.1f} ms (corr {res.peak_corr:.2f})")
    assert abs(res.offset_s - (-true_offset)) < 0.02


def test_pose_interpolation():
    ts = np.array([0.0, 1.0])
    Ta = np.eye(4)
    Rb = quat_to_R(R_to_quat(
        np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.]])))   # 90 deg about z
    Tb = make_T(Rb, [1.0, 0, 0])
    interp = PoseInterpolator(ts, np.stack([Ta, Tb]))
    Tm = interp.query(0.5)
    assert np.allclose(Tm[:3, 3], [0.5, 0, 0], atol=1e-9)
    ang = np.degrees(np.arccos((np.trace(Tm[:3, :3]) - 1) / 2))
    assert abs(ang - 45.0) < 1e-6
    print("[interp] SE(3) interpolation ok (45.0 deg at midpoint)")


def test_umeyama():
    src = rng.normal(size=(50, 3))
    Rz = quat_to_R(np.array([0, 0, np.sin(0.4), np.cos(0.4)]))
    dst = src @ Rz.T + [0.3, -0.2, 1.0]
    rmse, _ = ate_rmse(src, dst)
    assert rmse < 1e-9
    print("[umeyama] rigid alignment ok")


if __name__ == "__main__":
    test_pose_interpolation()
    test_umeyama()
    test_sync_offset_recovery()
    test_reverse_slam_recovery()
    print("\nALL SYNTHETIC TESTS PASSED")
