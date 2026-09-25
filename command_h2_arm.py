#!/usr/bin/env python3
"""Move one real H2 arm joint and return; view measured motion with h2_bridge.

Protocol reference: unitree_sdk2_python/example/h2/high_level/
h2_arm_sdk_dds_example.py. Only rt/arm_sdk is written, on DDS domain 0.
"""
import argparse
import fcntl
import math
from pathlib import Path
import signal
import sys
import threading
import time
import xml.etree.ElementTree as ET


ARM_NAMES = tuple(
    f"{side}_{part}_joint"
    for side in ("left", "right")
    for part in ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
                 "wrist_roll", "wrist_pitch", "wrist_yaw")
)
ARM_IDS = dict(zip(ARM_NAMES, range(15, 29)))
URDF = Path(__file__).parent / "src/h2_description/urdf/h2.urdf"
STALE_SECONDS = 0.25
MAX_STEP = math.radians(30)
MAX_SPEED = math.radians(20)
TRACKING_LIMIT = math.radians(20)


def joint_limits():
    root = ET.parse(URDF).getroot()
    return {
        name: tuple(float(root.find(f"joint[@name='{name}']/limit").get(key))
                    for key in ("lower", "upper"))
        for name in ARM_NAMES
    }


def plan(start, joint, degrees, relative, duration, limits):
    if joint not in ARM_IDS:
        raise ValueError("Only the 14 arm joints are supported")
    if not math.isfinite(degrees) or not math.isfinite(duration) or duration < 1:
        raise ValueError("Angle must be finite; duration must be at least 1 second")
    if len(start) != 14 or not all(math.isfinite(q) for q in start):
        raise ValueError("Invalid arm feedback")
    for name, q in zip(ARM_NAMES, start):
        lo, hi = limits[name]
        if not lo <= q <= hi:
            raise ValueError(f"Measured {name} is outside URDF limits")
    index = ARM_IDS[joint] - 15
    target = list(start)
    target[index] = math.radians(degrees) + (start[index] if relative else 0)
    lo, hi = limits[joint]
    if not lo <= target[index] <= hi:
        raise ValueError(f"Target exceeds {joint} limits: {math.degrees(lo):.1f} to "
                         f"{math.degrees(hi):.1f} degrees")
    step = abs(target[index] - start[index])
    if step > MAX_STEP + 1e-9:
        raise ValueError("Use a target within 30 degrees of the measured position")
    if 1.5 * step / duration > MAX_SPEED + 1e-9:
        raise ValueError("Increase --duration: peak command speed exceeds 20 degrees/s")
    return target


def interpolate(start, target, fraction):
    u = min(1.0, max(0.0, fraction))
    u = u * u * (3 - 2 * u)
    return [a + (b - a) * u for a, b in zip(start, target)]


class Feedback:
    def __init__(self):
        self.lock = threading.Lock()
        self.q = None
        self.received = 0.0

    def update(self, msg):
        try:
            q = [msg.motor_state[i].q for i in range(15, 29)]
            if not all(math.isfinite(v) for v in q):
                return
        except (IndexError, AttributeError, TypeError):
            return
        with self.lock:
            self.q, self.received = q, time.monotonic()

    def read(self):
        with self.lock:
            if self.q is None or time.monotonic() - self.received > STALE_SECONDS:
                raise RuntimeError("No fresh robot feedback; stopping arm commands")
            return list(self.q)


def check_mode(loco):
    code, mode = loco.GetFsmId()
    if code != 0 or mode not in (4, 703):
        raise RuntimeError(f"Arm SDK requires H2 mode 4 or 703; got {mode}, code {code}. "
                           "Set the appropriate robot mode using its normal controller first.")


