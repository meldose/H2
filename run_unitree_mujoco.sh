#!/bin/bash
# Launches unitree_mujoco with unitree_sdk2's own CycloneDDS build prioritized
# on LD_LIBRARY_PATH, instead of ROS's (auto-sourced in every shell via
# .bashrc in this image). Without this, the dynamic linker resolves
# libddsc.so.0 from ROS's CycloneDDS (0.10.5, built with Iceoryx/SHM) while
# libddscxx.so.0 still resolves from unitree_sdk2's own build — a mismatched
# pair that crashes with:
#   dds_writecdr_impl_common: Assertion `(wr->m_iox_pub == NULL) == ...` failed
# See: https://github.com/unitreerobotics/unitree_mujoco/issues/60
#
# Deliberately scoped to just this one process (not exported globally) —
# doing that instead would flip the same mismatch onto ros2/rmw_cyclonedds_cpp
# commands run in the same shell.
#
# Usage: ./run_unitree_mujoco.sh

exec env LD_LIBRARY_PATH="/opt/unitree_robotics/lib:$LD_LIBRARY_PATH" \
    "$HOME/unitree_mujoco/simulate/build/unitree_mujoco" "$@"