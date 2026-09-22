#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
source ~/miniconda3/etc/profile.d/conda.sh
source ~/airseai/install/local_setup.bash
conda activate airseai_perception
ros2 launch airseai_perception run_airseai_perception_node.launch.py

