# AGENT.md

Guidance for AI coding agents (Claude Code, Cursor, Aider, …) working in this repository. Companion human-oriented document: [wiki/home.md](wiki/home.md).

## Project overview

Docker-based ROS 2 Jazzy workspace for working through the official ROS 2 tutorials. ROS 2 runs entirely inside the container; nothing ROS-related is installed on the host. Target platform AMD64 Linux; ARM64 (Jetson) and WSL2 supported via Docker. The workspace ships one example package, `hello_world`. Code, comments, and commit messages are English.

---

## Build / run

Standard colcon workspace. `build/`, `install/`, `log/` are generated; work in `src/`.

```bash
# Inside the container
colcon build
source install/setup.bash

# Single package
colcon build --packages-select hello_world
```

`source install/setup.bash` is required after every `colcon build` and in every new shell. The image auto-sources `/opt/ros/jazzy`, and the workspace overlay too once `install/` exists.

Run the example:

```bash
ros2 run hello_world talker
ros2 launch hello_world hello_world_launch.py
ros2 topic echo /hello_world
```

Submodules: `./docker/host_setup.sh` initializes them. Manual: `git submodule update --init --recursive --checkout`. Day-to-day bump of tracking submodules (wikis, docker_template): `git submodule update --remote --recursive` — leaves submodules on `main` because they carry `update = merge` in `.gitmodules`. Full contract: [Submodule Pinning Contract](wiki/wiki_robost/git/Submodule-Pinning-Contract.md).

---

## Docker

```bash
./docker/host_setup.sh        # first-time setup: submodules + Docker + image build
./docker/run_container.sh     # start the container (auto-detects amd64 / arm64 / wsl)
```

The Docker setup uses the team's wrapper pattern over the [docker/docker_template](docker/docker_template/) submodule:

- [docker/docker_template/Dockerfile](docker/docker_template/Dockerfile) builds the shared base image `robost-ros2-base:jazzy`.
- [docker/Dockerfile](docker/Dockerfile) builds the project image `tutorial_ws_image` on top of it — adds `ros-jazzy-desktop`, `nano`, `mesa-utils`.
- [docker/host_setup.sh](docker/host_setup.sh) initializes the submodules, then calls the template; its `HOST_SETUP_CMD_*` hooks are empty (the tutorials need no host setup).
- [docker/run_container.sh](docker/run_container.sh) sources the template runner; its `EXTRA_DOCKER_ARGS_*` arrays are empty (the tutorials need no extra hardware).

Never run `apt-get upgrade` / `full-upgrade` in [docker/Dockerfile](docker/Dockerfile) — system updates belong in the base image. See [docker/docker_template/README.md](docker/docker_template/README.md).

---

## Architecture

One example package, one node. Edge list:

| From | Edge type | Identifier | To |
|---|---|---|---|
| `hello_world_publisher` | topic | `/hello_world` (`std_msgs/String`, 1 Hz) | any subscriber |

Mermaid version for humans: [wiki/home.md § Architecture](wiki/home.md#architecture).

---

## Packages by role

- **`hello_world`** (`ament_python`) — minimal example package. Entry points:
  - [src/hello_world/hello_world/publisher.py](src/hello_world/hello_world/publisher.py) — `HelloWorldPublisher`, publishes `std_msgs/String` on `/hello_world` at 1 Hz. Exposed as the console script `talker` (see [src/hello_world/setup.py](src/hello_world/setup.py)).
  - [src/hello_world/launch/hello_world_launch.py](src/hello_world/launch/hello_world_launch.py) — launches the `talker` executable.

New tutorial packages go under `src/` as independent colcon packages.

---

## Traps

- The image and container names (`tutorial_ws_image`, `tutorial_ws_container`) are derived from the workspace folder name by the `docker_template` scripts — renaming the folder changes both names.
- `build/`, `install/`, `log/` are colcon-generated and git-ignored — never edit them by hand or commit them.
- [docker/host_setup.sh](docker/host_setup.sh) initializes the submodules before running the template, because the template scripts live in the `docker/docker_template` submodule and do not exist after a non-recursive clone.
- The project [docker/Dockerfile](docker/Dockerfile) must not run `apt-get upgrade` — see [Docker](#docker).

---

## Commit / push policy

AI agents do not run `git commit` or `git push`, and do not ask to. An agent's work ends at changing the files; the developer reviews the diff and commits it, keeping control of what enters the history.

Do not announce or restate this policy in your responses — no closing notes about committing. Just leave the working tree modified. The developer knows.

The only exception is a direct, explicit instruction in the task itself — commit messages then follow [Conventions § Commit messages](wiki/wiki_robost/Conventions.md#commit-messages), and must never include a `Co-Authored-By` trailer or any other AI-attribution line.

---

## Wiki layout

This workspace embeds two documentation wikis as submodules under `wiki/`, alongside its own workspace wiki:

- [wiki/wiki_robost/](wiki/wiki_robost/) — team wiki (Git, Docker, Linux, conventions, lab equipment).
- [wiki/wiki_ros2/](wiki/wiki_ros2/) — ROS-specific docs (ROS install, RealSense on ROS, MoveIt).
- [wiki/home.md](wiki/home.md) — this workspace's project guide (humans).

**Before editing or creating any file under `wiki/`, read both [wiki/wiki_robost/AGENT.md](wiki/wiki_robost/AGENT.md) and [wiki/wiki_robost/Conventions.md](wiki/wiki_robost/Conventions.md) end-to-end.** They are the single source of truth for wiki content rules (Diátaxis, Markdown-only, English, no images, link style, Mermaid + ELK layout, naming). This file does not duplicate those rules.

**Git / submodule questions:** consult the team wiki's [wiki/wiki_robost/git/](wiki/wiki_robost/git/) folder — it defines the standard Robost Git workflows. In particular [git/Submodules.md](wiki/wiki_robost/git/Submodules.md) (pinning, the two sources of truth) and [git/Update-Submodules.md](wiki/wiki_robost/git/Update-Submodules.md). Git / commit conventions: [wiki/wiki_robost/Conventions.md § Git conventions](wiki/wiki_robost/Conventions.md#git-conventions).
