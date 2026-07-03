#!/bin/bash

source ~/airseai/install/local_setup.bash 

# Input
echo "Enter your instrucitons:"
read -r MSG

# Check empty
if [ -z "$MSG" ]; then
  echo "❌ No input, please enter a message."
  exit 1
fi

# Call ROS 2 service
echo "✅ Send: \"$MSG\""
ros2 service call /airseai_planner/planner_server airseai_interface/srv/AirseaiInstruct "{msg: \"$MSG\"}"


