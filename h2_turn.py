#!/usr/bin/env python3
"""Approximate H2 in-place turns using a timed high-level velocity command."""
import argparse
from contextlib import ExitStack
import fcntl
import math
from pathlib import Path
import sys
import time


YAW_RATE_RAD_S = 0.2
STOP_LEASE_SECONDS = 0.75
DISPLAY_UPDATE_SECONDS = 0.2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="enp6s0",
                        help="H2 network interface on PC2 (default: enp6s0)")
    parser.add_argument("--angle", type=int, choices=(45, 90), default=45,
                        help="Approximate turn angle in degrees (default: 45)")
    parser.add_argument("--direction", choices=("left", "right"), default="left",
                        help="Turn direction (default: left)")
    parser.add_argument("--check", action="store_true",
                        help="Read controller status only; send no motion commands (default)")
    parser.add_argument("--execute", action="store_true",
                        help="After preflight and explicit confirmation, request the timed turn")
    args = parser.parse_args(argv)
    if args.check and args.execute:
        parser.error("choose only one of --check and --execute")

    omega = YAW_RATE_RAD_S if args.direction == "left" else -YAW_RATE_RAD_S
    duration = math.radians(args.angle) / YAW_RATE_RAD_S
    print("H2 in-place turn — " + ("READ-ONLY" if not args.execute else "EXECUTION ARMED"))
    print(f"Requested turn: about {args.angle} degrees {args.direction} at {YAW_RATE_RAD_S:.2f} rad/s.")
    print(f"Timed command duration: {duration:.2f} seconds; angle is estimated, not measured.")
    print("Positive yaw is treated as left/counterclockwise; verify with the 45-degree option first.")
    print("Use a flat, clear area with a spotter and the robot's remote stop ready.")

    try:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient
    except ImportError as exc:
        print(f"SDK unavailable: {exc}. Run this inside the h2_ws container.", file=sys.stderr)
        return 1

    lock_paths = (Path("/tmp/h2_locomotion_command.lock"),
                  Path("/tmp/h2_arm_command.lock"))
    try:
        with ExitStack() as locks:
            for path in lock_paths:
                lock = locks.enter_context(path.open("w"))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise RuntimeError(f"Another H2 command is running on this host ({path.name})") from exc

            ChannelFactoryInitialize(0, args.interface)
            loco = LocoClient()
            loco.SetTimeout(10.0)
            loco.Init()

            code, fsm_id = loco.GetFsmId()
            if code != 0 or fsm_id is None:
                raise RuntimeError(f"Cannot read H2 FSM ID (code={code})")
            code, fsm_mode = loco.GetFsmMode()
            if code != 0 or fsm_mode is None:
                raise RuntimeError(f"Cannot read H2 FSM mode (code={code})")
            code, arm_sdk_enabled = loco.GetArmSdkStatus()
            if code != 0 or type(arm_sdk_enabled) is not bool:
                raise RuntimeError(f"Cannot read Arm SDK status (code={code})")
            print(f"H2 reports FSM id={fsm_id}, mode={fsm_mode}, Arm SDK enabled={arm_sdk_enabled}.")
            if arm_sdk_enabled:
                print("Arm SDK enabled flag does not show whether an arm publisher is active.")
            if not args.execute:
                print("Check complete. No motion commands sent.")
                return 0

            print("Confirm the robot is upright and stationary, there is room to turn, and the remote stop is ready.")
            confirmation_phrase = f"TURN {args.direction.upper()} {args.angle} DEGREES"
            confirmation = " ".join(input(f"Type {confirmation_phrase} to begin: ").upper().split())
            if confirmation != confirmation_phrase:
                print("Cancelled. No motion commands sent.")
                return 0

            command_attempted = False
            stop_failed = False
            try:
                command_attempted = True
                code = loco.SetVelocity(0.0, 0.0, omega, duration)
                if code != 0:
                    raise RuntimeError(f"Turn velocity request failed (code={code})")

                started = time.monotonic()
                next_update = 0.0
                while True:
                    elapsed = min(time.monotonic() - started, duration)
                    if elapsed >= next_update:
                        estimate_deg = math.degrees(YAW_RATE_RAD_S * elapsed)
                        print(f"t={elapsed:4.1f}/{duration:.1f}s  commanded yaw={omega:+.2f} rad/s  "
                              f"estimated turn={estimate_deg:.0f}/{args.angle} degrees (not measured)",
                              end="\r", flush=True)
                        next_update += DISPLAY_UPDATE_SECONDS
                    remaining = duration - elapsed
                    if remaining <= 0:
                        break
                    time.sleep(min(DISPLAY_UPDATE_SECONDS, remaining))
                print(flush=True)
                print(f"Turn RPC accepted (code={code}); actual heading change is not measured.", flush=True)
            finally:
                if command_attempted:
                    try:
                        stop_code = loco.SetVelocity(0.0, 0.0, 0.0, STOP_LEASE_SECONDS)
                        if stop_code != 0:
                            stop_failed = True
                            print(f"STOP REQUEST FAILED (code={stop_code}); use the robot remote stop immediately.",
                                  file=sys.stderr, flush=True)
                        else:
                            print("Zero-velocity stop request sent.", flush=True)
                    except Exception as stop_error:
                        stop_failed = True
                        print(f"STOP REQUEST FAILED ({stop_error}); use the robot remote stop immediately.",
                              file=sys.stderr, flush=True)

            if stop_failed:
                return 1
            print("Timed turn finished. Check the robot's heading before another command.")
            return 0
    except KeyboardInterrupt:
        print("Interrupted; a zero-velocity request was attempted if the turn had started.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
