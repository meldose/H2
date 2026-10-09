#!/bin/bash

# Host Setup Script
# Detects the platform (AMD64, ARM64, WSL2) and installs Docker,
# GPU support, tmux/tmuxp, git submodules, and builds the Docker image.

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")"
WS_DIR="$(dirname "$DOCKER_DIR")"
WORKSPACE_NAME="$(basename "$WS_DIR")"
IMAGE_NAME="${WORKSPACE_NAME}_image"
BASE_IMAGE_NAME="robost-ros2-base:humble"

# =============================================================================
# Helper Functions
# =============================================================================

install_docker() {
    echo "======================================"
    echo "Installing Docker"
    echo "======================================"
    echo ""

    echo "Step 1: Removing old Docker versions..."
    sudo apt-get remove -y docker docker-engine docker.io containerd runc || true

    echo ""
    echo "Step 2: Setting up Docker repository..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    echo ""
    echo "Step 3: Installing Docker Engine..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo ""
    echo "Step 4: Configuring Docker group..."
    sudo groupadd docker || true
    TARGET_USER="${USER:-$(id -un)}"
    if [ -z "$TARGET_USER" ]; then
        echo "Error: Could not determine user to add to docker group."
        exit 1
    fi
    sudo usermod -aG docker "$TARGET_USER"

    echo ""
    echo "Step 5: Starting Docker service..."
    sudo systemctl start docker
    sudo systemctl enable docker

    echo ""
    echo "Step 6: Testing Docker installation (with sudo)..."
    sudo docker run hello-world

    echo ""
    echo "======================================"
    echo "Docker installed successfully!"
    echo "======================================"
    echo ""
}

ensure_docker_installed() {
    if ! command -v docker &> /dev/null; then
        echo "Docker is not installed. Installing now..."
        install_docker
    else
        echo "Docker is already installed."
        echo ""
    fi
}

install_nvidia_container_toolkit() {
    local distribution
    distribution=$(. /etc/os-release; echo "$ID$VERSION_ID")

    echo "Adding NVIDIA package repository..."
    sudo rm -f /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L "https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list" | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

    echo ""
    echo "Installing NVIDIA Container Toolkit..."
    sudo apt-get update
    sudo apt-get install -y --allow-downgrades nvidia-container-toolkit

    echo ""
    echo "NVIDIA Container Toolkit installed"
}

# =============================================================================
# Platform-Specific Setup Functions
# =============================================================================

setup_amd64() {
    echo "======================================"
    echo "Starting AMD64 Setup..."
    echo "======================================"

    # Check for lspci and install if missing
    if ! command -v lspci &> /dev/null; then
        echo "Installing pciutils for GPU detection..."
        sudo apt-get update && sudo apt-get install -y pciutils
    fi

    # Check if NVIDIA GPU is available first
    HAS_NVIDIA_GPU=false
    if lspci | grep -i nvidia &> /dev/null; then
        echo "NVIDIA GPU detected"
        HAS_NVIDIA_GPU=true
    else
        echo "No NVIDIA GPU detected"
        echo "  Skipping NVIDIA Container Toolkit installation."
    fi
    echo ""

    ensure_docker_installed

    if [ "$HAS_NVIDIA_GPU" = true ]; then
        echo "======================================"
        echo "NVIDIA Container Toolkit Configuration"
        echo "======================================"
        echo ""

        # Check if NVIDIA drivers are installed
        if ! command -v nvidia-smi &> /dev/null; then
            echo "WARNING: NVIDIA drivers not installed!"
            echo "Please install the drivers first:"
            echo "  sudo apt-get install nvidia-driver-XXX"
            echo ""
            echo "Skipping NVIDIA Container Toolkit installation."
            echo ""
        elif ! nvidia-smi &> /dev/null; then
            echo "WARNING: NVIDIA drivers installed but not working!"
            echo "Please check your driver installation."
            echo ""
            echo "Skipping NVIDIA Container Toolkit installation."
            echo ""
        else
            if ! command -v nvidia-ctk &> /dev/null; then
                install_nvidia_container_toolkit
            fi

            echo "Configuring NVIDIA runtime as default..."
            sudo nvidia-ctk runtime configure --runtime=docker --set-as-default

            echo ""
            echo "Generating CDI specification for NVIDIA devices..."
            sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml || echo "Warning: CDI generation failed (non-critical)"
        fi
    fi
}

