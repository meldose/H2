"""Launch the H2 model in RViz with optional joint sliders."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory("h2_description"))
    robot_description = (share / "urdf" / "h2.urdf").read_text()
    gui = LaunchConfiguration("gui")

    return LaunchDescription([
        DeclareLaunchArgument("gui", default_value="true",
                              description="Show joint_state_publisher_gui sliders."),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             parameters=[{"robot_description": robot_description}]),
        Node(package="joint_state_publisher_gui", executable="joint_state_publisher_gui",
             condition=IfCondition(gui), parameters=[{"robot_description": robot_description}]),
        Node(package="joint_state_publisher", executable="joint_state_publisher",
             condition=UnlessCondition(gui), parameters=[{"robot_description": robot_description}]),
        Node(package="rviz2", executable="rviz2", arguments=["-d", str(share / "rviz" / "display.rviz")]),
    ])
