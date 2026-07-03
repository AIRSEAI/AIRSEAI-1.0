#!/bin/bash
source ~/airseai/install/local_setup.bash
ros2 launch airseai_localization airseai_localization_gt_sim.launch.py &
ros2 launch airseai_navigation airseai_navigation_sim.launch.py