setup_arm64() {
    echo "======================================"
    echo "Starting ARM64/Jetson Setup..."
    echo "======================================"

    ensure_docker_installed

    echo "======================================"
    echo "NVIDIA Container Toolkit Setup"
    echo "======================================"
    echo ""

    install_nvidia_container_toolkit

    echo ""
    echo "Configuring Docker for NVIDIA runtime..."
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker

    echo ""
    echo "ARM64 setup complete"
    echo ""
}

setup_wsl() {
    echo "======================================"
    echo "Starting WSL2 Setup..."
    echo "======================================"
    echo ""

    # Check WSL2 kernel
    KERNEL_VERSION=$(uname -r)
    echo "WSL kernel: $KERNEL_VERSION"
    if echo "$KERNEL_VERSION" | grep -q "WSL2\|microsoft-standard"; then
        echo "WSL2 detected"
    else
        echo "Warning: Could not confirm WSL2. GPU passthrough requires WSL2."
        echo "  Upgrade with: wsl --set-version <distro> 2  (from PowerShell)"
    fi
    echo ""

    # Check systemd (required for Docker service)
    if [ "$(ps -p 1 -o comm=)" = "systemd" ]; then
        echo "systemd is running"
    else
        echo "systemd is not running. Enabling it..."
        NEEDS_RESTART=false
        if [ -f /etc/wsl.conf ]; then
            if grep -q '^\[boot\]' /etc/wsl.conf; then
                if ! grep -q 'systemd=true' /etc/wsl.conf; then
                    sudo sed -i '/^\[boot\]/a systemd=true' /etc/wsl.conf
                    NEEDS_RESTART=true
                fi
            else
                echo -e "\n[boot]\nsystemd=true" | sudo tee -a /etc/wsl.conf > /dev/null
                NEEDS_RESTART=true
            fi
        else
            echo -e "[boot]\nsystemd=true" | sudo tee /etc/wsl.conf > /dev/null
            NEEDS_RESTART=true
        fi

        if [ "$NEEDS_RESTART" = true ]; then
            echo ""
            echo "============================================================"
            echo "  systemd has been enabled in /etc/wsl.conf."
            echo "  You MUST restart WSL for this to take effect:"
            echo ""
            echo "    1. Open PowerShell on Windows"
            echo "    2. Run:  wsl --shutdown"
            echo "    3. Re-open your WSL terminal"
            echo "    4. Run this script again"
            echo "============================================================"
            exit 0
        fi
    fi
    echo ""

    # Docker Installation (WSL-specific)
    echo "======================================"
    echo "Docker Installation (WSL2)"
    echo "======================================"
    echo ""

    if command -v docker &> /dev/null; then
        DOCKER_INFO=$(docker info 2>/dev/null || true)
        if echo "$DOCKER_INFO" | grep -qi "docker desktop"; then
            echo "Docker Desktop detected (Windows integration)"
            echo "  Note: Docker Desktop with WSL2 backend works fine."
        else
            echo "Docker is already installed."
        fi
    else
        echo "Installing Docker Engine in WSL2..."
        echo ""

        echo "Step 1: Removing old Docker versions..."
        sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

        echo ""
        echo "Step 2: Setting up Docker repository..."
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        echo ""
        echo "Step 3: Installing Docker Engine..."
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        echo ""
        echo "Step 4: Configuring Docker group..."
        sudo groupadd docker 2>/dev/null || true
        sudo usermod -aG docker "${USER:-$(id -un)}"

        echo ""
        echo "Step 5: Starting Docker service..."
        sudo systemctl start docker
        sudo systemctl enable docker

        echo ""
        echo "Step 6: Testing Docker installation..."
        sudo docker run --rm hello-world

        echo ""
        echo "Docker installed successfully!"
    fi
    echo ""

    # NVIDIA Container Toolkit (WSL2 GPU)
    echo "======================================"
    echo "NVIDIA GPU Support (WSL2)"
    echo "======================================"
    echo ""

    echo "Note: In WSL2, GPU drivers are provided by the Windows host."
    echo "      Do NOT install nvidia-driver-* packages inside WSL."
    echo ""

    HAS_GPU=false
    if nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU accessible via WSL2"
        nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null || true
        HAS_GPU=true
        echo ""
    else
        echo "nvidia-smi not found or not working."
        echo "  Ensure you have a recent NVIDIA GPU driver installed on Windows."
        echo "  Download from: https://www.nvidia.com/download/index.aspx"
        echo "  After installing the Windows driver, restart WSL: wsl --shutdown"
        echo ""
    fi

    if [ "$HAS_GPU" = true ]; then
        if command -v nvidia-ctk &> /dev/null; then
            echo "NVIDIA Container Toolkit already installed"
        else
            install_nvidia_container_toolkit

            echo ""
            echo "Configuring Docker runtime..."
            sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
            sudo systemctl restart docker

            echo ""
            echo "NVIDIA Container Toolkit installed and configured"
        fi

        echo ""
        echo "Testing GPU access in Docker..."
        if docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi 2>/dev/null; then
            echo ""
            echo "GPU passthrough to Docker containers works!"
        else
            echo ""
            echo "Warning: GPU test failed. Trying CDI configuration..."
            sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml 2>/dev/null || true
            sudo systemctl restart docker
            echo "  Please try again after WSL restart: wsl --shutdown"
        fi
    fi
    echo ""
}

