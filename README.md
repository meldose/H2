# h2_ws

Docker-based ROS 2 Jazzy workspace for working through the official
[ROS 2 tutorials](https://docs.ros.org/en/jazzy/Tutorials.html). ROS 2 runs
entirely inside a container, so the tutorials can be completed independently of
the host system. Target platform is an AMD64 Linux workstation; the Jetson Orin
(ARM64) and WSL2 are also supported via the Docker setup. The workspace ships
one example package, `hello_world`, as a starting point.

---

## Requirements

### Required

- **OS:** any Docker-capable host — a Linux workstation (Ubuntu LTS recommended — see [Install Ubuntu](https://gitlab.gwdg.de/robost/wiki_robost/-/blob/main/linux/Install-Ubuntu.md)), Windows with WSL2, or the Jetson Orin. ROS 2 Jazzy runs *inside the container* — it is not required on the host.
- **Git** with a GitLab account and access to this project, plus to the `wiki_robost`, `wiki_ros2`, and `docker_template` submodules.

### Recommended

- **IDE:** VS Code with the Mermaid plugin — see [Workstation Setup](https://gitlab.gwdg.de/robost/wiki_robost/-/blob/main/Workstation-Setup.md). VS Code renders Markdown and math natively; only Mermaid needs an extension.
- **AI assistant:** Claude, OpenAI Codex, or GitHub Copilot — see Workstation Setup above for install commands. This repo ships `AGENT.md` for the agent briefing.

---

## How to get started

1. Clone the repo:

   ```bash
   git clone git@gitlab.gwdg.de:robost/ros2/ws/h2_ws.git
   cd h2_ws
   ```

   No SSH key set up? Use the HTTPS clone URL and follow [Authentication](https://gitlab.gwdg.de/robost/wiki_robost/-/blob/main/git/Authentication.md) so the `git@…` submodule URLs still resolve.

2. Make the setup script executable and run it. If you have not used a terminal on Linux before, read [Run Commands in Terminal](https://gitlab.gwdg.de/robost/wiki_robost/-/blob/main/linux/Run-Commands-in-Terminal.md) first; `chmod +x` makes a file executable.

   ```bash
   chmod +x docker/host_setup.sh
   ./docker/host_setup.sh
   ```

   `host_setup.sh` initializes all git submodules (team wiki, ROS wiki, `docker_template`), installs Docker and the NVIDIA Container Toolkit, and builds the base and project Docker images.

3. Clone the two Unitree integration workspaces as siblings, next to `h2_ws` — not inside it. Each is its own independent upstream project (own git history, own build), kept deliberately separate rather than folded into this repo. Clone from the `danreu25` forks, not `unitreerobotics` upstream directly — the forks carry local fixes this project needs (`unitree_ros2`: ROS distro set to `humble`, fixed `ROS_DOMAIN_ID`; `unitree_mujoco`: `config.yaml` set to the `h2` robot):

   ```bash
   cd ..
   git clone https://github.com/danreu25/unitree_ros2.git
   git clone https://github.com/danreu25/unitree_mujoco.git
   cd h2_ws
   ```

   `docker/run_container.sh` bind-mounts both automatically if found at `../unitree_ros2` and `../unitree_mujoco`. Skip this step if you only need the plain ROS 2 tutorials — everything Unitree/H2-specific (simulation, the real robot) needs them.

---

## Setup complete — keep reading locally in VS Code

You are still in the workspace folder from the clone step above — open it in VS Code (`.` means the current directory):

```bash
code .
```

From here on, **stop reading this README on the GitLab web view** and open the project locally instead. Reasons:

- The `wiki/wiki_robost/`, `wiki/wiki_ros2/`, and `docker/docker_template/` submodules are now present in your working tree, so all cross-references below resolve to actual files.
- The full Markdown rendering (Mermaid diagrams) only works in VS Code with the Mermaid extension installed.
- An AI assistant in VS Code can read this README, the workspace wiki, and the team / ROS wikis in one shot.

Not set up VS Code and the Mermaid extension yet? Do that before continuing — see **Recommended** under Requirements above.

---

## Next steps

**Bring the workspace up.** [Running the Workspace](wiki/Running-the-Workspace.md) takes you from here to the running `hello_world` example.

**Want to work on the project?** Read [`wiki/home.md`](wiki/home.md) carefully — it is the project guide: architecture, the package map, how the ROS 2 tutorials fit in, and where to go from there.

---

## Deploying to the robot's onboard computer

Everything above sets up a dev workstation. The robot itself has its own onboard computer(s) — PC2 and Thor — reachable over the robot's network. To bring `h2_ws` up there, SSH in first:

```bash
ssh unitree@192.168.123.164   # Thor
# or
ssh unitree@192.168.123.162   # PC2
```

You'll need git access configured on the robot's computer for the private GitLab remote first — see **Git access on the robot's computer** below.

Then, on the robot's computer, repeat the same sibling-clone layout as steps 1–3 above:

```bash
mkdir -p ~/ros2 && cd ~/ros2
git clone git@gitlab.gwdg.de:robost/ros2/ws/h2_ws.git
git clone https://github.com/danreu25/unitree_ros2.git
cd h2_ws
./docker/host_setup.sh
./docker/run_container.sh
```

Skip `unitree_mujoco` — it simulates a robot, and this computer is already attached to a real one. `docker/run_container.sh` bind-mounts `unitree_ros2` the same way it does on a workstation and does not require `unitree_mujoco` to be present.

[`docker/robot_bootstrap.sh`](docker/robot_bootstrap.sh) automates the block above. Since `h2_ws` doesn't exist on the robot yet, copy that one file over first:

```bash
scp docker/robot_bootstrap.sh unitree@192.168.123.164:~/   # or .162 for PC2
ssh unitree@192.168.123.164
chmod +x robot_bootstrap.sh && ./robot_bootstrap.sh
```

### Git access on the robot's computer

`h2_ws` is a private GitLab project, so the robot's computer needs its own credentials — don't copy your personal SSH private key onto shared robot hardware. Use a **deploy key** instead, scoped to just this repo:

1. On the robot's computer, generate a dedicated key (no passphrase, since it needs to run non-interactively):

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/h2_ws_deploy -N ""
   cat ~/.ssh/h2_ws_deploy.pub
   ```

2. In GitLab, open the `h2_ws` project → **Settings → Repository → Deploy keys** → paste the public key. Leave "Grant write permissions" unchecked (read-only is enough to clone and pull).

3. Back on the robot's computer, point git at that key for GitLab specifically:

   ```bash
   cat >> ~/.ssh/config <<'EOF'
   Host gitlab.gwdg.de
     IdentityFile ~/.ssh/h2_ws_deploy
     IdentitiesOnly yes
   EOF
   ssh -T git@gitlab.gwdg.de   # should greet you by the deploy key's name
   ```

`unitree_ros2` is public on GitHub, so no credentials are needed for that clone.
