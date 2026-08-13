"""Evaluate estimated wrist trajectories against ground truth (mocap /
ArUco-wrist rig). Produces the numbers reviewers expect: ATE-style wrist
error after time + rigid alignment, plus relative (drift) error.

GT format: CSV with columns t, x, y, z  (seconds, meters; any world frame --
alignment absorbs the frame difference). Usage:

    python -m handtraj.eval_gt --npz episodes/E1/hand_annotation/hands.npz \
        --gt gt_wrist_right.csv --side right [--with-scale]

`--with-scale` additionally reports scale-aligned error (sim(3)): comparing
the two isolates metric-scale mistakes (personalization off) from shape
mistakes (tracking noise).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .se3 import ate_rmse, umeyama


def _resample(t_src, x_src, t_dst):
    return np.stack([np.interp(t_dst, t_src, x_src[:, k]) for k in range(3)], 1)


def time_align(t_est, p_est, t_gt, p_gt, max_shift=2.0, step=0.005):
    """Grid-search a constant clock shift by minimizing rigid ATE."""
    best = (0.0, np.inf)
    for dt in np.arange(-max_shift, max_shift + step, step):
        t0 = max(t_est[0] + dt, t_gt[0])
        t1 = min(t_est[-1] + dt, t_gt[-1])
        if t1 - t0 < 1.0:
            continue
        grid = np.arange(t0, t1, 0.02)
        a = _resample(t_est + dt, p_est, grid)
        b = _resample(t_gt, p_gt, grid)
        rmse, _ = ate_rmse(a, b)
        if rmse < best[1]:
            best = (float(dt), rmse)
    return best[0]


def evaluate(t_est, p_est, t_gt, p_gt, with_scale=False) -> dict:
    dt = time_align(t_est, p_est, t_gt, p_gt)
    t0 = max(t_est[0] + dt, t_gt[0])
    t1 = min(t_est[-1] + dt, t_gt[-1])
    grid = np.arange(t0, t1, 0.02)
    a = _resample(t_est + dt, p_est, grid)
    b = _resample(t_gt, p_gt, grid)

    out = {"time_offset_s": dt, "overlap_s": float(t1 - t0)}
    rmse, a_al = ate_rmse(a, b, with_scale=False)
    err = np.linalg.norm(a_al - b, axis=1)
    out["ate_rmse_cm"] = 100 * rmse
    out["ate_median_cm"] = 100 * float(np.median(err))
    out["ate_p95_cm"] = 100 * float(np.percentile(err, 95))
    if with_scale:
        s, _, _ = umeyama(a, b, with_scale=True)
        rmse_s, _ = ate_rmse(a, b, with_scale=True)
        out["scale_factor"] = float(s)
        out["ate_rmse_scaled_cm"] = 100 * rmse_s
    # relative error over 1 s windows (drift, independent of alignment)
    n = int(1.0 / 0.02)
    if len(a) > n:
        da = a[n:] - a[:-n]
        db = b[n:] - b[:-n]
        out["rpe_1s_rmse_cm"] = 100 * float(
            np.sqrt((np.linalg.norm(da - db, axis=1) ** 2).mean()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--side", default="right", choices=["left", "right"])
    ap.add_argument("--with-scale", action="store_true")
    args = ap.parse_args()

    d = np.load(args.npz)
    p = args.side[0]
    valid = d[f"{p}_valid"]
    t_est = d["frame_times"][valid]
    p_est = d[f"{p}_wrist_world"][valid]

    gt = pd.read_csv(args.gt)
    cols = {c.lower(): c for c in gt.columns}
    t_gt = gt[cols.get("t", cols.get("timestamp"))].to_numpy(float)
    p_gt = gt[[cols["x"], cols["y"], cols["z"]]].to_numpy(float)

    res = evaluate(t_est, p_est, t_gt, p_gt, args.with_scale)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
