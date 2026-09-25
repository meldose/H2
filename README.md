# H2 arm control and RViz feedback

`command_h2_arm.py` and `h2_small_joint_test.py` command the **real H2 arm**.
`h2_rviz_bridge.py` only reads measured arm positions from `rt/lowstate` and
publishes them as ROS 2 `sensor_msgs/msg/JointState` on `/joint_states`. Run the
bridge while a controller is active to see the actual arm motion in RViz.

## Connect RViz to the real arm

1. On the machine connected to the H2, install `unitree_sdk2py` and source a
   ROS 2 environment with `rclpy`, `sensor_msgs`, `robot_state_publisher`, and
   RViz 2 available.
2. Load a matching H2 URDF into `robot_state_publisher`. Its 14 arm joint names
   must match `ARM_NAMES` in `command_h2_arm.py`. The URDF is **not included** in
   this repository. The real arm controller also expects it at
   `src/h2_description/urdf/h2.urdf` for limit checks.
3. In one terminal, run:

   ```bash
   python3 h2_rviz_bridge.py --interface enp6s0
   ```

4. In RViz, add **RobotModel**, select the same robot description used by
   `robot_state_publisher`, and set the Fixed Frame to the URDF root frame.
   Check that `ros2 topic echo /joint_states --once` reports the arm joints.
5. In another terminal, run a read-only check and then, when ready, the small
   real-robot motion:

   ```bash
   python3 h2_small_joint_test.py --interface enp6s0
   python3 h2_small_joint_test.py --interface enp6s0 --execute
   ```

Replace `enp6s0` with the interface connected to your H2. The bridge shows
**measured motion**, so it also reflects tracking errors or a stopped arm.

If your existing H2 bridge already publishes `/joint_states`, use that instead
of starting `h2_rviz_bridge.py`; two publishers for the same joints will make
the displayed pose jump. This bridge publishes only the 14 arm joints. A full
H2 model also needs joint states for its other moving joints from your existing
setup. RViz displays those states; it does not simulate physics or control the
robot.
