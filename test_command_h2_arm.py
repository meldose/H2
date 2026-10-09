"""Offline tests: never initialize real DDS or send robot commands."""
import copy
import math
import types
import unittest
from unittest.mock import patch

import command_h2_arm as arm


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.limits = arm.joint_limits()
        self.start = [max(lo, min(0.0, hi)) for lo, hi in self.limits.values()]

    def test_only_requested_joint_changes(self):
        target = arm.plan(self.start, "left_elbow_joint", 10, True, 3, self.limits)
        self.assertAlmostEqual(target[3] - self.start[3], math.radians(10))
        self.assertEqual(target[:3] + target[4:], self.start[:3] + self.start[4:])

    def test_reject_bad_targets(self):
        for name, degrees, duration in [
            ("left_knee_joint", 10, 3), ("left_elbow_joint", float("nan"), 3),
            ("left_elbow_joint", 40, 3), ("left_elbow_joint", 30, 1),
            ("left_elbow_joint", -180, 3),
        ]:
            with self.subTest(name=name, degrees=degrees), self.assertRaises(ValueError):
                arm.plan(self.start, name, degrees, False, duration, self.limits)

    def test_interpolation_endpoints_and_monotonicity(self):
        self.assertEqual(arm.interpolate([0], [1], -1), [0])
        self.assertEqual(arm.interpolate([0], [1], 2), [1])
        values = [arm.interpolate([0], [1], i / 100)[0] for i in range(101)]
        self.assertEqual(values, sorted(values))

    def test_feedback_missing_stale_and_invalid(self):
        feedback = arm.Feedback()
        with self.assertRaises(RuntimeError):
            feedback.read()
        msg = types.SimpleNamespace(motor_state=[types.SimpleNamespace(q=0.0) for _ in range(35)])
        with patch.object(arm.time, "monotonic", return_value=1.0):
            feedback.update(msg)
            self.assertEqual(feedback.read(), [0.0] * 14)
        with patch.object(arm.time, "monotonic", return_value=1.3):
            with self.assertRaises(RuntimeError):
                feedback.read()
        msg.motor_state[15].q = float("nan")
        with patch.object(arm.time, "monotonic", return_value=2.0):
            feedback.update(msg)
            with self.assertRaises(RuntimeError):
                feedback.read()


class FakeRobot:
    def __init__(self):
        self.now = 1.0
        self.positions = [0.0] * 14
        self.commands = []
        self.enabled = []
        self.mode = 4
        self.owned = False
        self.interrupt = False
        self.stale = False
        self.enable_code = 0
        self.channels = []
        self.motion_mode = {"name": ""}
        self.motion_code = 0

    def modules(self):
        robot = self
        class Loco:
            def Init(self): pass
            def SetTimeout(self, timeout): pass
            def GetFsmId(self): return 0, robot.mode
            def GetArmSdkStatus(self): return 0, robot.owned
            def SetArmSdkStatus(self, enabled):
                robot.enabled.append(enabled)
                return robot.enable_code if enabled else 0
        class Subscriber:
            def __init__(self, topic, msg):
                robot.channels.append(topic)
            def Init(self, callback, queue): pass
            def Close(self): pass
        class Switcher:
            def Init(self): pass
            def SetTimeout(self, timeout): pass
            def CheckMode(self): return robot.motion_code, robot.motion_mode
        class Publisher:
            def __init__(self, topic, msg):
                robot.channels.append(topic)
            def Init(self): pass
            def Close(self): pass
            def Write(self, cmd):
                if robot.interrupt and len(robot.commands) == 3:
                    raise KeyboardInterrupt
                robot.commands.append(copy.deepcopy(cmd))
                robot.positions = [cmd.motor_cmd[i].q for i in robot.motor_ids]
                return True
        def command():
            return types.SimpleNamespace(
                motor_cmd=[types.SimpleNamespace(q=0.0, dq=0.0, tau=0.0, kp=0.0, kd=0.0)
                           for _ in range(35)], crc=0)
        def initialize(domain, interface):
            assert (domain, interface) == (0, "test0")
        return {
            "unitree_sdk2py.core.channel": types.SimpleNamespace(
                ChannelFactoryInitialize=initialize, ChannelPublisher=Publisher, ChannelSubscriber=Subscriber),
            "unitree_sdk2py.h2.loco.h2_loco_client": types.SimpleNamespace(LocoClient=Loco),
            "unitree_sdk2py.comm.motion_switcher.motion_switcher_client": types.SimpleNamespace(MotionSwitcherClient=Switcher),
            "unitree_sdk2py.idl.default": types.SimpleNamespace(unitree_hg_msg_dds__LowCmd_=command),
            "unitree_sdk2py.idl.unitree_hg.msg.dds_": types.SimpleNamespace(LowCmd_=object, LowState_=object),
            "unitree_sdk2py.utils.crc": types.SimpleNamespace(CRC=lambda: types.SimpleNamespace(Crc=lambda cmd: 42)),
        }

    def read(self):
        if self.stale and len(self.commands) >= 3:
            raise RuntimeError("stale feedback")
        return list(self.positions)

    def sleep(self, duration):
        self.now += duration

    def run(self, check=False, joint="left_elbow_joint", topic="arm_sdk"):
        names = arm.controlled_names(joint, topic)
        ids = arm.LOWCMD_IDS if topic == "lowcmd" else arm.JOINT_IDS
        self.motor_ids = [ids[name] for name in names]
        self.positions = [0.0] * len(names)
        args = types.SimpleNamespace(interface="test0", joint=joint, degrees=10,
                                     relative=True, duration=3.0, hold=1.0, check=check, topic=topic)
        with patch.dict("sys.modules", self.modules()), \
             patch.object(arm.Feedback, "read", side_effect=self.read), \
             patch.object(arm.Feedback, "machine_mode", return_value=7), \
             patch.object(arm.time, "monotonic", side_effect=lambda: self.now), \
             patch.object(arm.time, "sleep", side_effect=self.sleep):
            arm.run(args)


