#!/bin/bash
source ~/miniconda3/etc/profile.d/conda.sh
source ~/airseai/install/local_setup.bash
conda activate airseai_grasp
ros2 launch airseai_grasp grasp_sim.launch.py use_isaac_sim:=true

