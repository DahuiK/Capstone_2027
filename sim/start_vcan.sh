#!/usr/bin/env bash
# Create the virtual CAN bus vcan0 (Linux only). Needed after every reboot.
set -euo pipefail
sudo modprobe vcan
if ! ip link show vcan0 >/dev/null 2>&1; then
  sudo ip link add dev vcan0 type vcan
fi
sudo ip link set up vcan0
ip -details link show vcan0 | head -3
echo "vcan0 is up. Watch traffic with: candump vcan0"