class ProtocolTests(unittest.TestCase):
    def test_all_leg_and_waist_motors_move_only_target_and_return(self):
        expected = {
            "left_hip_pitch_joint": 0, "left_hip_roll_joint": 1,
            "left_hip_yaw_joint": 2, "left_knee_joint": 3,
            "left_ankle_roll_joint": 4, "left_ankle_pitch_joint": 5,
            "right_hip_pitch_joint": 6, "right_hip_roll_joint": 7,
            "right_hip_yaw_joint": 8, "right_knee_joint": 9,
            "right_ankle_roll_joint": 10, "right_ankle_pitch_joint": 11,
            "waist_roll_joint": 12, "waist_pitch_joint": 13, "waist_yaw_joint": 14,
        }
        for joint, index in expected.items():
            with self.subTest(joint=joint):
                robot = FakeRobot()
                robot.run(joint=joint, topic="lowcmd")
                self.assertEqual(robot.channels, ["rt/lowstate", "rt/lowcmd"])
                self.assertEqual(robot.enabled, [])
                self.assertAlmostEqual(max(c.motor_cmd[index].q for c in robot.commands), math.radians(10))
                self.assertEqual(robot.positions, [0.] * 15)
                peak = max(robot.commands, key=lambda c: c.motor_cmd[index].kp)
                for i, motor in enumerate(peak.motor_cmd):
                    self.assertEqual(motor.mode, int(i < 15))
                    if i != index:
                        self.assertEqual(motor.q, 0.)
                self.assertEqual(peak.motor_cmd[3].kp, 250)
                self.assertEqual(peak.motor_cmd[12].kd, 2.5)
                self.assertEqual(peak.motor_cmd[13].kd, 5.)
                self.assertTrue(all(m.kp == m.kd == 0 for m in robot.commands[-1].motor_cmd))

    def test_lower_body_rejected_before_dds_on_arm_sdk(self):
        for joint in arm.LEG_NAMES:
            with self.subTest(joint=joint), self.assertRaisesRegex(ValueError, "require --topic lowcmd"):
                arm.run(types.SimpleNamespace(joint=joint, topic="arm_sdk"))

    def test_arm_sdk_waist_mapping_gains_and_return(self):
        for joint, selected in [("waist_yaw_joint", 12), ("waist_roll_joint", 13),
                                ("waist_pitch_joint", 14)]:
            with self.subTest(joint=joint):
                robot = FakeRobot()
                robot.run(joint=joint, topic="arm_sdk")
                self.assertEqual(robot.channels, ["rt/lowstate", "rt/arm_sdk"])
                self.assertEqual(robot.enabled, [True, False])
                self.assertAlmostEqual(max(c.motor_cmd[selected].q for c in robot.commands), math.radians(10))
                self.assertEqual(robot.positions, [0.] * 17)
                for cmd in robot.commands:
                    weight = cmd.motor_cmd[31].q
                    for i in range(12):
                        self.assertEqual((cmd.motor_cmd[i].q, cmd.motor_cmd[i].kp, cmd.motor_cmd[i].kd), (0, 0, 0))
                    for i, kd in [(12, 5.), (13, 2.5), (14, 5.)]:
                        self.assertAlmostEqual(cmd.motor_cmd[i].kp, 200 * weight)
                        self.assertAlmostEqual(cmd.motor_cmd[i].kd, kd * weight)
                    for i in set(range(12, 31)) - {selected}:
                        self.assertEqual(cmd.motor_cmd[i].q, 0)
                robot = FakeRobot()
                robot.run(joint=joint, topic="arm_sdk", check=True)
                self.assertEqual(robot.commands, [])
                self.assertEqual(robot.enabled, [])

    def test_lower_body_limits_and_read_only(self):
        limits = arm.joint_limits(arm.LOWER_NAMES)
        with self.assertRaisesRegex(ValueError, "Target exceeds"):
            arm.plan([0.] * 15, "left_ankle_roll_joint", 30, True, 5, limits, "lowcmd")
        target = arm.plan([0.1] * 15, "waist_yaw_joint", 2, True, 5, limits, "lowcmd")
        self.assertEqual(target[:14], [0.1] * 14)
        self.assertAlmostEqual(target[14], 0.1 + math.radians(2))
        robot = FakeRobot()
        robot.run(joint="left_knee_joint", topic="lowcmd", check=True)
        self.assertEqual(robot.commands, [])
        self.assertEqual(robot.channels, ["rt/lowstate"])

    def test_lowcmd_protocol(self):
        robot = FakeRobot()
        robot.run(topic="lowcmd")
        self.assertEqual(robot.channels, ["rt/lowstate", "rt/lowcmd"])
        self.assertEqual(robot.enabled, [])
        self.assertAlmostEqual(max(c.motor_cmd[18].q for c in robot.commands), math.radians(10))
        self.assertEqual(robot.positions, [0.0] * 14)
        for cmd in robot.commands:
            self.assertEqual((cmd.mode_pr, cmd.mode_machine, cmd.crc), (0, 7, 42))
            for index, motor in enumerate(cmd.motor_cmd):
                self.assertEqual(motor.mode, int(15 <= index <= 28))
                if not 15 <= index <= 28:
                    self.assertEqual((motor.q, motor.kp, motor.kd), (0, 0, 0))
        self.assertEqual(robot.commands[-1].motor_cmd[18].kp, 0)

    def test_lowcmd_check_and_service_refusal(self):
        robot = FakeRobot()
        robot.run(topic="lowcmd", check=True)
        self.assertEqual(robot.channels, ["rt/lowstate"])
        self.assertEqual(robot.enabled, [])
        for mode in ({"name": "normal"}, None, {}):
            robot = FakeRobot()
            robot.motion_mode = mode
            with self.assertRaises(RuntimeError):
                robot.run(topic="lowcmd")
            self.assertEqual(robot.commands, [])

    def test_lowcmd_feedback_mapping_and_machine_mode(self):
        feedback = arm.Feedback(arm.JOINT_NAMES, arm.LOWCMD_IDS)
        with self.assertRaises(RuntimeError):
            feedback.machine_mode()
        msg = types.SimpleNamespace(mode_machine=7,
            motor_state=[types.SimpleNamespace(q=float(i)) for i in range(35)])
        feedback.update(msg)
        self.assertEqual(feedback.machine_mode(), 7)
        self.assertEqual(feedback.read()[4:7], [21, 20, 19])
        self.assertEqual(feedback.read()[11:14], [28, 27, 26])

    def test_lowcmd_abort_does_not_call_arm_sdk(self):
        for attribute, error in [("stale", RuntimeError), ("interrupt", KeyboardInterrupt)]:
            robot = FakeRobot()
            setattr(robot, attribute, True)
            with self.assertRaises(error):
                robot.run(topic="lowcmd")
            self.assertEqual(robot.enabled, [])
            self.assertEqual(len(robot.commands), 3)

    def test_success_moves_only_arm_target_and_returns(self):
        robot = FakeRobot()
        robot.run()
        self.assertEqual(robot.enabled, [True, False])
        self.assertEqual(robot.channels, ["rt/lowstate", "rt/arm_sdk"])
        self.assertAlmostEqual(max(c.motor_cmd[18].q for c in robot.commands), math.radians(10))
        self.assertEqual(robot.positions, [0.0] * 14)
        self.assertEqual(robot.commands[-1].motor_cmd[31].q, 0)
        self.assertEqual(robot.commands[0].motor_cmd[18].kp, 0)
        weights = [c.motor_cmd[31].q for c in robot.commands]
        self.assertTrue(any(0 < w < 1 for w in weights))
        for cmd in robot.commands:
            weight = cmd.motor_cmd[31].q
            for index in range(15, 29):
                self.assertAlmostEqual(cmd.motor_cmd[index].kp, 80 * weight)
                self.assertAlmostEqual(cmd.motor_cmd[index].kd, 1.5 * weight)
            self.assertEqual(cmd.crc, 42)
            for index in list(range(15)) + [29, 30, 32, 33, 34]:
                self.assertEqual(vars(cmd.motor_cmd[index]), dict(q=0., dq=0., tau=0., kp=0., kd=0.))
            for index in set(range(15, 29)) - {18}:
                self.assertEqual(cmd.motor_cmd[index].q, 0)

    def test_head_motion_gains_and_return(self):
        for joint in arm.HEAD_NAMES:
            robot = FakeRobot()
            robot.run(joint=joint)
            selected = arm.JOINT_IDS[joint]
            self.assertAlmostEqual(max(c.motor_cmd[selected].q for c in robot.commands),
                                   math.radians(10))
            self.assertEqual(robot.positions, [0.0] * 16)
            self.assertEqual(robot.enabled, [True, False])
            for cmd in robot.commands:
                weight = cmd.motor_cmd[31].q
                for index in (29, 30):
                    self.assertAlmostEqual(cmd.motor_cmd[index].kp, 30 * weight)
                    self.assertAlmostEqual(cmd.motor_cmd[index].kd, weight)
                for index in set(range(15, 31)) - {selected}:
                    self.assertEqual(cmd.motor_cmd[index].q, 0)
                for index in range(15):
                    self.assertEqual(cmd.motor_cmd[index].kp, 0)
            robot = FakeRobot()
            robot.run(check=True, joint=joint)
            self.assertEqual(robot.commands, [])
            self.assertEqual(robot.enabled, [])

    def test_check_does_not_enable_or_publish(self):
        robot = FakeRobot()
        robot.run(check=True)
        self.assertEqual(robot.enabled, [])
        self.assertEqual(robot.commands, [])
        self.assertEqual(robot.channels, ["rt/lowstate"])

    def test_wrong_mode_and_invalid_status_refused(self):
        for attribute, value in [("mode", 1), ("mode", 601), ("owned", None)]:
            robot = FakeRobot()
            setattr(robot, attribute, value)
            with self.assertRaises(RuntimeError):
                robot.run()
            self.assertEqual(robot.enabled, [])
            self.assertEqual(robot.commands, [])

    def test_enabled_sdk_is_not_treated_as_another_owner(self):
        robot = FakeRobot()
        robot.owned = True
        robot.run(check=True)
        self.assertEqual(robot.enabled, [])
        self.assertEqual(robot.commands, [])
        robot.run()
        self.assertEqual(robot.enabled, [True, False])

    def test_stale_feedback_and_interrupt_release_control(self):
        for attribute, error in [("stale", RuntimeError), ("interrupt", KeyboardInterrupt)]:
            robot = FakeRobot()
            setattr(robot, attribute, True)
            with self.assertRaises(error):
                robot.run()
            self.assertEqual(robot.enabled, [True, False])
            self.assertEqual(len(robot.commands), 3)

    def test_failed_enable_attempt_releases_without_publishing(self):
        robot = FakeRobot()
        robot.enable_code = 42
        with self.assertRaises(RuntimeError):
            robot.run()
        self.assertEqual(robot.enabled, [True, False])
        self.assertEqual(robot.commands, [])


if __name__ == "__main__":
    unittest.main()
