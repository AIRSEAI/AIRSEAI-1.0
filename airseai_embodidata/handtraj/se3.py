"""SE(3) utilities: quaternions, rigid transforms, interpolation, alignment.

Conventions
-----------
* Quaternions are (x, y, z, w) -- same as ARKit and scipy.
* A pose T_A_B is a 4x4 matrix mapping points expressed in frame B to frame A:
      p_A = T_A_B @ p_B
* "T_world_cam" therefore maps camera-frame points into the world frame,
  i.e. it *is* the camera pose in the world (ARKit's `camera.transform`).
"""
from __future__ import annotations

import numpy as np

from ._rot import Rotation, Slerp   # scipy if installed, numpy fallback else


# ---------------------------------------------------------------- basic ops
def make_T(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(t).reshape(3)
    return T


def T_inv(T: np.ndarray) -> np.ndarray:
    R = T[:3, :3]
    t = T[:3, 3]
    Ti = np.eye(4)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ t
    return Ti


def transform_points(T: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply 4x4 transform to (N,3) points."""
    pts = np.asarray(pts)
    return pts @ T[:3, :3].T + T[:3, 3]


def quat_to_R(q: np.ndarray) -> np.ndarray:
    return Rotation.from_quat(np.asarray(q, dtype=float)).as_matrix()


def R_to_quat(R: np.ndarray) -> np.ndarray:
    return Rotation.from_matrix(R).as_quat()


def pose_from_txyz_quat(t: np.ndarray, q: np.ndarray) -> np.ndarray:
    return make_T(quat_to_R(q), t)


def fix_quat_continuity(qs: np.ndarray) -> np.ndarray:
    """Flip quaternion signs so consecutive quats live on the same hemisphere
    (q and -q encode the same rotation; sign flips break interpolation)."""
    qs = np.array(qs, dtype=float, copy=True)
    for i in range(1, len(qs)):
        if np.dot(qs[i], qs[i - 1]) < 0.0:
            qs[i] = -qs[i]
    return qs


def geodesic_deg(Ra: np.ndarray, Rb: np.ndarray) -> float:
    """Angular distance between two rotations in degrees."""
    cos = (np.trace(Ra.T @ Rb) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


# ------------------------------------------------------------ interpolation
class PoseInterpolator:
    """Continuous-time SE(3) interpolation of a discrete pose track.

    Translation: linear.  Rotation: SLERP.  Queries outside the time range
    are clamped to the endpoints (and flagged via `in_range`).
    """

    def __init__(self, timestamps: np.ndarray, Ts: np.ndarray):
        order = np.argsort(timestamps)
        self.t = np.asarray(timestamps, dtype=float)[order]
        Ts = np.asarray(Ts)[order]
        # deduplicate timestamps (Slerp requires strictly increasing)
        keep = np.concatenate([[True], np.diff(self.t) > 1e-9])
        self.t = self.t[keep]
        Ts = Ts[keep]
        self.trans = Ts[:, :3, 3]
        qs = fix_quat_continuity(
            np.stack([R_to_quat(T[:3, :3]) for T in Ts]))
        self._slerp = Slerp(self.t, Rotation.from_quat(qs))
        self.t0, self.t1 = float(self.t[0]), float(self.t[-1])

    def in_range(self, tq: float, slack: float = 0.05) -> bool:
        return (self.t0 - slack) <= tq <= (self.t1 + slack)

    def query(self, tq) -> np.ndarray:
        """Return 4x4 pose(s) at query time(s). Scalar -> (4,4)."""
        scalar = np.isscalar(tq)
        tq = np.atleast_1d(np.asarray(tq, dtype=float))
        tqc = np.clip(tq, self.t0, self.t1)
        Rq = self._slerp(tqc).as_matrix()
        pq = np.stack([np.interp(tqc, self.t, self.trans[:, k])
                       for k in range(3)], axis=-1)
        out = np.tile(np.eye(4), (len(tq), 1, 1))
        out[:, :3, :3] = Rq
        out[:, :3, 3] = pq
        return out[0] if scalar else out


# ---------------------------------------------------------------- alignment
def umeyama(src: np.ndarray, dst: np.ndarray, with_scale: bool = False):
    """Least-squares similarity/rigid transform aligning src -> dst.

    Returns (s, R, t) with  dst ~= s * R @ src + t.
    Used for evaluating trajectories against ground truth (ATE).
    """
    src = np.asarray(src, float)
    dst = np.asarray(dst, float)
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    if with_scale:
        var_s = (xs ** 2).sum() / len(src)
        s = float(np.trace(np.diag(D) @ S) / var_s)
    else:
        s = 1.0
    t = mu_d - s * R @ mu_s
    return s, R, t


def ate_rmse(est: np.ndarray, gt: np.ndarray, with_scale: bool = False):
    """Absolute trajectory error after Umeyama alignment. Returns (rmse, aligned_est)."""
    s, R, t = umeyama(est, gt, with_scale)
    est_al = s * est @ R.T + t
    err = np.linalg.norm(est_al - gt, axis=1)
    return float(np.sqrt((err ** 2).mean())), est_al
