# =============================================================================
# Project Image — h2_ws
# Built on top of the shared robost-ros2-base image.
# =============================================================================
# Build context must be the workspace root.
# Build: docker build --build-arg WS_NAME=h2_ws -f docker/Dockerfile -t h2_ws_image .
#
# Project Dockerfiles only add project-specific packages. Never run
# apt-get upgrade / full-upgrade here — system updates belong in the base
# image. See docker/docker_template/README.md.

ARG BASE_IMAGE=robost-ros2-base:humble
FROM $BASE_IMAGE

ARG ROS_DISTRO=humble \
    WS_NAME=h2_ws

# ============================================================================
# Layer 1: Desktop ROS 2 + tools — the official ROS 2 tutorials rely on the
#          desktop install (rviz2, rqt, turtlesim, demo nodes); nano is an
#          in-container editor, mesa-utils helps GUI rendering.
# ============================================================================
RUN apt-get update && apt-get install -y \
    ros-$ROS_DISTRO-desktop \
    nano \
    mesa-utils \
 && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Layer 1.5: Unitree ROS 2 bridge deps — required by the unitree_ros2
#            submodule (see unitree_ros2/README.md § Dependencies). On Humble
#            these three apt packages are sufficient; compiling CycloneDDS
#            0.10.2 from source is only needed on Foxy, so it's skipped here.
# ============================================================================
RUN apt-get update && apt-get install -y \
    ros-$ROS_DISTRO-rmw-cyclonedds-cpp \
    ros-$ROS_DISTRO-rosidl-generator-dds-idl \
    libyaml-cpp-dev \
 && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Layer 1.6: unitree_mujoco build deps — unitree_sdk2 (installed system-wide
#            at /opt/unitree_robotics, its own recommended path) and a pinned
#            MuJoCo release, both needed to compile unitree_mujoco's C++
#            simulator. unitree_mujoco itself is a separate standalone
#            workspace, bind-mounted at runtime (see docker/run_container.sh),
#            same as unitree_ros2 — it is not part of this repo.
# ============================================================================
RUN apt-get update && apt-get install -y \
    libspdlog-dev \
    libboost-all-dev \
    libglfw3-dev \
    libeigen3-dev \
    libfmt-dev \
 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/unitreerobotics/unitree_sdk2.git /tmp/unitree_sdk2 \
 && mkdir /tmp/unitree_sdk2/build \
 && cd /tmp/unitree_sdk2/build \
 && cmake .. -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics \
 && make install \
 && rm -rf /tmp/unitree_sdk2

ARG MUJOCO_VERSION=3.3.6
RUN mkdir -p /home/robost/.mujoco \
 && curl -fsSL "https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/mujoco-${MUJOCO_VERSION}-linux-x86_64.tar.gz" \
    | tar -xz -C /home/robost/.mujoco \
 && chown -R robost:robost /home/robost/.mujoco

# ============================================================================
# Layer 1.7: unitree_mujoco Python simulator deps (simulate_python) — mujoco
#            and pygame from pip, plus unitree_sdk2_python for the DDS
#            bridge. Installed editable (-e) from a clone kept at
#            /opt/unitree_sdk2_python, not removed after install: a plain
#            (non-editable) wheel build silently drops the package's native
#            crc_amd64.so (it's data, not declared as package data), which
#            crashes crc.py's ctypes.CDLL() at import time. CYCLONEDDS_HOME
#            points at unitree_sdk2's own CycloneDDS build (Layer 1.6) —
#            needed to find libddsc, per unitree_mujoco/readme.md's own
#            troubleshooting note for the "Could not locate cyclonedds" error.
# ============================================================================
RUN pip3 install --no-cache-dir mujoco pygame

RUN git clone https://github.com/unitreerobotics/unitree_sdk2_python.git /opt/unitree_sdk2_python \
 && CYCLONEDDS_HOME=/opt/unitree_robotics pip3 install --no-cache-dir -e /opt/unitree_sdk2_python \
 && chown -R robost:robost /opt/unitree_sdk2_python

# ============================================================================
# Layer 1.8: h2_description (src/) build/runtime deps — joint_state_publisher
#            isn't in ros-$ROS_DISTRO-desktop by default; xacro is standard
#            practice for a robot_description package's launch files even
#            though H2's own URDF happens to be plain (not xacro).
# ============================================================================
RUN apt-get update && apt-get install -y \
    ros-$ROS_DISTRO-joint-state-publisher \
    ros-$ROS_DISTRO-joint-state-publisher-gui \
    ros-$ROS_DISTRO-xacro \
 && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Layer 1.9: MoveIt 2 — h2_moveit_config (src/). RViz demo/fake-execution
#            only for now (moveit_fake_controller_manager): planning,
#            self-collision checking, IK for the left_arm/right_arm groups,
#            "Execute" only animates the displayed model. No real trajectory
#            execution bridge to rt/lowcmd — that's separate, later, and
#            deliberately not built casually (see h2.srdf's header comment).
# ============================================================================
RUN apt-get update && apt-get install -y \
    ros-$ROS_DISTRO-moveit \
    ros-$ROS_DISTRO-ros2-control \
    ros-$ROS_DISTRO-ros2-controllers \
 && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Layer 2: Workspace mountpoint — the workspace is bind-mounted at runtime via
#          --volume in run_container.sh ($HOST_WS_DIR -> /home/robost/$WS_NAME).
#          WS_NAME is passed as build-arg from host_setup.sh (derived from the
#          workspace folder name).
# ============================================================================
ENV WS_ROOT=/home/robost/$WS_NAME \
    ROS_LOG_DIR=/home/robost/$WS_NAME/log
RUN mkdir -p $WS_ROOT && chown -R robost:robost $WS_ROOT
WORKDIR $WS_ROOT

# ============================================================================
# Layer 3: Interactive shell — drop into the workspace and source the colcon
#          overlay once it has been built. The base image already sources
#          /opt/ros/$ROS_DISTRO.
# ============================================================================
RUN echo '[ -f $WS_ROOT/install/setup.bash ] && source $WS_ROOT/install/setup.bash' >> $HOME/.bashrc && \
    echo "cd $WS_ROOT" >> $HOME/.bashrc && \
    chown robost:robost $HOME/.bashrc

# Switch to non-root user for runtime
USER robost

CMD ["/bin/bash"]
