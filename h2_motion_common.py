"""Shared CLI for individual H2 arm motions; default is read-only.

Uses command_h2_arm.py for telemetry, limits, mode checks and execution.
No Cartesian planning, finger control or collision checking is provided.
"""
import argparse
import math

import command_h2_arm as controller


MOTIONS = {
    "left_elbow": "left_elbow_joint",
    "right_elbow": "right_elbow_joint",
    "left_wrist": "left_wrist_roll_joint",
    "right_wrist": "right_wrist_roll_joint",
}


def main(motion, argv=None):
    joint = MOTIONS[motion]
    parser = argparse.ArgumentParser(
        description=f"Check or execute a relative {joint} motion, then return. "
                    "Both arms are held during execution. Default: read-only check.")
    parser.add_argument("--interface", required=True)
    parser.add_argument("--degrees", type=float, default=2.0,
                        help="Signed relative change, -10 to +10 degrees; default +2")
    parser.add_argument("--execute", action="store_true", help="Actually command the real robot")
    args = parser.parse_args(argv)
    if not math.isfinite(args.degrees) or not 0 < abs(args.degrees) <= 10:
        parser.error("--degrees must be finite, nonzero, and between -10 and +10")
    command = [joint, str(args.degrees), "--relative", "--interface", args.interface,
               "--duration", "5", "--hold", "2"]
    if args.execute:
        print(f"REAL MOTION: {joint} changes by {args.degrees:g} degrees over 5 seconds, "
              "holds 2 seconds, then returns. Keep the arm path clear.", flush=True)
    else:
        command.append("--check")
        print("READ-ONLY: validating robot mode, feedback and target; no motion commands.", flush=True)
    return controller.main(command)
