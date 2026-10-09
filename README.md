# Template Docker (robost-ros2-base)

This repository serves as a central Git submodule for all ROS2 robotics projects. It encapsulates the complexity of the Docker environment, X11 forwarding, GPU passthrough, and host configurations, keeping the actual project repositories clean and manageable.

## Architecture & Concept

The setup is based on two core principles:
1. **Two-stage Dockerfiles:** A generic base image (`robost-ros2-base:jazzy`) and a lean, project-specific image.
2. **Wrapper Pattern for Scripts:** The complex logic (mounting, platform detection) resides within the template. The project repository only contains tiny wrapper scripts that pass project-specific parameters when needed.

---

## Integration into a New Project (Wrapper Pattern)

Instead of copying execution scripts into every repository, this repository is included as a submodule under `docker/docker_template`. You then create short wrapper scripts in your project's `docker/` directory.

### 1. Starting the Container (`run_container.sh`)

The template automatically detects the architecture (AMD64, ARM64/Jetson, WSL2) and mounts X11, GPUs, and the workspace. If your project requires additional Docker arguments (e.g., USB cameras, custom network ports), create the following `docker/run_container.sh` in your project:

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cross-platform arguments (Bash array – supports values with spaces)
EXTRA_DOCKER_ARGS_COMMON=(
    --device /dev/video0
)

# Platform-specific arguments (optional)
EXTRA_DOCKER_ARGS_AMD64=()
EXTRA_DOCKER_ARGS_ARM64=()
EXTRA_DOCKER_ARGS_WSL=()

# Source the template (required for array expansion) and run
source "$SCRIPT_DIR/docker_template/run_container.sh"

detect_platform
detect_usb_can
preflight_checks

case "$ARCH_TYPE" in
    amd64) run_amd64 ;;
    arm64) run_arm64 ;;
    wsl)   run_wsl   ;;
esac
```

### 2. Setting Up the Host (`host_setup.sh`)

The template installs Docker, NVIDIA drivers, and builds the Docker images. If your project requires additional host setup steps (e.g., installing udev rules) before the image build, create the following `docker/host_setup.sh`:

```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(dirname "$SCRIPT_DIR")"

# ----------------------------------------------------------------------------
# 0. Initialize git submodules
# ----------------------------------------------------------------------------
# --checkout forces a checkout of the pinned SHA even for submodules with
# `update = none` in .gitmodules. That policy is meant to protect pinned
# submodules from later `git submodule update --remote --recursive` runs, but
# on a fresh clone we still need the pinned SHA to land in the working tree.
# Without --checkout here, vendor-pinned submodules (kernel-coupled SDKs,
# tag-pinned drivers) would be left uninitialized after host_setup.
if [ -d "$WS_DIR/.git" ]; then
    if ssh -T git@gitlab.gwdg.de -o ConnectTimeout=5 -o BatchMode=yes 2>&1 | grep -q "Welcome"; then
        git -C "$WS_DIR" submodule update --init --recursive --checkout
    else
        git -C "$WS_DIR" -c url."https://gitlab.gwdg.de/".insteadOf="git@gitlab.gwdg.de:" \
            submodule update --init --recursive --checkout
    fi
fi

# ----------------------------------------------------------------------------
# 1. Platform-specific setup hooks (run right after driver installation)
# ----------------------------------------------------------------------------
export HOST_SETUP_CMD_AMD64=""
export HOST_SETUP_CMD_ARM64=""
export HOST_SETUP_CMD_WSL=""

# ----------------------------------------------------------------------------
# 2. Common hook — runs on every platform exactly BEFORE the images are built.
# Example: activate udev rules.
# ----------------------------------------------------------------------------
export HOST_SETUP_CMD_COMMON=""

# Call the template script
"$SCRIPT_DIR/docker_template/host_setup.sh"
```

The submodule contract — which submodules track a branch (`branch = main`) versus which are hard-pinned (`update = none`) — is documented in the team's `wiki_robost/git/Submodule-Pinning-Contract.md`. The `--checkout` flag above is the wrapper-side half of that contract.

### 3. Dockerfile

Your project-specific Dockerfile (`docker/Dockerfile` in the main repo) should be based on the base image and only contain dependencies specific to the project (e.g., `rosdep install`).

**Important:** Please **never** use `apt-get full-upgrade` or `apt-get upgrade` in project Dockerfiles. This breaks reproducibility and the Docker layer cache. Add system updates to the base image of this template instead.

---

## Cleanup

The template comes with a `docker_cleanup.sh` script. This removes unneeded containers, orphaned volumes, and dangling images to free up disk space on the host.
