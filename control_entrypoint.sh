#!/bin/bash
# Run inside the container via `docker exec`. Sources the sim environment,
# then pre-fills the ankle-swing command on the prompt (editable, just press
# Enter to run it as-is) instead of making you retype/paste it every time.
source ~/unitree_ros2/setup_local.sh
export ROS_DOMAIN_ID=1
source ~/unitree_ros2/example/install/setup.bash

read -e -i "ros2 run unitree_ros2_example h2_ankle_swing_example --ros-args --remap rt/lowcmd:=lowcmd --remap rt/lowstate:=lowstate --remap rt/secondary_imu:=secondary_imu" -p "\$ " cmd
eval "$cmd"

exec bash