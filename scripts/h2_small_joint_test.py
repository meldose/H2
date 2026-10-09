#!/usr/bin/env python3
"""Check a small real-H2 arm motion; add --execute to actually move.

Requires command_h2_arm.py alongside this file. Motion is relative, limited
to 2 degrees, takes 5 seconds each way, and returns after a 1-second hold.
The existing controller checks still apply, including supported robot mode.
This is a smaller test motion, not a guarantee of physical safety.
"""
import argparse
import math
import sys

import command_h2_arm as controller


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", required=True, help="Robot Ethernet interface, e.g. enp6s0")
    parser.add_argument("--joint", choices=controller.ARM_NAMES, default="left_elbow_joint")
    parser.add_argument("--degrees", type=float, default=2.0,
                        help="Relative angle, between -2 and +2 degrees (default +2)")
    parser.add_argument("--execute", action="store_true",
                        help="Send real arm commands; otherwise only read and validate")
    args = parser.parse_args(argv)
    if not math.isfinite(args.degrees) or not 0 < abs(args.degrees) <= 2:
        parser.error("--degrees must be finite, nonzero, and between -2 and +2")
    command = [args.joint, str(args.degrees), "--relative", "--interface", args.interface,
               "--duration", "5", "--hold", "1"]
    if not args.execute:
        command.append("--check")
        print("READ-ONLY: checking feedback, robot mode and target; no motion commands.", flush=True)
    else:
        print("REAL MOTION: both arms will be held; the selected joint moves by "
              f"{args.degrees:g} degrees, then returns. Keep the arm area clear.", flush=True)
    return controller.main(command)


if __name__ == "__main__":
    sys.exit(main())
