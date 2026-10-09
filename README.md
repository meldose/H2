# Unitree H2 workspace

Docker-based ROS 2 workspace for the Unitree H2 robot. It supports MuJoCo,
RViz/MoveIt visualization, read-only state viewing, and deliberately guarded
real-robot joint commands.

## Layout

| Path | Purpose |
| --- | --- |
| `docker/` | Image definitions, container runner, host setup, and robot bootstrap |
| `src/` | ROS 2 packages (`h2_description`, `h2_moveit_config`, `h2_bridge`) |
| `tmux/` | tmuxp sessions and real-robot network configuration |
| `scripts/` | Simulation, visualization, and robot-control tools |
| `tests/` | Offline tests; never send DDS commands |
| `docs/` | Simulation and real-arm operating instructions |

## Required companion workspaces

Clone `unitree_ros2` and `unitree_mujoco` beside this repository. The container
runner mounts both as siblings because their upstream setup scripts require
those paths. The included `h2_description` package supports the static RViz
viewer; add `h2_moveit_config` and `h2_bridge` under `src/` for the MoveIt and
live-state sessions.

## First-time setup

```bash
./docker/host_setup.sh
```

This builds the base and project images. For a simulator session, use:

```bash
./scripts/launch_h2.sh
```

Or load a session directly:

```bash
tmuxp load tmux/h2_example.tmuxp.yaml
```

See [the runbook](docs/RUNBOOK.md), [simulated motion](docs/SIMULATED_MOTION.md),
and [real-arm control](docs/REAL_ARM_CONTROL.md) for operating details.

## Safety

All real-H2 command scripts are read-only unless their explicit execution flag
is supplied. Validate network interface, mode, clear workspace, and the
documented physical-safety procedure before enabling any real motion.
