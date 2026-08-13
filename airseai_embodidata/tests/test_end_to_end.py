"""Integration test: a synthetic episode written to disk in the EmbodiData
release layout, processed by the real `run_episode` code path (ingest ->
sync -> lift -> compose -> track -> export -> QA), with a fake detector
standing in for MediaPipe. Verifies files land where the release spec
expects them and the recovered trajectory matches ground truth.

Run:  python tests/test_end_to_end.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handtraj.config import PipelineCfg
from handtraj.detect2d import DetectorBase
from handtraj.eval_gt import evaluate
from handtraj.pipeline import run_episode
from test_synthetic import simulate


class FakeDetector(DetectorBase):
    """Replays precomputed synthetic observations (perfect articulation net)."""

    def __init__(self, obs_frames):
        self.obs_frames = obs_frames
        self._i = 0

    def detect(self, frame_bgr, t):
        obs = self.obs_frames[self._i] if self._i < len(self.obs_frames) else []
        self._i += 1
        return obs


def build_episode(tmp: Path):
    (t, wrist_gt, kpsw_gt, tp, Ts_arkit, intr, L, obs_frames) = simulate(
        n_frames=180)
    ep = tmp / "E_SYNTH"
    ep.mkdir(parents=True)

    # --- video: draw the hand's 2D keypoints so the overlay is meaningful
    vw = cv2.VideoWriter(str(ep / "video.mp4"),
                         cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (1920, 1440))
    if not vw.isOpened():
        vw = cv2.VideoWriter(str(ep / "video.avi"),
                             cv2.VideoWriter_fourcc(*"MJPG"), 30.0,
                             (1920, 1440))
    for i in range(len(t)):
        img = np.full((1440, 1920, 3), 40, np.uint8)
        for u, v in obs_frames[i][0].kps_2d:
            if 0 <= int(v) < 1440 and 0 <= int(u) < 1920:
                cv2.circle(img, (int(u), int(v)), 4, (0, 200, 255), -1)
        vw.write(img)
    vw.release()
    mp4 = ep / "video.mp4"
    if mp4.exists():
        cap = cv2.VideoCapture(str(mp4))
        ok, _ = cap.read()
        cap.release()
        if not ok:
            mp4.unlink()  # container unusable here; fall back handled above

    # --- pose.csv (ARKit convention, 60 Hz), imu.csv (200 Hz), frames.csv
    with open(ep / "pose.csv", "w") as f:
        f.write("timestamp,tx,ty,tz,qx,qy,qz,qw\n")
        from handtraj.se3 import R_to_quat
        for ti, T in zip(tp, Ts_arkit):
            q = R_to_quat(T[:3, :3])
            f.write(f"{ti:.6f},{T[0,3]:.6f},{T[1,3]:.6f},{T[2,3]:.6f},"
                    f"{q[0]:.7f},{q[1]:.7f},{q[2]:.7f},{q[3]:.7f}\n")

    rng = np.random.default_rng(3)
    imu_t = np.arange(-3.0, t[-1] + 3.0, 1 / 200.0)   # includes still tails
    with open(ep / "imu.csv", "w") as f:
        f.write("timestamp,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z\n")
        from handtraj.se3 import quat_to_R  # noqa: F401
        # gyro: from pose finite differences inside [0, T]; still outside
        from handtraj._rot import Rotation
        Rs = [T[:3, :3] for T in Ts_arkit]
        for ti in imu_t:
            if 0.0 <= ti <= tp[-1] - 1 / 60:
                k = min(int(ti * 60), len(Rs) - 2)
                q = Rotation.from_matrix(Rs[k].T @ Rs[k + 1]).as_quat()
                ang = 2 * np.arctan2(np.linalg.norm(q[:3]), abs(q[3]))
                axis = q[:3] / (np.linalg.norm(q[:3]) + 1e-12)
                g = axis * ang * 60.0
            else:
                g = np.zeros(3)
            g = g + rng.normal(0, 0.01, 3)
            a = np.array([0, -9.81, 0]) + rng.normal(0, 0.05, 3)
            f.write(f"{ti:.6f},{a[0]:.4f},{a[1]:.4f},{a[2]:.4f},"
                    f"{g[0]:.5f},{g[1]:.5f},{g[2]:.5f}\n")

    with open(ep / "frames.csv", "w") as f:
        f.write("frame,timestamp\n")
        for i, ti in enumerate(t):
            f.write(f"{i},{ti:.6f}\n")

    calib = ep / "calibration"
    calib.mkdir()
    (calib / "camera.json").write_text(json.dumps(
        {"fx": intr.fx, "fy": intr.fy, "cx": intr.cx, "cy": intr.cy,
         "width": intr.width, "height": intr.height}))
    (ep / "meta.json").write_text(json.dumps(
        {"episode_id": "E_SYNTH", "task_family": "synthetic"}))

    profile = tmp / "profile.json"
    profile.write_text(json.dumps(
        {"user_id": "synth",
         "hands": {"left": {"hand_length_m": L},
                   "right": {"hand_length_m": L}}}))
    return ep, profile, t, wrist_gt, obs_frames


def main():
    tmp = Path(tempfile.mkdtemp(prefix="embodidata_e2e_"))
    try:
        ep, profile, t, wrist_gt, obs_frames = build_episode(tmp)
        cfg = PipelineCfg.load(None)
        cfg.lift.user_profile = str(profile)
        cfg.export.plot = True
        res = run_episode(ep, cfg, detector=FakeDetector(obs_frames))

        out = ep / "hand_annotation"
        expected = ["hands.csv", "hands.npz", "hand_annotation.json",
                    "detections.npz"]
        for name in expected:
            assert (out / name).exists(), f"missing {name}"
        print("[files]", ", ".join(p.name for p in sorted(out.iterdir())))

        rep = res.qa_report
        print(f"[qa] verdict={rep['verdict']} "
              f"right coverage={rep['hands']['right']['coverage']:.0%} "
              f"reproj={rep['hands']['right']['mean_reproj_px']:.2f}px "
              f"warnings={rep['warnings']}")
        assert rep["hands"]["right"]["coverage"] > 0.95

        d = np.load(out / "hands.npz")
        valid = d["r_valid"]
        ate = evaluate(d["frame_times"][valid],
                       d["r_wrist_world"][valid], t, wrist_gt)
        print(f"[traj] ATE rmse {ate['ate_rmse_cm']*10:.2f} mm, "
              f"median {ate['ate_median_cm']*10:.2f} mm, "
              f"time offset {1000*ate['time_offset_s']:.0f} ms")
        assert ate["ate_rmse_cm"] < 1.0     # < 1 cm through the full stack

        # raw (unaligned) error too -- no hidden frame mismatch
        raw = np.linalg.norm(d["r_wrist_world"][valid] - wrist_gt[valid],
                             axis=1)
        print(f"[traj] raw world-frame RMSE "
              f"{1000*np.sqrt((raw**2).mean()):.2f} mm")
        assert np.sqrt((raw ** 2).mean()) < 0.01
        print("\nEND-TO-END TEST PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
