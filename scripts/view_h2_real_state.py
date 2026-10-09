#!/usr/bin/env python3
"""Passive MuJoCo viewer that mirrors the real H2's joint state — read-only.

Unlike unitree_mujoco's own C++ bridge (which is a full physics simulator:
it *subscribes* rt/lowcmd to drive its own physics *and* publishes its own
simulated rt/lowstate/rt/sportmodestate), this script only *subscribes*
rt/lowstate and writes the received joint angles into a MuJoCo viewer's
qpos — no physics stepping, no rt/lowcmd publisher, nothing written back to
the robot. Pointing the real bridge at the real robot's DDS domain would put
a second, fake publisher of rt/lowstate on the robot's live network,
racing the real one — this script avoids that entirely by never publishing.

Root orientation (tilt/lean) comes from rt/lowstate's IMU quaternion, which
is raw sensor data — always published regardless of control mode. Root
*position* comes from rt/sportmodestate instead, which per
unitree_mujoco/readme.md "is not readable after the built-in motion control
service is turned off" on real hardware — so it's only available while the
robot is in its normal built-in locomotion mode (e.g. driven by Unitree's
own joystick/remote), not while a custom LowCmd controller (like this
workspace's h2_ankle_swing_example) has taken over. If no
rt/sportmodestate ever arrives, position just stays pinned at a nominal
spot while orientation and joints keep animating — no error, just less
data available in that control mode.

Usage:
    python3 scripts/view_h2_real_state.py --interface eth0   # real robot, domain 0
    python3 scripts/view_h2_real_state.py --mock              # local MuJoCo sim instead,
                                                        # domain 1 / "lo" — same
                                                        # convention as ros2_control's
                                                        # use_mock_hardware, requires
                                                        # scripts/run_unitree_mujoco.sh already
                                                        # running (see docs/RUNBOOK.md)

Real-robot interface is whatever `ip a` shows once the Ethernet cable is
connected (see docs/RUNBOOK.md § Real robot for the one-time host IP setup);
domain_id is 0 there, the real robot's default.
"""
import argparse
import threading

import mujoco
import mujoco.viewer
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

SCENE_XML = "/home/robost/unitree_mujoco/unitree_robots/h2/scene.xml"

# Motor index -> joint name, in rt/lowstate's motor_state[] order. Not the
# MJCF's own kinematic-tree joint order (which puts head before the arms) —
# this is Unitree's motor numbering (head last), read off this workspace's
# own unitree_mujoco run log (H2, unitree_hg IDL, "Sensor_index" printout).
MOTOR_JOINT_NAMES = [
    "left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint",
    "left_knee_joint", "left_ankle_roll_joint", "left_ankle_pitch_joint",
    "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint",
    "right_knee_joint", "right_ankle_roll_joint", "right_ankle_pitch_joint",
    "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
    "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint",
    "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint",
    "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint",
    "head_pitch_joint", "head_yaw_joint",
]

state_lock = threading.Lock()
latest_q = [0.0] * len(MOTOR_JOINT_NAMES)
latest_quat = [1.0, 0.0, 0.0, 0.0]  # w x y z — MuJoCo's own convention, no reorder needed
latest_pos = None  # None until an rt/sportmodestate message actually arrives


def LowStateHandler(msg: LowState_):
    with state_lock:
        for i in range(len(MOTOR_JOINT_NAMES)):
            latest_q[i] = msg.motor_state[i].q
        latest_quat[:] = msg.imu_state.quaternion


def SportModeStateHandler(msg: SportModeState_):
    global latest_pos
    with state_lock:
        latest_pos = list(msg.position)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mock", action="store_true",
                         help="read from the local MuJoCo sim (domain 1, interface lo) instead of the real robot")
    parser.add_argument("--interface", help="host network interface connected to the real robot (ignored with --mock)")
    args = parser.parse_args()
    if not args.mock and not args.interface:
        parser.error("--interface is required unless --mock is set")
    return args


def main():
    args = parse_args()
    domain_id, interface = (1, "lo") if args.mock else (0, args.interface)

    model = mujoco.MjModel.from_xml_path(SCENE_XML)
    data = mujoco.MjData(model)

    qpos_adr = []
    for name in MOTOR_JOINT_NAMES:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError(f"joint '{name}' not found in {SCENE_XML}")
        qpos_adr.append(model.jnt_qposadr[joint_id])

    pelvis_joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "floating_base_joint")
    pelvis_adr = model.jnt_qposadr[pelvis_joint_id]
    data.qpos[pelvis_adr:pelvis_adr + 7] = [0, 0, 1.2, 1, 0, 0, 0]  # x y z, quat w x y z

    ChannelFactoryInitialize(domain_id, interface)
    lowstate_suber = ChannelSubscriber("rt/lowstate", LowState_)
    lowstate_suber.Init(LowStateHandler, 10)
    sportstate_suber = ChannelSubscriber("rt/sportmodestate", SportModeState_)
    sportstate_suber.Init(SportModeStateHandler, 10)

    source = "local MuJoCo sim" if args.mock else "real robot"
    print(f"Subscribing rt/lowstate + rt/sportmodestate on domain {domain_id}, interface '{interface}' "
          f"({source}). Read-only — publishes nothing. Position stays pinned until/unless "
          f"rt/sportmodestate actually arrives (see module docstring).")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            with state_lock:
                for adr, q in zip(qpos_adr, latest_q):
                    data.qpos[adr] = q
                data.qpos[pelvis_adr + 3:pelvis_adr + 7] = latest_quat
                if latest_pos is not None:
                    data.qpos[pelvis_adr:pelvis_adr + 3] = latest_pos
            mujoco.mj_kinematics(model, data)
            viewer.sync()


if __name__ == "__main__":
    main()
