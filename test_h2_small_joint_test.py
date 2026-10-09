"""Offline checks; the real controller is mocked and never connects to DDS."""
import contextlib
import io
import unittest
from unittest.mock import patch

import h2_small_joint_test as small


class SmallJointTest(unittest.TestCase):
    def test_default_cannot_execute(self):
        with patch.object(small.controller, "main", return_value=0) as run:
            self.assertEqual(small.main(["--interface", "test0"]), 0)
        self.assertEqual(run.call_args.args[0], [
            "left_elbow_joint", "2.0", "--relative", "--interface", "test0",
            "--duration", "5", "--hold", "1", "--check"])

    def test_execute_preserves_controller_failure(self):
        with patch.object(small.controller, "main", return_value=1) as run:
            result = small.main(["--interface", "test0", "--degrees", "-1", "--execute"])
        self.assertEqual(result, 1)
        self.assertNotIn("--check", run.call_args.args[0])
        self.assertEqual(run.call_args.args[0][1], "-1.0")

    def test_unsafe_or_invalid_inputs_never_reach_controller(self):
        cases = [["--degrees", v] for v in ("3", "-3", "nan", "inf", "0")]
        cases.append(["--joint", "left_knee_joint"])
        for case in cases:
            with self.subTest(case=case), patch.object(small.controller, "main") as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    small.main(["--interface", "test0", "--execute"] + case)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
