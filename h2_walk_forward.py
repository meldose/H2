#!/usr/bin/env python3
"""Short, timed H2 forward-walk request."""
import argparse
from contextlib import ExitStack
import fcntl
import math
from pathlib import Path
import sys
import time


DEFAULT_SPEED_MPS = 0.5
MIN_SPEED_MPS = 0.05
MAX_SPEED_MPS = 0.5
DEFAULT_DURATION_SECONDS = 1.0
MIN_DURATION_SECONDS = 0.5
MAX_DURATION_SECONDS = 10.0
MAX_HIGH_SPEED_DURATION_SECONDS = 2.0
LEASE_SECONDS = 0.75
DISPLAY_UPDATE_SECONDS = 0.20


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="enp6s0",
                        help="H2 network interface on PC2 (default: enp6s0)")
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED_MPS,
                        help=f"Forward speed in m/s ({MIN_SPEED_MPS}..{MAX_SPEED_MPS}; default {DEFAULT_SPEED_MPS})")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_SECONDS,
                        help=f"Short burst duration in seconds ({MIN_DURATION_SECONDS}..{MAX_DURATION_SECONDS}; default {DEFAULT_DURATION_SECONDS})")
    parser.add_argument("--check", action="store_true",
                        help="Read controller status only; send no motion commands (default)")
    parser.add_argument("--execute", action="store_true",
                        help="After preflight and explicit confirmation, request timed forward motion")
    args = parser.parse_args(argv)
    if args.check and args.execute:
        parser.error("choose only one of --check and --execute")
    if not math.isfinite(args.speed) or not MIN_SPEED_MPS <= args.speed <= MAX_SPEED_MPS:
        parser.error(f"--speed must be between {MIN_SPEED_MPS} and {MAX_SPEED_MPS} m/s")
    if not math.isfinite(args.duration) or not MIN_DURATION_SECONDS <= args.duration <= MAX_DURATION_SECONDS:
        parser.error(f"--duration must be between {MIN_DURATION_SECONDS} and {MAX_DURATION_SECONDS} seconds")
    if args.speed > 0.15 and args.duration > MAX_HIGH_SPEED_DURATION_SECONDS:
        parser.error("speeds above 0.15 m/s are limited to 2 seconds")

    print("H2 forward locomotion — " + ("READ-ONLY" if not args.execute else "EXECUTION ARMED"))
    print(f"Short forward burst: {args.duration:.1f} s at {args.speed:.2f} m/s.")
    print("Step count depends on the robot's gait; this script controls velocity and time, not individual steps.")
    print("Use only on a flat, clear test area with a spotter and the robot's remote stop ready.")

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
                raise RuntimeError(f"Cannot read H2 locomotion state (code={code})")
            code, fsm_mode = loco.GetFsmMode()
            if code != 0 or fsm_mode is None:
                raise RuntimeError(f"Cannot read H2 locomotion mode (code={code})")
            fsm_name = None
            if hasattr(loco, "GetBalanceMode"):
                balance_code, balance_mode = loco.GetBalanceMode()
                print(f"Balance mode: {balance_mode if balance_code == 0 else 'unavailable'} (code={balance_code}).")
            if hasattr(loco, "GetAvailableFsmIds"):
                fsm_code, fsm_ids, fsm_names = loco.GetAvailableFsmIds()
                if fsm_code == 0:
                    states = dict(zip(fsm_ids, fsm_names))
                    fsm_name = states.get(fsm_id)
                    core_states = ((state_id, name) for state_id, name in states.items()
                                   if isinstance(state_id, int) and state_id < 1000)
                    print("Core FSM states: " + ", ".join(
                        f"{name}={state_id}" for state_id, name in core_states))
                else:
                    print(f"Available FSM states unavailable (code={fsm_code}).")
            code, arm_sdk_enabled = loco.GetArmSdkStatus()
            if code != 0 or type(arm_sdk_enabled) is not bool:
                raise RuntimeError(f"Cannot read Arm SDK status (code={code})")

            current_state = f" ({fsm_name})" if fsm_name else ""
            print(f"H2 reports FSM id={fsm_id}{current_state}, mode={fsm_mode}, Arm SDK enabled={arm_sdk_enabled}.")
            if arm_sdk_enabled:
                print("Arm SDK enable flag is on; it does not identify an active publisher. The local joint-command lock is held.")
            print("The H2 RPC routine documents SetVelocity directly; this script will not change the FSM.")
            if not args.execute:
                print("Check complete. No motion commands sent.")
                return 0

            print("Confirm: robot is upright and stationary in locomotion mode, path is clear, remote stop is ready, and no external motion controller is active.")
            if args.duration == 1.5 and args.speed == 0.10:
                confirmation_phrase = "WALK 3 STEPS"
            else:
                unit = "SECOND" if args.duration == 1.0 else "SECONDS"
                confirmation_phrase = f"WALK {args.duration:g} {unit}"
            confirmation = " ".join(input(f"Type {confirmation_phrase} to begin: ").upper().split())
            if confirmation != confirmation_phrase:
                print("Cancelled. No motion commands sent.")
                return 0

            command_attempted = False
            stop_failed = False
            try:
                print("Sending the documented timed SetVelocity request; showing commanded speed and estimated travel.",
                      flush=True)
                print("Travel is calculated from requested speed; it is not measured odometry.", flush=True)
                command_attempted = True
                code = loco.SetVelocity(args.speed, 0.0, 0.0, args.duration)
                if code != 0:
                    raise RuntimeError(f"Forward velocity request failed (code={code})")
                started = time.monotonic()
                next_update = 0.0
                while True:
                    elapsed = min(time.monotonic() - started, args.duration)
                    if elapsed >= next_update:
                        estimated_m = args.speed * elapsed
                        print(f"t={elapsed:4.1f}/{args.duration:.1f}s  commanded vx={args.speed:.2f} m/s  "
                              f"estimated travel={estimated_m:.2f} m (not measured)",
                              end="\r", flush=True)
                        next_update += DISPLAY_UPDATE_SECONDS
                    remaining = args.duration - elapsed
                    if remaining <= 0:
                        break
                    time.sleep(min(DISPLAY_UPDATE_SECONDS, remaining))
                print(flush=True)
                print(f"Forward velocity RPC accepted (code={code}); commanded {args.speed:.2f} m/s for {args.duration:.1f} s. "
                      "Actual speed and displacement are not measured.", flush=True)
            finally:
                if command_attempted:
                    try:
                        stop_code = loco.SetVelocity(0.0, 0.0, 0.0, LEASE_SECONDS)
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
            print("Timed burst finished. Check the robot's position before repeating.")
            return 0
    except KeyboardInterrupt:
        print("Interrupted; a zero-velocity request was attempted if motion had started.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
