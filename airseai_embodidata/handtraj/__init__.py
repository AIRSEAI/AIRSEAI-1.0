"""EmbodiData hand-trajectory annotation pipeline ("reverse SLAM").

Recovers metric, gravity-aligned, world-frame 3D hand trajectories from
head-mounted iPhone recordings (RGB video + IMU + ARKit 6-DoF pose):

    T_world_hand(t) = T_world_cam(t) . T_cam_hand(t)

Entry points:
    scripts/run_pipeline.py         process one episode or a whole dataset
    python -m handtraj.calibrate_user   personalized hand-scale profiles
    python -m handtraj.eval_gt          ATE/RPE against ground truth
"""
__version__ = "0.1.0"