# =============================================================================
# Main
# =============================================================================

# --- Platform Detection ---
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
fi

DETECTED_ARCH=$(uname -m)
if [ "$IS_WSL" = true ]; then
    ARCH_TYPE="wsl"
elif [[ "$DETECTED_ARCH" == "x86_64" ]]; then
    ARCH_TYPE="amd64"
elif [[ "$DETECTED_ARCH" == "aarch64" || "$DETECTED_ARCH" == "arm64" ]]; then
    ARCH_TYPE="arm64"
else
    echo "Error: Unknown architecture '$DETECTED_ARCH'. Supported: x86_64 (amd64), aarch64/arm64 (arm64), WSL2"
    exit 1
fi

echo "Detected platform: $DETECTED_ARCH ($ARCH_TYPE)"
echo ""

# --- Part 1: Platform-specific setup (Docker, GPU) ---
setup_${ARCH_TYPE}

# --- Part 1.5: Project-specific Platform Setup Hook ---
if [ -n "$(eval echo \$HOST_SETUP_CMD_${ARCH_TYPE^^})" ]; then
    echo "======================================"
    echo "Running Project-specific Platform Setup"
    echo "======================================"
    eval "\$HOST_SETUP_CMD_${ARCH_TYPE^^}"
    echo ""
fi

# --- Part 2: tmux & tmuxp (all platforms) ---
echo "======================================"
echo "tmux & tmuxp Installation"
echo "======================================"
echo ""

if ! command -v tmux &> /dev/null; then
    echo "Installing tmux..."
    sudo apt-get update && sudo apt-get install -y tmux
else
    echo "tmux is already installed"
fi

if ! command -v tmuxp &> /dev/null; then
    echo "Installing tmuxp..."
    sudo apt-get install -y python3-pip 2>/dev/null || true
    pip3 install --user tmuxp 2>/dev/null || pipx install tmuxp 2>/dev/null || sudo pip3 install tmuxp
else
    echo "tmuxp is already installed"
fi

echo ""

# --- Part 3.5: Project-specific Common Setup Hook ---
if [ -n "$HOST_SETUP_CMD_COMMON" ]; then
    echo "======================================"
    echo "Running Project-specific Common Setup"
    echo "======================================"
    echo "$HOST_SETUP_CMD_COMMON"
    eval "$HOST_SETUP_CMD_COMMON"
    echo ""
fi

# --- Part 4: Build Docker Images ---
echo "======================================"
echo "Building Base Docker Image"
echo "======================================"
echo ""

echo "Building base image '$BASE_IMAGE_NAME'..."
echo "This may take a while depending on your internet connection..."

if sudo docker build --network=host \
    --build-arg HOST_UID=$(id -u) \
    --build-arg HOST_GID=$(id -g) \
    -f "$SCRIPT_DIR/Dockerfile" \
    -t "$BASE_IMAGE_NAME" "$SCRIPT_DIR"; then
    echo "Base image built successfully"
else
    echo "Base image build failed"
    exit 1
fi

echo ""
echo "======================================"
echo "Building Project Docker Image"
echo "======================================"
echo ""

echo "Building project image '$IMAGE_NAME'..."

if sudo docker build --network=host \
    --build-arg BASE_IMAGE="$BASE_IMAGE_NAME" \
    --build-arg WS_NAME="$WORKSPACE_NAME" \
    -f "$DOCKER_DIR/Dockerfile" \
    -t "$IMAGE_NAME" "$WS_DIR"; then
    echo "Project image built successfully"
else
    echo "Project image build failed"
    exit 1
fi

echo ""
echo "Setup finished successfully!"
