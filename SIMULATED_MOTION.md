# H2 arm motion in RViz

Run these commands inside the workspace ROS environment (or its Docker container).
The launcher builds the description/config packages and starts mock ros2_control
hardware, both arm trajectory controllers, robot_state_publisher, and RViz.
All new controllers and feedback use the `/h2_sim` namespace.

Terminal 1:

```bash
bash ./run_h2_rviz_sim.sh
```

Terminal 2, from this directory:

```bash
source /opt/ros/humble/setup.bash  # use jazzy instead if your container runs Jazzy
source install/h2_rviz_sim/setup.bash
python3 h2_sim_motion.py --arm left --joint elbow --degrees 20
python3 h2_sim_motion.py --arm right --joint elbow --degrees 20
python3 h2_sim_motion.py --arm left --joint wrist_roll --degrees 15 --repeat 3
python3 h2_sim_motion.py --arm right --joint wrist_roll --degrees -15
```

Each command reads the current simulated arm pose, moves one joint smoothly,
holds, and returns. Other joints in that arm hold their starting positions.
Use `--duration 5 --hold 2` to change timing; `--help` lists all supported joints.
Targets are checked against the H2 URDF limits. Run one command per arm at a time.
Ctrl+C cancels the active trajectory; cancellation does not perform a return motion.

These are joint trajectories through mock hardware, not collision-checked MoveIt
plans or a MuJoCo physics simulation. They do not move the physical H2. The existing
`command_h2_arm.py` and `REAL_ARM_CONTROL.md` cover physical arm commands;
`h2_bridge h2_live_launch.py` displays physical or MuJoCo telemetry.

For headless controller testing, launch with `rviz:=false`.

Run the launcher with `bash`, not `.` or `source`: it replaces its own process
with ROS launch. It uses separate `build/h2_rviz_sim` and `install/h2_rviz_sim`
directories and refreshes the CMake cache, so build artifacts copied from another
workspace path do not prevent the simulation packages from building.
