"""Ego-motion: continuous-time camera pose in a gravity-aligned world frame.

This is the "forward SLAM" half of the reverse-SLAM problem -- and on
EmbodiData it comes for free: ARKit runs tightly-coupled VIO on-device with
factory calibration, so pose.csv already contains metric, gravity-aligned
T_world_cam at ~60 Hz. We only need to (a) fix coordinate conventions,
(b) interpolate to exact frame timestamps, (c) expose quality signals.

Coordinate conventions (the classic source of silent bugs):

  ARKit camera frame:  +x right, +y UP,   +z BACKWARD (camera looks along -z)
  OpenCV camera frame: +x right, +y DOWN, +z FORWARD  (what PnP/lift3d uses)
      R_arkitcam_cvcam = diag(1, -1, -1)      (180 deg about x)

  ARKit world (gravityAndHeading / gravity): +y up, metric, gravity-aligned.
  Optional robotics convention "zup": +z up, obtained by x->x, y->z, z->-y.

If the app captures portrait video, ARKit's pose still refers to the
landscape sensor frame while pixels are rotated; `video_rotation` composes
the corresponding in-plane rotation so that PnP results (in *rotated image*
coordinates) map correctly into the world.
"""
from __future__ import annotations

import numpy as np

from .se3 import PoseInterpolator, make_T

# ARKit camera -> OpenCV camera (rotation only, same origin)
R_ARKITCAM_CVCAM = np.diag([1.0, -1.0, -1.0])

# ARKit world (y-up) -> robotics world (z-up)
R_ZUP_ARKITW = np.array([[1.0, 0.0, 0.0],
                         [0.0, 0.0, -1.0],
                         [0.0, 1.0, 0.0]])


def _R_image_rotation(rot_deg: int) -> np.ndarray:
    """Camera-frame rotation equivalent to rotating the image by rot_deg
    clockwise: p_sensor_cv = Rz(theta) @ p_rotated_cv with theta = -rot_deg
    about the optical axis (OpenCV z)."""
    th = np.deg2rad(-(rot_deg % 360))
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


class EgoMotion:
    """Query T_world_cam (OpenCV camera frame, chosen world frame) at any t."""

    def __init__(self, pose_t: np.ndarray, T_world_cam_arkit: np.ndarray,
                 video_rotation: int = 0, world_convention: str = "arkit_yup",
                 time_offset_s: float = 0.0):
        self.time_offset = float(time_offset_s)

        T_ac_cv = make_T(R_ARKITCAM_CVCAM @ _R_image_rotation(video_rotation),
                         np.zeros(3))
        if world_convention == "zup":
            T_w_aw = make_T(R_ZUP_ARKITW, np.zeros(3))
        elif world_convention == "arkit_yup":
            T_w_aw = np.eye(4)
        else:
            raise ValueError(f"unknown world_convention {world_convention}")

        Ts = np.einsum("ij,njk,kl->nil", T_w_aw, T_world_cam_arkit, T_ac_cv)
        self._interp = PoseInterpolator(pose_t + self.time_offset, Ts)
        self.gravity_world = (np.array([0.0, -1.0, 0.0])
                              if world_convention == "arkit_yup"
                              else np.array([0.0, 0.0, -1.0]))

    def T_world_cam(self, t):
        return self._interp.query(t)

    def in_range(self, t) -> bool:
        return self._interp.in_range(t)

    def head_positions(self, ts: np.ndarray) -> np.ndarray:
        return self._interp.query(ts)[:, :3, 3]
