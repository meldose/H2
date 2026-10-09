"""Offline CLI tests: no DDS initialization or robot commands."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h2_joint_cli as cli


class MenuTests(unittest.TestCase):
    def run_menu(self, answers, args=(), result=0):
        with patch("builtins.input", side_effect=answers), \
             patch.object(cli.arm, "main", return_value=result) as controller, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            code = cli.main(list(args))
        return code, controller, output.getvalue()

    def test_labeled_right_elbow_relative_adjustment(self):
        code, controller, output = self.run_menu(["11", "r", "5", "", "", "q"])
        self.assertEqual(code, 0)
        self.assertIn("Right Elbow", output)
        self.assertEqual(controller.call_args.args[0], [
            "right_elbow_joint", "5.0", "--interface", "eth0",
            "--topic", "arm_sdk",
            "--duration", "5", "--hold", "2", "--relative"])

    def test_absolute_read_only_and_invalid_input(self):
        _, controller, _ = self.run_menu(
            ["99", "1", "a", "nan", "0", "1", "5", "2", "q"],
            ["--check", "--interface", "test0"])
        command = controller.call_args.args[0]
        self.assertIn("--check", command)
        self.assertNotIn("--relative", command)
        self.assertEqual(command[command.index("--duration") + 1], "5.0")

    def test_head_selections(self):
        for selection, joint in [("15", "head_pitch_joint"), ("16", "head_yaw_joint")]:
            _, controller, output = self.run_menu([selection, "r", "2", "", "", "q"],
                                                   ["--check"])
            self.assertEqual(controller.call_args.args[0][0], joint)
            self.assertIn("Head Pitch", output)
            self.assertIn("Head Yaw", output)

    def test_interrupted_motion_exits_menu(self):
        code, controller, _ = self.run_menu(["1", "", "", "", ""], result=130)
        self.assertEqual(code, 130)
        controller.assert_called_once()

    def test_lowcmd_forwarded(self):
        _, controller, output = self.run_menu(["11", "r", "2", "", "", "q"],
                                               ["--topic", "lowcmd", "--check"])
        command = controller.call_args.args[0]
        self.assertEqual(command[command.index("--topic") + 1], "lowcmd")
        self.assertIn("--check", command)
        self.assertIn("rt/lowcmd", output)

    def test_lower_body_menu_only_available_on_lowcmd(self):
        _, controller, output = self.run_menu(["20", "q"])
        controller.assert_not_called()
        self.assertNotIn("Left Hip Pitch", output)
        for selection, joint in [("17", "left_hip_pitch_joint"), ("28", "right_ankle_pitch_joint"),
                                 ("29", "waist_roll_joint"), ("30", "waist_pitch_joint"),
                                 ("31", "waist_yaw_joint")]:
            _, controller, output = self.run_menu([selection, "r", "2", "", "", "q"],
                                                   ["--topic", "lowcmd", "--check"])
            self.assertEqual(controller.call_args.args[0][0], joint)
            self.assertIn("Waist Yaw", output)

    def test_arm_sdk_waist_menu(self):
        for selection, joint in [("17", "waist_roll_joint"), ("18", "waist_pitch_joint"),
                                 ("19", "waist_yaw_joint")]:
            _, controller, output = self.run_menu([selection, "r", "2", "", "", "q"], ["--check"])
            command = controller.call_args.args[0]
            self.assertEqual(command[0], joint)
            self.assertEqual(command[command.index("--topic") + 1], "arm_sdk")
            self.assertNotIn("Left Hip Pitch", output)


if __name__ == "__main__":
    unittest.main()
