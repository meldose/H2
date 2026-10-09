# =============================================================================
# ROS2 Base Image — shared across all robost projects
# =============================================================================
# Build: docker build --build-arg HOST_UID=$(id -u) --build-arg HOST_GID=$(id -g) -t robost-ros2-base:jazzy .
# Usage: FROM robost-ros2-base:jazzy  (in project Dockerfiles)

ARG ROS_DISTRO=humble
FROM ros:$ROS_DISTRO

ARG ROS_DISTRO \
    USERNAME=robost \
    HOST_UID=1000 \
    HOST_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/$USERNAME

# ============================================================================
# Layer 1: System utilities — build tools and ROS essentials needed by every project
#           (project-specific packages go in the project Dockerfile)
# ============================================================================
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    build-essential \
    git \
    sudo \
    python3-rosdep \
 && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Layer 2: Non-root user — mirrors host UID/GID to avoid permission issues
#           when bind-mounting the workspace from the host
# ============================================================================
RUN set -eux; \
    EXISTING_USER=$(getent passwd $HOST_UID | cut -d: -f1 || echo ""); \
    if [ -n "$EXISTING_USER" ] && [ "$EXISTING_USER" != "$USERNAME" ]; then \
        EXISTING_GROUP=$(getent group $(getent passwd $HOST_UID | cut -d: -f4) | cut -d: -f1); \
        if [ -n "$EXISTING_GROUP" ] && [ "$EXISTING_GROUP" != "$USERNAME" ]; then \
            groupmod -n $USERNAME $EXISTING_GROUP; \
        fi; \
        usermod -l $USERNAME -d /home/$USERNAME -m $EXISTING_USER; \
    elif [ -z "$EXISTING_USER" ]; then \
        if ! getent group $HOST_GID >/dev/null; then groupadd -g $HOST_GID $USERNAME; fi; \
        useradd -m -u $HOST_UID -g $HOST_GID -s /bin/bash $USERNAME; \
    fi; \
    echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME; \
    chmod 0440 /etc/sudoers.d/$USERNAME; \
    mkdir -p /home/$USERNAME/.ros; \
    chown -R $HOST_UID:$HOST_GID /home/$USERNAME

# Auto-source ROS 2 setup in .bashrc
RUN echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> $HOME/.bashrc && \
    chown $HOST_UID:$HOST_GID $HOME/.bashrc

CMD ["/bin/bash"]