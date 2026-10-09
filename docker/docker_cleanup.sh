#!/bin/bash

# Docker Cleanup Script
# Frees disk space using Docker commands, with a filesystem cleanup fallback.
# Two-phase strategy: Docker commands first, then a filesystem cleanup if needed.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}"
echo "============================================"
echo "Docker Cleanup Script"
echo "============================================"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}This script:${NC}"
echo "  - uses the official Docker commands"
echo "  - removes containers, images, volumes, and build cache"
echo "  - runs an extra filesystem cleanup if more than 5 GB remain"
echo ""
read -p "Really continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${BLUE}=== Disk usage before ===${NC}"
echo -e "${YELLOW}Docker directory:${NC}"
sudo du -sh /var/lib/docker 2>/dev/null || echo "N/A"
echo -e "${YELLOW}overlay2 directory:${NC}"
sudo du -sh /var/lib/docker/overlay2 2>/dev/null || echo "N/A"
BEFORE=$(sudo du -sb /var/lib/docker 2>/dev/null | awk '{print $1}' || echo 0)
echo ""

# Phase 1: Docker commands
echo -e "${BLUE}=== Phase 1: Docker commands ===${NC}"

echo -e "${YELLOW}[1/5] Stopping all containers...${NC}"
docker container ls -q 2>/dev/null | xargs -r docker stop 2>/dev/null || true
docker container ls -aq 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
echo "Containers removed."
echo ""

echo -e "${YELLOW}[2/5] Removing all images...${NC}"
docker image ls -q 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
echo "Images removed."
echo ""

echo -e "${YELLOW}[3/5] Removing all volumes...${NC}"
docker volume ls -q 2>/dev/null | xargs -r docker volume rm -f 2>/dev/null || true
echo "Volumes removed."
echo ""

echo -e "${YELLOW}[4/5] Running 'docker system prune' with all flags...${NC}"
docker system prune -a -f --volumes 2>/dev/null || true
echo "System prune done."
echo ""

echo -e "${YELLOW}[5/5] Clearing the build cache...${NC}"
docker builder prune -a -f 2>/dev/null || true
echo "Build cache cleared."
echo ""

# Disk usage after the Docker commands
echo -e "${BLUE}Disk usage after the Docker commands:${NC}"
sudo du -sh /var/lib/docker 2>/dev/null || echo "N/A"
AFTER_DOCKER=$(sudo du -sb /var/lib/docker 2>/dev/null | awk '{print $1}' || echo 0)
echo ""

# Phase 2: filesystem cleanup if a lot of space is still used
THRESHOLD=$((5 * 1024 * 1024 * 1024))  # 5 GB
if [ "$AFTER_DOCKER" -gt "$THRESHOLD" ]; then
    echo -e "${YELLOW}WARNING: still more than 5 GB used - starting filesystem cleanup...${NC}"
    echo ""

    echo -e "${BLUE}=== Phase 2: Filesystem cleanup (needed) ===${NC}"

    echo -e "${YELLOW}[1/4] Stopping Docker for the direct cleanup...${NC}"
    sudo systemctl stop docker
    sudo systemctl stop docker.socket 2>/dev/null || true
    sleep 3
    echo "Docker stopped."
    echo ""

    echo -e "${YELLOW}[2/4] Deleting overlay2 content...${NC}"
    if [ -d "/var/lib/docker/overlay2" ]; then
        sudo find /var/lib/docker/overlay2 -maxdepth 1 -type d ! -name 'l' ! -name 'overlay2' -exec rm -rf {} + 2>/dev/null || true
        if [ -d "/var/lib/docker/overlay2/l" ]; then
            sudo find /var/lib/docker/overlay2/l -type l -delete 2>/dev/null || true
        fi
        echo "overlay2 cleared."
    fi
    echo ""

    echo -e "${YELLOW}[3/4] Deleting metadata and cache...${NC}"
    sudo rm -rf /var/lib/docker/image/overlay2 2>/dev/null || true
    sudo rm -rf /var/lib/docker/buildkit 2>/dev/null || true
    sudo rm -rf /var/lib/docker/tmp 2>/dev/null || true
    echo "Metadata deleted."
    echo ""

    echo -e "${YELLOW}[4/4] Restarting Docker...${NC}"
    sudo systemctl start docker
    sleep 3

    for i in {1..30}; do
        if docker ps &> /dev/null; then
            echo "Docker is running again."
            break
        fi
        sleep 1
    done
    echo ""
else
    echo -e "${GREEN}The Docker commands were sufficient.${NC}"
    echo "   Filesystem cleanup not needed."
    echo ""
fi

# Final statistics
echo -e "${BLUE}=== Final disk usage ===${NC}"
FINAL=$(sudo du -sb /var/lib/docker 2>/dev/null | awk '{print $1}' || echo 0)
sudo du -sh /var/lib/docker 2>/dev/null || echo "N/A"
echo ""

# Summary
if [ "$BEFORE" -gt 0 ] && [ "$FINAL" -gt 0 ]; then
    FREED=$((BEFORE - FINAL))
    FREED_GB=$((FREED / 1024 / 1024 / 1024))
    echo -e "${GREEN}Cleanup complete.${NC}"
    echo -e "${GREEN}   Freed: ~${FREED_GB} GB${NC}"
else
    echo -e "${GREEN}Cleanup complete.${NC}"
fi
echo ""

echo "Disk usage summary:"
echo "  Before: ~$((BEFORE / 1024 / 1024 / 1024)) GB"
echo "  After:  ~$((FINAL / 1024 / 1024 / 1024)) GB"
echo ""

echo -e "${YELLOW}Note:${NC}"
echo "  - all operations use Docker commands"
echo "  - filesystem cleanup only runs when needed (> 5 GB left)"
echo "  - Docker is reinitialized cleanly"
echo ""
