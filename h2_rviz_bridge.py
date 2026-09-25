#!/usr/bin/env python3
"""Mirror measured H2 arm joint positions to ROS 2 for RViz.

This process only subscribes to Unitree lowstate and publishes ROS JointState.
It never sends a command to the robot.
"""

import argparse
import sys

from command_h2_arm import ARM_NAMES, Feedback


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", required=True,
                        help="Network interface connected to the H2, e.g. enp6s0")
    parser.add_argument("--topic", default="/joint_states",
                        help="ROS JointState output topic (default: /joint_states)")
    args = parser.parse_args(argv)

    try:
        import rclpy
        from sensor_msgs.msg import JointState
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    except ImportError as exc:
        parser.exit(1, f"Missing ROS 2 or Unitree SDK dependency: {exc}\n")

    ChannelFactoryInitialize(0, args.interface)
    feedback = Feedback()
    subscriber = ChannelSubscriber("rt/lowstate", LowState_)
    rclpy.init()
    node = rclpy.create_node("h2_arm_rviz_bridge")
    publisher = node.create_publisher(JointState, args.topic, 10)
    waiting = True

    def publish_feedback():
        nonlocal waiting
        try:
            positions = feedback.read()
        except RuntimeError:
            if not waiting:
                node.get_logger().warn("H2 feedback stopped; joint state publishing paused")
            waiting = True
            return
        if waiting:
            node.get_logger().info("Receiving H2 arm feedback")
            waiting = False
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.name = list(ARM_NAMES)
        message.position = positions
        publisher.publish(message)

    try:
        subscriber.Init(feedback.update, 1)
        node.create_timer(0.05, publish_feedback)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        subscriber.Close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
