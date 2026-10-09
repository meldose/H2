#!/bin/bash

# ==============================================================================
# Project-specific Host Setup Script
# ==============================================================================
# Wraps the generic docker_template host setup. It first initializes the git
# submodules (so the template scripts and the wikis are actually present), then
# passes project-specific setup commands via the HOST_SETUP_CMD_* hooks before
# the Docker images are built. The ROS 2 tutorial workspace needs no extra host
# setup, so the hooks are left empty.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(dirname "$SCRIPT_DIR")"
# Keep Docker image, container, and in-container workspace names stable even
# when this checkout directory is renamed (for example, H2 instead of h2_ws).
export PROJECT_WORKSPACE_NAME=h2_ws

# ------------------------------------------------------------------------------
# 0. Initialize Git Submodules
# ------------------------------------------------------------------------------
# Done first so the docker_template scripts (and the wikis) are available.
echo "======================================"
echo "Initializing Git Submodules"
echo "======================================"
echo ""

if [ -d "$WS_DIR/.git" ] || [ -f "$WS_DIR/.git" ]; then
    echo "Updating git submodules..."
    cd "$WS_DIR"

    # Auto-detect SSH vs HTTPS for submodule cloning.
    # --checkout forces a checkout of the pinned SHA even for submodules
    # with `update = none` in .gitmodules. That policy protects pinned
    # submodules from later `--remote` runs, but on a fresh clone the
    # pinned SHA still has to land in the working tree.
    # See wiki/wiki_robost/git/Submodule-Pinning-Contract.md.
    if ssh -T git@gitlab.gwdg.de -o ConnectTimeout=5 -o BatchMode=yes 2>&1 | grep -q "Welcome"; then
        git submodule update --init --recursive --checkout
    else
        echo "SSH not available, using HTTPS for submodules..."
        git -c url."https://gitlab.gwdg.de/".insteadOf="git@gitlab.gwdg.de:" submodule update --init --recursive --checkout
    fi

    # Check out the branch specified in .gitmodules for each submodule
    # (prevents a detached HEAD state).
    echo "Checking out configured branches for submodules..."
    git submodule foreach -q 'branch=$(git config -f $toplevel/.gitmodules submodule.$name.branch); if [ -n "$branch" ]; then git checkout -q $branch 2>/dev/null || true; fi'

    echo "Submodules initialized."
else
    echo "Not a git repository or .git missing. Skipping submodule update."
fi
echo ""

# ------------------------------------------------------------------------------
# 1. Platform-specific setup hooks
# ------------------------------------------------------------------------------
# Run on their respective platform right after Docker / the NVIDIA toolkit are
# installed. The ROS 2 tutorials need no platform-specific host setup.
export HOST_SETUP_CMD_AMD64=""
export HOST_SETUP_CMD_ARM64=""
export HOST_SETUP_CMD_WSL=""

# ------------------------------------------------------------------------------
# 2. Common setup hook
# ------------------------------------------------------------------------------
# Runs on all platforms exactly before the Docker images are built.
export HOST_SETUP_CMD_COMMON=""

# Execute the main template script. docker_template is pinned to its humble
# branch (see .gitmodules), so this already builds robost-ros2-base:humble and
# the project image on top of it — no separate Humble build step needed here.
"$SCRIPT_DIR/docker_template/host_setup.sh"
