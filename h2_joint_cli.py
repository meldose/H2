#!/usr/bin/env python3
"""Interactive, bounded H2 joint pose adjustments with ramped handover."""
import argparse
import math

import command_h2_arm as arm


def number(prompt, default, lower, upper):
    while True:
        raw = input(f"{prompt} [{default:g}]: ").strip()
        try:
            value = float(raw) if raw else default
            if math.isfinite(value) and lower <= value <= upper:
                return value
        except ValueError:
            pass
        print(f"Enter a finite number between {lower:g} and {upper:g}.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="eth0", help="Robot network interface (default eth0)")
    parser.add_argument("--topic", choices=("arm_sdk", "lowcmd"), default="arm_sdk",
                        help="DDS command topic (default arm_sdk); lowcmd requires physical support")
    parser.add_argument("--check", action="store_true", help="Validate selections without sending motor commands")
    args = parser.parse_args(argv)
    names = arm.ALL_NAMES if args.topic == "lowcmd" else arm.SDK_NAMES
    limits = arm.joint_limits(names)
    print("H2 joint pose menu — " + ("READ-ONLY" if args.check else "REAL ROBOT"))
    print(f"Command topic: rt/{args.topic}")
    if args.topic == "lowcmd":
        print("Physically support the robot and release its motion service first. No standing balance control.")
        print("Leg/waist selections hold both legs and waist; arms/head are uncommanded.")
        print("Arm/head selections leave legs/waist uncommanded.")
    else:
        print("Waist selections hold both arms and all waist joints.")
    print("Each adjustment holds briefly, then returns to its measured starting pose.")
    print("Head selections hold both arms and both head joints. Arm selections hold both arms. Keep the path clear and remote stop available.")
    try:
        while True:
            print("\nSelect a joint (angles in degrees):")
            for index, name in enumerate(names, 1):
                lo, hi = limits[name]
                label = name.removesuffix("_joint").replace("_", " ").title()
                print(f" {index:2d}. {label:25s} {math.degrees(lo):7.1f} .. {math.degrees(hi):7.1f}")
            selection = input("Joint number, or q to quit: ").strip().lower()
            if selection in ("q", "quit", "exit"):
                return 0
            if not selection.isdigit() or not 1 <= int(selection) <= len(names):
                print("Choose one of the listed joint numbers.")
                continue
            joint = names[int(selection) - 1]
            mode = input("Relative change (r) or absolute pose (a) [r]: ").strip().lower() or "r"
            if mode not in ("r", "a"):
                print("Choose r or a.")
                continue
            lo, hi = limits[joint]
            degrees = number("Change in degrees" if mode == "r" else "Target angle",
                             2 if mode == "r" else 0,
                             -30 if mode == "r" else math.degrees(lo),
                             30 if mode == "r" else math.degrees(hi))
            duration = number("Movement time in seconds (each way)", 5, 2.25, 60)
            hold = number("Hold time in seconds", 2, 0.1, 60)
            command = [joint, str(degrees), "--interface", args.interface,
                       "--topic", args.topic,
                       "--duration", str(duration), "--hold", str(hold)]
            if mode == "r":
                command.append("--relative")
            if args.check:
                command.append("--check")
            result = arm.main(command)
            if result == 130:
                return result
            if result:
                print("Adjustment stopped or rejected. Resolve the reported issue before retrying.")
    except (KeyboardInterrupt, EOFError):
        print("\nMenu closed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
