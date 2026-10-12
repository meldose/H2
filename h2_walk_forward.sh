#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
H2_INTERFACE="${H2_INTERFACE:-enp6s0}"

if [[ ! -f /.dockerenv ]]; then
    echo "Run this inside the h2_ws Docker container (./docker/run_container.sh)." >&2
    echo "The H2 Unitree SDK is installed in the container." >&2
    exit 1
fi

exec python3 "$SCRIPT_DIR/h2_walk_forward.py" --interface "$H2_INTERFACE" "$@"
