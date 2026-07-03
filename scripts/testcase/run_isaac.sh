#!/bin/bash

tmux new-session -d -s testcase
tmux split-window -v -t testcase:0.0
tmux split-window -h -t testcase:0.0
tmux split-window -v -t testcase:0.0
tmux split-window -v -t testcase:0.2

tmux send-keys -t testcase:0.0 "cd ~/airseai/scripts/testcase && bash enable_nav.sh" C-m

tmux send-keys -t testcase:0.1 "cd ~/airseai/scripts/testcase && bash enable_perception.sh" C-m

tmux send-keys -t testcase:0.2 "cd ~/airseai/scripts/testcase && bash enable_grasp.sh" C-m

tmux send-keys -t testcase:0.4 "cd ~/airseai/scripts/testcase && bash send_inst.sh" C-m

tmux send-keys -t testcase:0.3 "cd ~/airseai/scripts/testcase && bash enable_planner.sh" C-m

tmux select-pane -t testcase:0.4


tmux attach-session -t testcase


