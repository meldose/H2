#!/bin/bash

# ==============================================================================
# Robot Onboard Computer Bootstrap
# ==============================================================================
# Run this on the robot's own computer (PC2 / Thor) — not on a dev workstation.
# Clones h2_ws and unitree_ros2 as siblings under ~/ros2 (same layout as
# README.md's "How to get started"), then runs the standard host setup and
# starts the container. unitree_mujoco is intentionally skipped: it simulates
# a robot, and this computer is already attached to a real one.
#
# unitree_ros2 is cloned from danreu25/unitree_ros2, a fork of
# unitreerobotics/unitree_ros2 carrying the local fixes this project needs
# (humble instead of foxy, fixed ROS_DOMAIN_ID) — not from upstream directly.
#
# h2_ws doesn't exist on the robot yet, so this single file has to get there
# some other way first — scp it over, or paste its contents into the SSH
# session:
#
#   scp docker/robot_bootstrap.sh unitree@192.168.123.164:~/   # or .162 for PC2
#   ssh unitree@192.168.123.164
#   chmod +x robot_bootstrap.sh && ./robot_bootstrap.sh
#
# Requires git access to the private GitLab remote already configured on this
# machine (SSH key or deploy token) — see README.md's robot deployment section.

set -e

ROS2_DIR="$HOME/ros2"
H2WS_URL="git@gitlab.gwdg.de:robost/ros2/ws/h2_ws.git"
UNITREE_ROS2_URL="https://github.com/danreu25/unitree_ros2.git"

mkdir -p "$ROS2_DIR"
cd "$ROS2_DIR"

if [ -d "h2_ws/.git" ]; then
    echo "h2_ws already present at $ROS2_DIR/h2_ws, skipping clone."
else
    git clone "$H2WS_URL"
fi

if [ -d "unitree_ros2/.git" ]; then
    echo "unitree_ros2 already present at $ROS2_DIR/unitree_ros2, skipping clone."
else
    git clone "$UNITREE_ROS2_URL"
fi

cd "$ROS2_DIR/h2_ws"
./docker/host_setup.sh
./docker/run_container.sh
