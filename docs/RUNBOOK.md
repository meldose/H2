# H2 Simulation — Runbook

Command reference only. Background/reasoning: `~/Notes/Unitree_H2_Setup.md` (Obsidian).

## Quick start (tmuxp)

```bash
cd ~/ros2/h2_ws
tmuxp load tmux/h2_example.tmuxp.yaml
```

Opens 3 windows (`ctrl-b` then a number to switch, or `ctrl-b w` to list):
- **simulator** — starts the container, then MuJoCo (H2 loaded, GUI window opens)
- **control** — waits for the container, attaches with `ROS_DOMAIN_ID=1` already set, and pre-fills the ankle-swing `ros2 run` command on the prompt (`tmux/control_entrypoint.sh`) — just press Enter to run it as-is, or edit the line first
- **monitor** — same env setup as control, free for `ros2 topic echo`/`hz` etc.

One-time setup needed before this works (see below if not done yet): `unitree_ros2`/`unitree_mujoco` cloned, message packages built, `config.yaml` set.

Other tmuxp sessions in this folder — each is self-contained (starts its own container, and its own MuJoCo sim if it needs one; no other session has to be running first):
- `h2_dds_test.tmuxp.yaml` — sim + a raw Python DDS test (`test_unitree_sdk2_h2.py`) printing SportModeState/LowState; also publishes a small constant leg torque, so don't run it alongside `control` above.
- `h2_state_viewer_real.tmuxp.yaml` — `view_h2_real_state.py`'s read-only MuJoCo viewer, pointed at the real robot (see § Real robot below); interface name set in `h2_interface.env`. No sim counterpart — against the sim it just duplicated the sim's own MuJoCo window (see `h2_rviz_live_sim.tmuxp.yaml` for a live sim view instead).
- `h2_rviz_static.tmuxp.yaml` — RViz + H2's URDF (`src/h2_description`), driven by manual `joint_state_publisher_gui` sliders, no sim/real connection.
- `h2_rviz_live_sim.tmuxp.yaml` — sim + RViz driven by that sim's real joint data (`h2_bridge`'s `joint_state_bridge`, read-only).
- `h2_rviz_live_real.tmuxp.yaml` — same, pointed at the real robot; interface name set in `h2_interface.env`.
- `h2_moveit_demo.tmuxp.yaml` — MoveIt 2 RViz demo for H2's arms (`src/h2_moveit_config`), fake-execution only — not connected to sim or the real robot, see that file's own header comment.

## Manual step-by-step (what the tmuxp file automates)

**Terminal 1 — simulator:**
```bash
cd ~/ros2/h2_ws
./docker/run_container.sh
./scripts/run_unitree_mujoco.sh
```
In the GUI window (click in first): `9` = toggle elastic band, `8`/`7` = raise/lower. H2 collapses immediately without the band active.

**Terminal 2+ — control/monitor, same running container:**
```bash
docker exec -it h2_ws_container bash
source ~/unitree_ros2/setup_local.sh
export ROS_DOMAIN_ID=1
```

## Common commands, once in a control/monitor shell

```bash
ros2 topic list
ros2 topic echo /lowstate
ros2 topic hz /lowcmd

# Move the robot (remap flags required — see Known issues). Also runs
# automatically pre-filled in the tmuxp "control" window.
source ~/unitree_ros2/example/install/setup.bash   # only needed for `ros2 run`
ros2 run unitree_ros2_example h2_ankle_swing_example --ros-args \
  --remap rt/lowcmd:=lowcmd \
  --remap rt/lowstate:=lowstate \
  --remap rt/secondary_imu:=secondary_imu
```

## One-time setup (only if unitree_ros2/unitree_mujoco aren't set up yet)

```bash
cd ~/ros2
git clone https://github.com/unitreerobotics/unitree_ros2.git
git clone https://github.com/unitreerobotics/unitree_mujoco.git

sed -i 's|/opt/ros/foxy|/opt/ros/humble|' \
  ~/ros2/unitree_ros2/setup.sh ~/ros2/unitree_ros2/setup_local.sh ~/ros2/unitree_ros2/setup_default.sh
# in config.yaml: robot: "h2"  and  enable_elastic_band: 1
```

Then, inside the container:
```bash
cd ~/unitree_ros2/cyclonedds_ws && colcon build
cd ~/unitree_ros2/example && colcon build

ln -sfn ~/.mujoco/mujoco-3.3.6 ~/unitree_mujoco/simulate/mujoco
cd ~/unitree_mujoco/simulate && mkdir build && cd build && cmake .. && make -j$(nproc)
```

## Known issues (don't re-debug these)

- `ros2 run unitree_ros2_example h2_ankle_swing_example` originally failed — the package's `CMakeLists.txt` has a real bug (a batch `install(TARGETS ... DESTINATION)` with no path after `DESTINATION`, and several bare `install(TARGETS <name>)` calls with no destination at all — affects more than just H2's targets). Executables land in `bin/` instead of the `lib/<package>/` path `ros2 run` searches. **Fixed** without touching Unitree's `CMakeLists.txt` or rebuilding: a relative symlink was added at `~/unitree_ros2/example/install/unitree_ros2_example/lib/unitree_ros2_example/h2_ankle_swing_example` → `../../bin/h2_ankle_swing_example`. Must be a *relative* symlink — an absolute host-path symlink resolves to nothing inside the container (bind-mount path differs). If this ever needs redoing (e.g. after a clean rebuild wipes `install/`):
  ```bash
  mkdir -p ~/unitree_ros2/example/install/unitree_ros2_example/lib/unitree_ros2_example
  ln -sfn ../../bin/h2_ankle_swing_example \
    ~/unitree_ros2/example/install/unitree_ros2_example/lib/unitree_ros2_example/h2_ankle_swing_example
  ```
- `h2_ankle_swing_example` needs the `--remap` flags above — it's a real bug in that specific file (hardcodes an already-DDS-mangled topic name), not fixed upstream, not touched here since it's Unitree's file.
- The whole settle+swing sequence is a **one-shot 6 seconds** (3s settle, 3s swing), then it holds `q=0` forever at full PD gains (mode stays active — it doesn't go limp). If you look away and come back later, "just standing there" is the *expected* end state, not a failure — restart the node to see the motion again, and watch continuously.
- Don't run the raw `unitree_mujoco` binary directly — use `./scripts/run_unitree_mujoco.sh`, or it crashes on a CycloneDDS library conflict with ROS's auto-sourced environment.
- `ROS_DOMAIN_ID` must be `1` for simulation (matches MuJoCo's `config.yaml`), default `0` for the real robot.

## Real robot (not simulation)

To send an arm joint command to the real H2 and watch measured movement in
RViz, see [Real arm control](REAL_ARM_CONTROL.md). The live RViz session
remains read-only; `command_h2_arm.py` is the separate command process.

```bash
ip a   # find the interface after connecting the Ethernet cable
# set that interface's IPv4 manually: 192.168.123.99 / 255.255.255.0, on the HOST
# edit ~/unitree_ros2/setup.sh: NetworkInterface name="<real interface>"

source ~/unitree_ros2/setup.sh    # not setup_local.sh
# ROS_DOMAIN_ID left at default (0)
ros2 topic list
```
