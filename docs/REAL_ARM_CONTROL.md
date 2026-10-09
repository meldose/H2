# Real H2 arm commands with live RViz

`command_h2_arm.py` sends a joint target to the real H2 using `rt/arm_sdk` by default
(or `rt/lowcmd` with `--topic lowcmd`)
on DDS domain 0. The existing RViz bridge displays measured joint positions
from `rt/lowstate`. No MuJoCo installation is needed for this live 3D display.

The command supports the 14 arm joints, head pitch/yaw (IDs 29/30), and
three waist joints on either topic. With `--topic lowcmd`, it also supports
12 leg joints. Leg commands are rejected on `arm_sdk`. It uses the H2 protocol in the
[official arm example](https://github.com/unitreerobotics/unitree_sdk2_python/blob/master/example/h2/high_level/h2_arm_sdk_dds_example.py).
This implementation has offline tests, but has not been tested on hardware.

## Start the screen display

On the host, set the Ethernet interface connected to H2 in
`tmux/h2_interface.env` (currently `eth0`). An external workstation needs a
robot-network address, as described in `docs/RUNBOOK.md`.

```bash
cd ~/ros2/h2_ws
nano tmux/h2_interface.env
tmuxp load tmux/h2_rviz_live_real.tmuxp.yaml
```

This starts the workspace container and RViz. The robot model follows real
joint feedback; its base is fixed in the RViz scene. It is a live visualizer,
not a separate physics simulation. Do not run the static joint slider demo or
MoveIt fake execution alongside this view, since they publish different joint
states.

## Send a command

### Interactive joint menu

From this directory on the robot host:

```bash
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/h2_joint_cli.py --interface eth0
```

The menu labels 19 arm/head/waist joints by default, or all 31 joints with
`--topic lowcmd`, and displays their URDF angle limits. Existing menu numbers
1–16 are unchanged. On `arm_sdk`, waist roll/pitch/yaw are 17–19.
On `lowcmd`, legs are 17–28 and waist roll/pitch/yaw are 29–31.
Select a joint, choose a relative change or absolute angle, and enter movement
and hold times. Each adjustment holds the requested pose briefly, returns to
the measured starting pose, and releases control before displaying the menu
again. Add `--check` to validate selections without publishing commands.
Press `q` at the menu to quit; Ctrl+C during movement requests release.

The controller ramps SDK blending and motor gains over one second during
takeover and release. Positions follow cubic smoothstep interpolation with
zero endpoint velocity. Existing 30-degree step and 20-degree/second peak
speed limits, live feedback checks, joint limits, and mode 4/703 checks apply.
Both arms are held while the selected joint moves. These safeguards do not
perform collision checking. Gains and trajectories have offline test coverage;
the updated ramp has not been validated on hardware.

The default `arm_sdk` backend rejects mode 601; change to a supported mode using
the normal robot controller before requesting Arm SDK motion.

### Optional lowcmd topic

Select the low-level backend in the same menu:

```bash
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/h2_joint_cli.py --interface eth0 --topic lowcmd --check
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/h2_joint_cli.py --interface eth0 --topic lowcmd
```

The direct command also accepts `--topic lowcmd`. Physically support/suspend the
robot and release its normal motion service using the established robot procedure
before using this backend. The tool checks that MotionSwitcher reports an empty
active mode name and refuses active or unreadable status; it does not release the
service automatically. Stop all other command publishers. Lowcmd does not maintain
standing balance. Motors outside the commanded group have mode and gains zero.
Arm selections command both arms; head selections additionally command both head
joints. Leg or waist selections command both legs and all three waist joints,
holding every other joint in that group at its measured starting position.
Arms/head are uncommanded during leg/waist adjustments.

This backend uses `mode_pr=0`, `mode_machine` from fresh feedback, motor `mode=1`
for commanded joints, CRC, and a 2 ms requested loop period (Python timing is not
hard real time). It ramps gains, retains trajectory/feedback checks, and does not
write the Arm SDK blend slot or call Arm SDK RPCs. `--check` sends no commands.
Normal completion ramps gains to zero; errors/interruption stop publishing.
The motion service remains inactive on exit, so keep physical support in place.

The installed H2 low-level example maps wrist yaw/pitch/roll to IDs 19/20/21
and 26/27/28; its Arm SDK example maps roll/pitch/yaw to those IDs. Each backend
uses its corresponding example's mapping. Verify this against the robot firmware
before wrist motion. This backend has offline coverage only; hardware behavior
and the cause of the original lack of motion have not been verified.

For a smaller first test, `h2_small_joint_test.py` defaults to a read-only
check and limits relative arm motion to 2 degrees. It uses
`command_h2_arm.py` from the same directory:

```bash
python3 scripts/h2_small_joint_test.py --interface enp6s0
# Only after the check succeeds, to command real motion:
python3 scripts/h2_small_joint_test.py --interface enp6s0 --execute
```

Execution moves the left elbow by +2 degrees over 5 seconds, holds for 1
second, then returns over 5 seconds. Both arms are held during the test.
Use `--joint right_elbow_joint` to choose a different arm joint, or
`--degrees -2` to reverse direction. Joint limits, feedback checks and the
mode 4/703 restriction still apply. Mode 601 is not enabled by this wrapper;
it does not change robot modes. A smaller motion does not provide collision
checking or validate a mode transition for a freely standing robot.

In another host terminal, enter the same container:

```bash
docker exec -it h2_ws_container bash
cd ~/h2_ws
source tmux/h2_interface.env
python3 scripts/command_h2_arm.py --list
```

Have the robot in its normal supported standing mode, with the arm workspace
clear and its remote stop available. Stop other arm SDK/low-level controllers.
The tool checks mode 4 or 703, but does not change robot mode or stand it up.
Joint limits alone do not prevent collisions with the body or surroundings.

First read the real position and validate a 10-degree relative elbow target
without enabling control or publishing motor commands:

```bash
python3 scripts/command_h2_arm.py left_elbow_joint 10 --relative \
  --interface "$H2_INTERFACE" --check
```

Then execute that motion:

```bash
python3 scripts/command_h2_arm.py left_elbow_joint 10 --relative \
  --interface "$H2_INTERFACE" --duration 3 --hold 3
```

Both arms are held at their measured starting positions while the selected
joint moves. It moves over 3 seconds, holds for 3 seconds, returns over 3
seconds, then releases arm SDK control. RViz follows the measured movement.
The tool also reports the measured target position. Without `--relative`, the
angle is an absolute joint angle in degrees; for example:

```bash
python3 scripts/command_h2_arm.py left_elbow_joint 30 \
  --interface "$H2_INTERFACE" --duration 3 --hold 5
```

Each command is limited to a 30-degree change and 20 degrees/second peak
command speed, and checked against the local URDF limits. The arm gains match
Unitree's example (kp=80, kd=1.5). These are command bounds, not a guarantee of
collision-free or hardware-safe movement in every pose.

Ctrl+C cancels the trajectory and requests release to the built-in controller;
it does not finish the return motion and is not a hardware emergency stop.
Missing/stale feedback, tracking error, DDS write failure or a stalled loop
also aborts and requests release. Network loss or forced process termination
can prevent release; use the normal robot remote if needed. The local lock
prevents two copies of this tool on the same host, not other DDS publishers.

## Additional individual motions

Keep `h2_motion_common.py` and `command_h2_arm.py` alongside these scripts:

| Script | Joint |
| --- | --- |
| `h2_motion_left_elbow.py` | Left elbow |
| `h2_motion_right_elbow.py` | Right elbow |
| `h2_motion_left_wrist.py` | Left wrist roll |
| `h2_motion_right_wrist.py` | Right wrist roll |

All default to a read-only check and a +2-degree relative target. `--degrees`
accepts a signed change of up to 10 degrees. Start with the small default to
observe the joint's positive direction. These are individual joint motions,
not coordinated waving, Cartesian hand movement or finger/gripper control.

```bash
python3 scripts/h2_motion_right_elbow.py --interface enp6s0
# After a successful check and clearing the motion path:
python3 scripts/h2_motion_right_elbow.py --interface enp6s0 --execute
```

For a larger wrist-roll test, first check the requested angle:

```bash
python3 scripts/h2_motion_left_wrist.py --interface enp6s0 --degrees 5
python3 scripts/h2_motion_left_wrist.py --interface enp6s0 --degrees 5 --execute
```

Motion takes 5 seconds, holds 2 seconds and returns over 5 seconds. Both arms
are held at their initial angles except for the requested joint. Run one
motion process at a time. Existing mode/feedback checks remain active; these
scripts do not switch modes or implement collision checking. Live RViz shows
the measured joint state. These scripts have offline tests only.

## Troubleshooting

- `No module named unitree_sdk2py`: use the workspace container, whose Dockerfile
  installs the SDK. The host's Python may not have it installed.
- `No fresh robot feedback`: check the Ethernet interface, robot connection and
  DDS domain. The command always uses domain 0.
- Unsupported mode or SDK RPC failure: verify robot firmware/SDK compatibility.
  Topic selection is explicit; there is no automatic fallback to `rt/lowcmd`.
- An enabled Arm SDK flag does not identify another controller. Stop other arm
  command publishers yourself; this tool cannot discover ownership from that flag.
  Execution disables Arm SDK on exit, including when it was already enabled;
  `--check` leaves the setting unchanged.
- Target rejected: inspect `--list`, reduce the angle or increase `--duration`.

Offline tests (no DDS communication):

```bash
cd ~/ros2/h2_ws
python3 -m unittest -v test_command_h2_arm
```

Head selections command both arms and both head joints through `rt/arm_sdk`,
using head gains kp=30, kd=1, ramped with SDK blending. Other commanded joints
hold their measured starting positions. Arm selections retain the existing
14-motor behavior. Head motion has offline coverage only, not hardware validation.

### Leg and waist adjustments (lowcmd only)

```bash
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/command_h2_arm.py --topic lowcmd --list
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/command_h2_arm.py left_knee_joint 2 --relative --duration 5 --interface eth0 --topic lowcmd --check
```

Remove `--check` to execute after preparing the supported robot and releasing the
motion service. The interactive menu accepts the same topic option. Each movement
returns to its measured starting pose and ramps gains down before stopping.

The mapping follows the installed H2 low-level example: left leg IDs 0–5,
right leg IDs 6–11, each ordered hip pitch/roll/yaw, knee, ankle roll/pitch;
waist roll/pitch/yaw are IDs 12/13/14 in PR mode (`mode_pr=0`). The waist mapping
is explicit, not inferred from URDF file order. Leg/waist gains follow that
example and ramp over one second during takeover/release. Joint limits, the
30-degree step limit, 20-degree/second peak speed limit, and feedback checks apply.
Verify firmware-specific mappings before hardware use. These changes have only
been tested offline and do not implement balance or collision checking.


### Waist adjustments through Arm SDK

```bash
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/h2_joint_cli.py --interface eth0 --topic arm_sdk
# Read-only direct check:
PYTHONPATH=/home/unitree/unitree_sdk2_python python3 scripts/command_h2_arm.py waist_yaw_joint 2 --relative --duration 5 --interface eth0 --topic arm_sdk --check
```

Waist selections hold both arms and all three waist joints while moving the
selected joint, then return and release Arm SDK control. Legs and head receive
no commands from this selection. Existing mode 4/703, feedback, limits, gain
ramps, SDK blending and enable/release checks still apply.

The installed Arm SDK example declares waist yaw/roll/pitch IDs 12/13/14;
this differs from the lowcmd example's roll/pitch/yaw mapping. Each backend uses
its corresponding mapping for both feedback and commands. Waist gains are
kp=200, with kd=2.5 for roll and 5 for pitch/yaw, taken from the low-level example
and ramped with SDK weight. The Arm SDK example demonstrates arm motion only;
its waist constants do not establish firmware acceptance of waist commands.
This extension has offline test coverage only. Actual waist response through
Arm SDK and these gains have not been validated on hardware.
