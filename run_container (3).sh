#!/bin/bash

# ==============================================================================
# Project-specific Container Start Script
# ==============================================================================
# Sources the generic docker_template runner and injects project-specific
# Docker arguments. The ROS 2 tutorials need no extra hardware devices, so the
# argument arrays are left empty — add e.g. `--device /dev/dri` for
# hardware-accelerated GUI rendering, or `--device /dev/video0` for a camera.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(dirname "$SCRIPT_DIR")"

# Project-specific arguments (applied on all platforms).
EXTRA_DOCKER_ARGS_COMMON=()

# unitree_ros2 is its own standalone workspace (see its README), not part of
# this repo — cloned separately at ~/ros2/unitree_ros2, sibling to this
# workspace. Its own setup.sh/setup_local.sh hardcode $HOME/unitree_ros2, so
# it's bind-mounted at exactly that container path to match, rather than
# folded into this repo's src/ tree.
UNITREE_ROS2_DIR="$(dirname "$WS_DIR")/unitree_ros2"
if [ -d "$UNITREE_ROS2_DIR" ]; then
    EXTRA_DOCKER_ARGS_COMMON+=(--volume="$UNITREE_ROS2_DIR:/home/robost/unitree_ros2")
fi

# unitree_mujoco: same reasoning as unitree_ros2 above — its own standalone
# workspace (its own cmake build, config.yaml, robot scene files), cloned
# separately at ~/ros2/unitree_mujoco, bind-mounted rather than folded in.
UNITREE_MUJOCO_DIR="$(dirname "$WS_DIR")/unitree_mujoco"
if [ -d "$UNITREE_MUJOCO_DIR" ]; then
    EXTRA_DOCKER_ARGS_COMMON+=(--volume="$UNITREE_MUJOCO_DIR:/home/robost/unitree_mujoco")
fi

# X11 over SSH (ssh -X/-Y, e.g. connecting to the robot's PC2) authenticates
# via a cookie in ~/.Xauthority — docker_template's xhost-based X11 setup
# above only covers a local monitor's host-based access control, not this.
# Bind-mounted live (not a one-time `docker cp` snapshot) so it stays correct
# across SSH reconnects without redoing anything by hand.
if [ -f "$HOME/.Xauthority" ]; then
    EXTRA_DOCKER_ARGS_COMMON+=(--volume="$HOME/.Xauthority:/home/robost/.Xauthority:ro")
    EXTRA_DOCKER_ARGS_COMMON+=(--env="XAUTHORITY=/home/robost/.Xauthority")
fi

# Platform-specific arguments.
EXTRA_DOCKER_ARGS_AMD64=()
EXTRA_DOCKER_ARGS_ARM64=()
EXTRA_DOCKER_ARGS_WSL=()

# ------------------------------------------------------------------------------
# Source the template and run.
# ------------------------------------------------------------------------------
# shellcheck source=docker_template/run_container.sh
source "$SCRIPT_DIR/docker_template/run_container.sh"

detect_platform
detect_usb_can
preflight_checks

case "$ARCH_TYPE" in
    amd64) run_amd64 ;;
    arm64) run_arm64 ;;
    wsl)   run_wsl   ;;
esac
