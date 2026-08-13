"""Rotation/Slerp provider: scipy when available, else a minimal pure-numpy
implementation with the same (subset of) API. Quaternions are (x, y, z, w).

Only the operations the pipeline uses are implemented in the fallback:
from_quat / from_matrix / as_quat / as_matrix / inv / __mul__ /
__getitem__ / magnitude, and Slerp(times, rotations)(query_times).
"""
from __future__ import annotations

try:                                       # pragma: no cover
    from scipy.spatial.transform import Rotation, Slerp  # type: ignore
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

    import numpy as np

    def _quat_to_matrix(q: "np.ndarray") -> "np.ndarray":
        x, y, z, w = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
        R = np.empty(q.shape[:-1] + (3, 3))
        R[..., 0, 0] = 1 - 2 * (y * y + z * z)
        R[..., 0, 1] = 2 * (x * y - z * w)
        R[..., 0, 2] = 2 * (x * z + y * w)
        R[..., 1, 0] = 2 * (x * y + z * w)
        R[..., 1, 1] = 1 - 2 * (x * x + z * z)
        R[..., 1, 2] = 2 * (y * z - x * w)
        R[..., 2, 0] = 2 * (x * z - y * w)
        R[..., 2, 1] = 2 * (y * z + x * w)
        R[..., 2, 2] = 1 - 2 * (x * x + y * y)
        return R

    def _matrix_to_quat(R: "np.ndarray") -> "np.ndarray":
        """Shepperd's method, single 3x3 -> (x,y,z,w)."""
        m = R
        tr = m[0, 0] + m[1, 1] + m[2, 2]
        if tr > 0:
            s = np.sqrt(tr + 1.0) * 2
            w = 0.25 * s
            x = (m[2, 1] - m[1, 2]) / s
            y = (m[0, 2] - m[2, 0]) / s
            z = (m[1, 0] - m[0, 1]) / s
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif m[1, 1] > m[2, 2]:
            s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s
        q = np.array([x, y, z, w])
        return q / np.linalg.norm(q)

    def _qmul(p: "np.ndarray", q: "np.ndarray") -> "np.ndarray":
        """Hamilton product p (x) q in xyzw; scipy semantics:
        (P*Q).apply(v) == P.apply(Q.apply(v))."""
        pv, pw = p[..., :3], p[..., 3:4]
        qv, qw = q[..., :3], q[..., 3:4]
        w = pw * qw - np.sum(pv * qv, axis=-1, keepdims=True)
        v = pw * qv + qw * pv + np.cross(pv, qv)
        return np.concatenate([v, w], axis=-1)

    class Rotation:  # noqa: N801  (mirror scipy's name)
        def __init__(self, quat: "np.ndarray", single: bool):
            self._q = np.atleast_2d(np.asarray(quat, dtype=float))
            self._q = self._q / np.linalg.norm(self._q, axis=-1, keepdims=True)
            self._single = single

        # -------- constructors
        @classmethod
        def from_quat(cls, q):
            q = np.asarray(q, dtype=float)
            return cls(q, single=(q.ndim == 1))

        @classmethod
        def from_matrix(cls, R):
            R = np.asarray(R, dtype=float)
            if R.ndim == 2:
                return cls(_matrix_to_quat(R), single=True)
            return cls(np.stack([_matrix_to_quat(r) for r in R]), single=False)

        # -------- accessors
        def as_quat(self):
            return self._q[0].copy() if self._single else self._q.copy()

        def as_matrix(self):
            M = _quat_to_matrix(self._q)
            return M[0] if self._single else M

        # -------- ops
        def inv(self):
            q = self._q.copy()
            q[:, :3] *= -1
            return Rotation(q[0] if self._single else q, self._single)

        def __mul__(self, other: "Rotation") -> "Rotation":
            q = _qmul(self._q, other._q)
            single = self._single and other._single
            return Rotation(q[0] if single else q, single)

        def __getitem__(self, idx):
            q = self._q[idx]
            return Rotation(q, single=(np.asarray(q).ndim == 1))

        def __len__(self):
            return len(self._q)

        def magnitude(self):
            m = 2.0 * np.arctan2(np.linalg.norm(self._q[:, :3], axis=1),
                                 np.abs(self._q[:, 3]))
            return float(m[0]) if self._single else m

    class Slerp:  # noqa: N801
        def __init__(self, times, rotations: "Rotation"):
            self.t = np.asarray(times, dtype=float)
            q = np.atleast_2d(rotations.as_quat()).copy()
            # hemisphere-align consecutive keyframes
            for i in range(1, len(q)):
                if np.dot(q[i], q[i - 1]) < 0:
                    q[i] = -q[i]
            self.q = q

        def __call__(self, tq):
            scalar_in = np.ndim(tq) == 0
            tq = np.atleast_1d(np.asarray(tq, dtype=float))
            tqc = np.clip(tq, self.t[0], self.t[-1])
            hi = np.clip(np.searchsorted(self.t, tqc, side="right"),
                         1, len(self.t) - 1)
            lo = hi - 1
            t0, t1 = self.t[lo], self.t[hi]
            u = np.where(t1 > t0, (tqc - t0) / np.maximum(t1 - t0, 1e-12), 0.0)
            q0, q1 = self.q[lo], self.q[hi]
            dot = np.clip(np.sum(q0 * q1, axis=-1), -1.0, 1.0)
            theta = np.arccos(np.abs(dot))
            sin_t = np.sin(theta)
            small = sin_t < 1e-6
            w0 = np.where(small, 1.0 - u, np.sin((1 - u) * theta)
                          / np.where(small, 1.0, sin_t))
            w1 = np.where(small, u, np.sin(u * theta)
                          / np.where(small, 1.0, sin_t))
            q = w0[:, None] * q0 + w1[:, None] * q1
            q = q / np.linalg.norm(q, axis=-1, keepdims=True)
            return Rotation(q[0] if scalar_in else q, single=scalar_in)
