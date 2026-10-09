#!/bin/bash

# Run Container Script
# Starts the Docker container with platform-specific configuration (AMD64, ARM64/Jetson, WSL2).

# ==============================================================================
# Common Configuration
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")"
WS_DIR="$(dirname "$DOCKER_DIR")"
WORKSPACE_NAME="${PROJECT_WORKSPACE_NAME:-$(basename "$WS_DIR")}"
WORKSPACE_SLUG="$(printf '%s' "$WORKSPACE_NAME" | tr '[:upper:]' '[:lower:]')"
IMAGE_NAME="${WORKSPACE_SLUG}_image"
CONTAINER_NAME="${WORKSPACE_SLUG}_container"
WORKSPACE_DIR="/home/robost/$WORKSPACE_NAME"
CONTAINER_COMMAND=("$@")
if [ ${#CONTAINER_COMMAND[@]} -eq 0 ]; then
    CONTAINER_COMMAND=(/bin/bash)
fi

# ==============================================================================
# Platform Detection
# ==============================================================================

detect_platform() {
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
        echo "Error: Unknown platform '$DETECTED_ARCH'. Supported: x86_64 (amd64), aarch64/arm64 (arm64), WSL2"
        exit 1
    fi

    echo "Detected platform: $DETECTED_ARCH ($ARCH_TYPE)"
}

# ==============================================================================
# USB-CAN Adapter Detection
# ==============================================================================

detect_usb_can() {
    if [ -e /dev/ttyUSB0 ]; then
        USB_CAN_DEVICE="/dev/ttyUSB0"
        echo "USB-CAN adapter found at $USB_CAN_DEVICE"
    else
        USB_CAN_DEVICE=""
        echo "No USB-CAN adapter found at /dev/ttyUSB0 (will start without CAN)"
    fi
}

# ==============================================================================
# Pre-flight Checks
# ==============================================================================

preflight_checks() {
    if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
        echo "Error: Docker image '$IMAGE_NAME' not found."
        echo "Please run ./docker/host_setup.sh to build the image first."
        exit 1
    fi

    # Remove leftover container with same name (if any)
    docker rm -f "$CONTAINER_NAME" 2>/dev/null

    xhost +local:docker
}

# ==============================================================================
# Platform-specific Run Functions
# ==============================================================================

run_amd64() {
    echo "Starting container for AMD64..."

    GPU_FLAGS=""
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU detected - enabling GPU support"
        GPU_FLAGS="--gpus all"
    elif lspci | grep -i nvidia &> /dev/null; then
        echo "Warning: NVIDIA GPU hardware detected but driver not working - running without GPU"
        echo "  Try: sudo reboot (driver mismatch often requires reboot after update)"
    else
        echo "No NVIDIA GPU detected - running without GPU support"
    fi

    docker run -it --rm \
        --name "$CONTAINER_NAME" \
        --net=host \
        --ipc=host \
        $GPU_FLAGS \
        --env="DISPLAY=$DISPLAY" \
        --env="QT_X11_NO_MITSHM=1" \
        --env="WEBKIT_DISABLE_DMABUF_RENDERER=1" \
        -u $(id -u):$(id -g) \
        --group-add dialout \
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --volume="$WS_DIR:$WORKSPACE_DIR" \
        --workdir "$WORKSPACE_DIR" \
        ${USB_CAN_DEVICE:+--device $USB_CAN_DEVICE} \
        "${EXTRA_DOCKER_ARGS_COMMON[@]}" \
        "${EXTRA_DOCKER_ARGS_AMD64[@]}" \
        "$IMAGE_NAME" \
        "${CONTAINER_COMMAND[@]}"
}

run_arm64() {
    echo "Starting container for ARM64 (Jetson)..."

    VID_GID=$(getent group video | cut -d: -f3 || echo 44)
    RENDER_GID=$(getent group render | cut -d: -f3 || echo 109)

    RUNTIME_FLAGS=""
    ENV_FLAGS=""
    if [ -f /etc/nv_tegra_release ]; then
        echo "Jetson Tegra detected - enabling NVIDIA runtime"
        RUNTIME_FLAGS="--runtime=nvidia"
        ENV_FLAGS="-e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display"
    fi

    docker run -it --rm \
        --name "$CONTAINER_NAME" \
        $RUNTIME_FLAGS \
        --network=host \
        --ipc=host \
        --group-add "$VID_GID" \
        --group-add "$RENDER_GID" \
        -e DISPLAY=${DISPLAY:-:0} \
        $ENV_FLAGS \
        -e QT_X11_NO_MITSHM=1 \
        -e WEBKIT_DISABLE_DMABUF_RENDERER=1 \
        -e LIBGL_ALWAYS_SOFTWARE=0 \
        -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
        -v "$WS_DIR:$WORKSPACE_DIR" \
        -w "$WORKSPACE_DIR" \
        -v /etc/localtime:/etc/localtime:ro \
        -v /run/udev:/run/udev:ro \
        "${EXTRA_DOCKER_ARGS_COMMON[@]}" \
        "${EXTRA_DOCKER_ARGS_ARM64[@]}" \
        "$IMAGE_NAME" \
        "${CONTAINER_COMMAND[@]}"
}

run_wsl() {
    echo "Starting container for WSL2..."

    GPU_FLAGS=""
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU detected via WSL2 - enabling GPU support"
        GPU_FLAGS="--gpus all"
    else
        echo "No NVIDIA GPU detected in WSL2 - running without GPU support"
    fi

    docker run -it --rm \
        --name "$CONTAINER_NAME" \
        --net=host \
        --ipc=host \
        $GPU_FLAGS \
        --env="DISPLAY=$DISPLAY" \
        --env="QT_X11_NO_MITSHM=1" \
        --env="WAYLAND_DISPLAY=$WAYLAND_DISPLAY" \
        --env="XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR" \
        --env="LIBGL_ALWAYS_INDIRECT=0" \
        --env="LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH}" \
        --env="MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA" \
        --env="GALLIUM_DRIVER=d3d12" \
        --env="MESA_LOADER_DRIVER_OVERRIDE=d3d12" \
        -u $(id -u):$(id -g) \
        --group-add dialout \
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --volume="/mnt/wslg:/mnt/wslg:ro" \
        --volume="/usr/lib/wsl:/usr/lib/wsl:ro" \
        ${USB_CAN_DEVICE:+--device $USB_CAN_DEVICE} \
        --device /dev/dxg \
        --volume="$WS_DIR:$WORKSPACE_DIR" \
        --workdir "$WORKSPACE_DIR" \
        "${EXTRA_DOCKER_ARGS_COMMON[@]}" \
        "${EXTRA_DOCKER_ARGS_WSL[@]}" \
        "$IMAGE_NAME" \
        "${CONTAINER_COMMAND[@]}"
}

# ==============================================================================
# Main (only runs when executed directly, not when sourced)
# ==============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    detect_platform
    detect_usb_can
    preflight_checks

    case "$ARCH_TYPE" in
        amd64) run_amd64 ;;
        arm64) run_arm64 ;;
        wsl)   run_wsl   ;;
    esac
fi
