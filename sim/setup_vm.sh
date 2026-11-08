#!/usr/bin/env bash
# One-time setup of the Ubuntu VM for simulation work.
# Take a VM snapshot first. Re-running is safe.
#
#   bash sim/setup_vm.sh
#
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
VENV="${VENV:-$HOME/drone-venv}"

echo "== Disk space (ArduPilot needs ~5-10 GB) =="
df -h "$HOME" | tail -1

echo "== System packages =="
sudo apt-get update
sudo apt-get install -y git can-utils python3-venv python3-pip

echo "== ArduPilot SITL =="
if [ ! -d "$ARDUPILOT_DIR" ]; then
  git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_DIR"
fi
cd "$ARDUPILOT_DIR"
Tools/environment_install/install-prereqs-ubuntu.sh -y
# shellcheck disable=SC1090
. "$HOME/.profile" || true
./waf configure --board sitl
./waf copter

echo "== Project Python venv (kept separate from ROS / system Python) =="
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install dronecan python-can pymavlink pyyaml

echo
echo "Done. Next:"
echo "  1. bash sim/start_vcan.sh"
echo "  2. source $VENV/bin/activate"
echo "  3. cd $ARDUPILOT_DIR && Tools/autotest/sim_vehicle.py -v ArduCopter --console --map"
