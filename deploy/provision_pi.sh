#!/usr/bin/env bash
# Set up a Raspberry Pi 3 B+ running Raspberry Pi OS Lite 64-bit (Bookworm).
# Run on the Pi from the repo root:
#
#   bash deploy/provision_pi.sh                # CAN HAT with a 12 MHz crystal
#   CAN_OSC=8000000 bash deploy/provision_pi.sh  # if the HAT's crystal says 8 MHz
#
# Safe to re-run. Reboot afterwards.
set -euo pipefail

CAN_OSC="${CAN_OSC:-12000000}"
CONFIG=/boot/firmware/config.txt
VENV="$HOME/drone-venv"

echo "== Board =="
tr -d '\0' < /proc/device-tree/model; echo
free -h | head -2

echo "== System packages =="
sudo apt-get update
sudo apt-get install -y git can-utils python3-venv python3-pip \
  python3-picamera2 python3-opencv python3-numpy

echo "== Boot config: SPI + CAN HAT overlay (crystal ${CAN_OSC} Hz) =="
add_line() { grep -qxF "$1" "$CONFIG" || echo "$1" | sudo tee -a "$CONFIG" >/dev/null; }
add_line "dtparam=spi=on"
add_line "dtoverlay=mcp2515-can0,oscillator=${CAN_OSC},interrupt=25,spimaxfrequency=2000000"
# camera_auto_detect=1 is already the default on Bookworm (detects Camera Module 3)

echo "== Bring can0 up at boot (only once the HAT is fitted) =="
sudo tee /etc/systemd/system/can0.service >/dev/null <<'EOF'
[Unit]
Description=Bring up can0 (Waveshare RS485 CAN HAT) for DroneCAN
ConditionPathExists=/sys/class/net/can0
After=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/ip link set can0 up type can bitrate 1000000
ExecStop=/sbin/ip link set can0 down

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable can0.service

echo "== Project venv (sees apt's picamera2 + OpenCV) =="
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install dronecan python-can pupil-apriltags piexif psutil pyyaml

echo
echo "Done. Reboot, then:"
echo "  source $VENV/bin/activate"
echo "  python3 tests/pi_benchmark.py            # speed checks, no camera needed"
echo "  bash sim/start_vcan.sh                   # virtual CAN on the Pi itself"
echo "  python3 sim/hello_bus.py cube --iface vcan0  &  python3 sim/hello_bus.py pi --iface vcan0"