def run(args):
    # Lazy imports allow --help, --list and offline tests without ROS or DDS.
    from unitree_sdk2py.core.channel import (
        ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber)
    from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient
    from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
    from unitree_sdk2py.utils.crc import CRC

    ChannelFactoryInitialize(0, args.interface)
    feedback = Feedback()
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(feedback.update, 1)
    loco = LocoClient()
    loco.SetTimeout(2.0)
    loco.Init()
    pub = None
    attempted_enable = False
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                start = feedback.read()
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        check_mode(loco)
        code, enabled = loco.GetArmSdkStatus()
        if code != 0 or type(enabled) is not bool:
            raise RuntimeError(f"Cannot read Arm SDK status: status={enabled}, code={code}")
        # This is an enable flag, not ownership or DDS publisher discovery.
        print(f"Arm SDK enabled: {enabled}. Run only one arm controller.", flush=True)
        start = feedback.read()
        target = plan(start, args.joint, args.degrees, args.relative, args.duration, joint_limits())
        i = ARM_IDS[args.joint] - 15
        print(f"{args.joint}: {math.degrees(start[i]):.1f} -> "
              f"{math.degrees(target[i]):.1f} degrees; return after {args.hold:g}s hold.", flush=True)
        if args.check:
            print("Check passed. No commands sent; Arm SDK setting unchanged.")
            return

        pub = ChannelPublisher("rt/arm_sdk", LowCmd_)
        pub.Init()
        cmd = unitree_hg_msg_dds__LowCmd_()
        crc = CRC()
        attempted_enable = True
        # Call this directly: older EnableArmSDK wrappers discard return codes.
        code = loco.SetArmSdkStatus(True)
        if code != 0:
            raise RuntimeError(f"Failed to enable Arm SDK: {code}")
        # The enable RPC can take time; capture and validate again before publishing.
        start = feedback.read()
        target = plan(start, args.joint, args.degrees, args.relative, args.duration, joint_limits())
        last = list(start)

        def publish(q, weight):
            actual = feedback.read()
            if max(abs(a - b) for a, b in zip(actual, last)) > TRACKING_LIMIT:
                raise RuntimeError("Arm tracking error exceeds 20 degrees; releasing control")
            for index, value in zip(range(15, 29), q):
                motor = cmd.motor_cmd[index]
                motor.q, motor.dq, motor.tau = value, 0.0, 0.0
                motor.kp, motor.kd = 80.0, 1.5
            cmd.motor_cmd[31].q = weight
            cmd.crc = crc.Crc(cmd)
            if pub.Write(cmd) is False:
                raise RuntimeError("DDS command write failed")
            last[:] = q

        def phase(a, b, duration, w0=1.0, w1=1.0):
            began = time.monotonic()
            previous = began
            while True:
                now = time.monotonic()
                if now - previous > STALE_SECONDS:
                    raise RuntimeError("Command loop stalled; releasing control")
                previous = now
                fraction = min(1.0, (now - began) / duration)
                publish(interpolate(a, b, fraction), w0 + (w1 - w0) * fraction)
                if fraction >= 1.0:
                    break
                time.sleep(0.02)

        print("Taking arm control; keep the arm workspace clear and remote stop available.", flush=True)
        phase(start, start, 1.0, 0.0, 1.0)
        phase(start, target, args.duration)
        phase(target, target, args.hold)
        measured = feedback.read()[i]
        if abs(measured - target[i]) > math.radians(5):
            raise RuntimeError("Joint did not reach target within 5 degrees; releasing control")
        print(f"Measured target position: {math.degrees(measured):.1f} degrees. Returning.", flush=True)
        phase(target, start, args.duration)
        phase(start, start, 1.0, 1.0, 0.0)
    finally:
        # On stale feedback/error/interruption, do not keep streaming stale positions.
        # Hand control back through the RPC even if the enable acknowledgement was lost.
        try:
            if attempted_enable:
                code = loco.SetArmSdkStatus(False)
                if code != 0:
                    raise RuntimeError(f"Arm SDK release failed ({code}); use the robot controller")
                print("Arm SDK released.", flush=True)
        finally:
            if pub is not None:
                pub.Close()
            sub.Close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("joint", nargs="?", choices=ARM_NAMES)
    parser.add_argument("degrees", nargs="?", type=float)
    parser.add_argument("--interface", help="Ethernet interface connected to the real H2")
    parser.add_argument("--relative", action="store_true", help="Degrees relative to measured starting angle")
    parser.add_argument("--duration", type=float, default=3.0, help="Seconds for each outward/return motion")
    parser.add_argument("--hold", type=float, default=3.0, help="Seconds to hold before returning (0.1 to 60)")
    parser.add_argument("--check", action="store_true", help="Read feedback and validate; send no commands")
    parser.add_argument("--list", action="store_true", help="List arm joints and URDF angle limits, offline")
    args = parser.parse_args(argv)
    if args.list:
        for name, (lo, hi) in joint_limits().items():
            print(f"{name:30s} {math.degrees(lo):7.1f} .. {math.degrees(hi):7.1f} deg")
        return 0
    if args.joint is None or args.degrees is None or not args.interface:
        parser.error("joint, degrees and --interface are required")
    if not all(math.isfinite(x) for x in (args.degrees, args.duration, args.hold)):
        parser.error("All numeric arguments must be finite")
    if not 1 <= args.duration <= 60 or not 0.1 <= args.hold <= 60:
        parser.error("--duration must be 1..60 seconds; --hold must be 0.1..60 seconds")
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        # Prevent two copies on this host; external controllers must be stopped separately.
        with open("/tmp/h2_arm_command.lock", "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another H2 arm command is already running on this host")
            run(args)
    except KeyboardInterrupt:
        print("Interrupted; no further joint trajectory will be sent.", file=sys.stderr)
        return 130
    except (RuntimeError, ValueError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
