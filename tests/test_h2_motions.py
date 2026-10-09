"""Offline motion CLI checks. No real SDK calls are made."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import h2_motion_common as motions


class MotionTests(unittest.TestCase):
    def test_scripts_select_correct_joint_and_default_to_check(self):
        expected = {
            "left_elbow": "left_elbow_joint", "right_elbow": "right_elbow_joint",
            "left_wrist": "left_wrist_roll_joint", "right_wrist": "right_wrist_roll_joint",
        }
        for name, joint in expected.items():
            with self.subTest(name=name), patch.object(motions.controller, "main", return_value=0) as call:
                path = SCRIPTS / f"h2_motion_{name}.py"
                with patch("sys.argv", [str(path), "--interface", "test0"]):
                    with self.assertRaises(SystemExit) as result:
                        runpy.run_path(str(path), run_name="__main__")
                self.assertEqual(result.exception.code, 0)
                self.assertEqual(call.call_args.args[0], [
                    joint, "2.0", "--relative", "--interface", "test0",
                    "--duration", "5", "--hold", "2", "--check"])

    def test_signed_execute_and_controller_failure_propagation(self):
        with patch.object(motions.controller, "main", return_value=1) as call:
            result = motions.main("right_wrist", ["--interface", "test0", "--degrees", "-5", "--execute"])
        self.assertEqual(result, 1)
        self.assertEqual(call.call_args.args[0][1], "-5.0")
        self.assertNotIn("--check", call.call_args.args[0])

    def test_invalid_angles_never_reach_controller(self):
        for value in ("0", "11", "-11", "nan", "inf"):
            with self.subTest(value=value), patch.object(motions.controller, "main") as call:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    motions.main("left_elbow", ["--interface", "test0", "--degrees", value, "--execute"])
                call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
