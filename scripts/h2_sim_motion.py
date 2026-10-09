#!/usr/bin/env python3
"""Execute an arm joint trajectory on the isolated H2 RViz mock controllers."""
import argparse
import math
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

PARTS = ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
         'wrist_roll', 'wrist_pitch', 'wrist_yaw')
NAMESPACE = '/h2_sim'


def make_positions(start, joint_index, degrees, limits):
    target = list(start)
    target[joint_index] += math.radians(degrees)
    for value, (lower, upper) in zip(target, limits):
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError('Trajectory exceeds URDF joint limits')
    return target


def run(args):
    import rclpy
    from rclpy.action import ActionClient
    from control_msgs.action import FollowJointTrajectory
    from sensor_msgs.msg import JointState
    from trajectory_msgs.msg import JointTrajectoryPoint

    names = [f'{args.arm}_{part}_joint' for part in PARTS]
    workspace_root = Path(__file__).resolve().parents[1]
    root = ET.parse(workspace_root / 'src/h2_description/urdf/h2.urdf').getroot()
    limits = [tuple(float(root.find(f"joint[@name='{name}']/limit").get(key))
                    for key in ('lower', 'upper')) for name in names]
    rclpy.init()
    node = rclpy.create_node('h2_sim_motion')
    feedback = {}
    received = [0.0]
    goal_handle = None

    def update(msg):
        if all(name in msg.name for name in names) and len(msg.name) == len(msg.position):
            feedback.update(zip(msg.name, msg.position))
            received[0] = time.monotonic()

    subscription = node.create_subscription(JointState, NAMESPACE + '/joint_states', update, 10)
    client = ActionClient(node, FollowJointTrajectory,
                         f'{NAMESPACE}/{args.arm}_arm_controller/follow_joint_trajectory')

    def wait(future, seconds):
        rclpy.spin_until_future_complete(node, future, timeout_sec=seconds)
        if not future.done():
            raise RuntimeError('Timed out waiting for trajectory controller')
        return future.result()

    try:
        if not client.wait_for_server(timeout_sec=15):
            raise RuntimeError('Simulation controller unavailable. Start ./scripts/run_h2_rviz_sim.sh first.')
        deadline = time.monotonic() + 10
        while not all(name in feedback for name in names) or time.monotonic() - received[0] > 1:
            if time.monotonic() >= deadline:
                raise RuntimeError('No fresh simulation joint feedback')
            rclpy.spin_once(node, timeout_sec=0.1)
        start = [feedback[name] for name in names]
        # Validate both starting and target positions before sending a goal.
        make_positions(start, PARTS.index(args.joint), 0, limits)
        target = make_positions(start, PARTS.index(args.joint), args.degrees, limits)
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = names
        elapsed = 0.0
        phases = [(start, target, args.duration), (target, target, args.hold),
                  (target, start, args.duration)] * args.repeat
        for begin, end, duration in phases:
            # Sample smoothstep; zero endpoint velocities make each reversal smooth.
            steps = max(1, math.ceil(duration * 20))
            for index in range(1, steps + 1):
                fraction = index / steps
                blend = fraction * fraction * (3 - 2 * fraction)
                point = JointTrajectoryPoint()
                point.positions = [a + (b - a) * blend for a, b in zip(begin, end)]
                point.velocities = [(b - a) * 6 * fraction * (1 - fraction) / duration
                                    for a, b in zip(begin, end)]
                timestamp = round((elapsed + fraction * duration) * 1e9)
                point.time_from_start.sec, point.time_from_start.nanosec = divmod(timestamp, 10**9)
                goal.trajectory.points.append(point)
            elapsed += duration
        print(f'SIMULATION: {args.arm} {args.joint}, {args.degrees:g} degrees relative, '
              f'{args.repeat} cycle(s), returning to the starting pose.', flush=True)
        goal_handle = wait(client.send_goal_async(goal), 10)
        if not goal_handle.accepted:
            raise RuntimeError('Simulation controller rejected trajectory')
        result = wait(goal_handle.get_result_async(), elapsed + 10)
        if result.status != 4 or result.result.error_code != 0:
            raise RuntimeError(f'Trajectory failed: {result.result.error_string} (status {result.status})')
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if time.monotonic() - received[0] < 1 and all(
                    abs(feedback[name] - position) < 0.01 for name, position in zip(names, start)):
                print('Completed; joint feedback confirms return to the starting pose.')
                return
        raise RuntimeError('Controller completed but feedback did not confirm the return pose')
    finally:
        if goal_handle is not None and goal_handle.accepted:
            rclpy.spin_until_future_complete(node, goal_handle.cancel_goal_async(), timeout_sec=2)
        client.destroy()
        node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('left', 'right'), default='left')
    parser.add_argument('--joint', choices=PARTS, default='elbow')
    parser.add_argument('--degrees', type=float, default=20, help='Relative angle in degrees')
    parser.add_argument('--duration', type=float, default=3, help='Seconds each way')
    parser.add_argument('--hold', type=float, default=1)
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args(argv)
    if not all(math.isfinite(x) for x in (args.degrees, args.duration, args.hold)):
        parser.error('Numeric arguments must be finite')
    if not 0 < abs(args.degrees) <= 30 or not 1 <= args.duration <= 60:
        parser.error('Use a nonzero angle up to 30 degrees and duration 1..60 seconds')
    if not 0.1 <= args.hold <= 60 or not 1 <= args.repeat <= 20:
        parser.error('Hold must be 0.1..60 seconds and repeat 1..20')
    try:
        run(args)
    except KeyboardInterrupt:
        return 130
    except (ImportError, RuntimeError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
