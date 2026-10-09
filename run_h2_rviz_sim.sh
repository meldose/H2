#!/usr/bin/env bash
# Run inside the ROS workspace environment/container.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    echo 'Run with: bash ./run_h2_rviz_sim.sh (do not source this launcher).' >&2
    return 1
fi
set -eo pipefail
SIM_WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SIM_WORKSPACE"
if ! command -v ros2 >/dev/null 2>&1; then
    for distro in jazzy humble; do
        if [[ -f "/opt/ros/$distro/setup.bash" ]]; then
            source "/opt/ros/$distro/setup.bash"
            break
        fi
    done
fi
if ! command -v colcon >/dev/null 2>&1; then
    echo 'ROS/colcon unavailable. Run this script inside the workspace ROS container.' >&2
    exit 1
fi
colcon build --build-base build/h2_rviz_sim --install-base install/h2_rviz_sim \
    --cmake-clean-cache --packages-select h2_description h2_moveit_config
source "$SIM_WORKSPACE/install/h2_rviz_sim/setup.bash"
exec ros2 launch h2_moveit_config motion_sim_launch.py "$@"
