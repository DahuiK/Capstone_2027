# Capstone_2027

Autonomous drone for daily Lake Ontario shoreline erosion monitoring: waypoint survey, geotagged capture, precision docking to a charging station, auto-upload, and day-over-day coastline change measurement.

## How it works

1. The **laptop (ground side)** schedules missions and plans the flight path.
2. The **Raspberry Pi (air side)** flies the mission: it runs the mission state machine and sends requests to the Cube Orange+ and the power board.
3. The drone surveys fixed waypoints, capturing a geotagged nadir image at each one.
4. It returns to the dock, lands precisely on an AprilTag pad, and starts charging.
5. While charging, it uploads the images over Wi-Fi. Local copies are deleted only after the server's checksum matches.
6. A separate analysis app compares each image with the same waypoint's image from the previous day and measures shoreline change.

If the Pi can't reach the laptop at launch time, the drone stays docked.

## Architecture

<img width="691" height="844" alt="image" src="https://github.com/user-attachments/assets/79508a8e-3b67-4ca3-8509-bf2d1fed28ae" />


All drone-side hardware shares **one CAN bus using DroneCAN**. A **Lua script on the Cube** bridges custom DroneCAN commands from the Pi to ArduPilot.

| Link | Carries | How |
| --- | --- | --- |
| Power board → everyone | Charge state, faults, battery | DroneCAN: standard battery message + custom charge status |
| Pi ↔ power board | Start/stop charging, status | Custom DroneCAN messages (`dronecan` Python library) |
| Pi → Cube | Arm, start mission, RTL, land-on-target offsets, abort | Custom DroneCAN messages → Lua bridge → ArduPilot |
| Cube → Pi | Mode, armed, position, attitude, battery, GPS time | Custom DroneCAN status message from the Lua bridge |
| Laptop ↔ Pi | Schedule, flight path, image uploads | Wi-Fi |
| Debug only | Operator RC + telemetry | Unified RC + telemetry on Cube TELEM 1 |

### Software layers

| Layer | Component | Runs on | Hardware-dependent? |
| --- | --- | --- | --- |
| Application | Mission Ctrl Script (scheduling, path planning, receive uploads) | Laptop | No |
| Application | Mission Mgmt Script (state machine, capture, tag landing, upload) | Raspberry Pi 3 B+ | No |
| Application | Lua bridge (CAN ↔ ArduPilot) | Cube Orange+ | Partly (ArduPilot Lua API) |
| Interface | DroneCAN message spec (`dsdl/`) | All boards | No |
| Firmware | Pi drivers (SocketCAN, libcamera, Wi-Fi) | Raspberry Pi 3 B+ | Yes (configured) |
| Firmware | Power board firmware (charge control, sensing) | Power board MCU (on the drone) | Yes |
| Firmware | ArduPilot (stock, configured with parameters) | Cube Orange+ | Yes |


## Full system wiring

Drone, charging station and ground, with every link. Solid parts are confirmed; amber dashed parts are still to confirm with the ME/EE team.

<img width="1276" height="804" alt="image" src="https://github.com/user-attachments/assets/68e7b4dd-596c-4146-8e28-616a415a36fb" />


## CAN bus (physical)

All three nodes are on the drone, daisy chained on one bus:

<img width="1393" height="629" alt="image" src="https://github.com/user-attachments/assets/0b04a66f-0f2d-41ae-b631-146c8b2b55b0" />

| Item | Decision |
| --- | --- |
| Bitrate | 1 Mbps (DroneCAN default), same on every node |
| Termination | 120 Ω at the two end nodes only; power off, CAN_H↔CAN_L should read ~60 Ω |
| Cable | Twisted pair CAN_H/CAN_L + shared GND; JST-GH 4-pin on the Cube; don't link 5 V between boards |
| Node IDs (static) | Cube 10, Pi 20, power board 30 |
| Heartbeat | Every node sends DroneCAN NodeStatus at 1 Hz; Lua triggers RTL if the Pi is silent for 2 s in flight |

## DroneCAN message spec (draft)

| Message | From → to | Fields | Rate |
| --- | --- | --- | --- |
| DRONE_CMD | Pi → Cube | command (ARM, DISARM, START_MISSION, RTL, LAND, ABORT), sequence number | On demand |
| MISSION_ITEM | Pi → Cube | index, total count, lat, lon, alt | Before each flight |
| LAND_TARGET | Pi → Cube | tag x/y offset (m), distance (m), valid flag | ~10 Hz during docking |
| DRONE_STATE | Cube → Pi | mode, armed, lat, lon, alt, roll, pitch, yaw, battery %, GPS time | 5–10 Hz |
| CMD_ACK | Cube / power board → Pi | sequence number, result, reason code | Per command |
| CHARGE_CMD | Pi → power board | start / stop charging | On demand |
| CHARGE_STATUS | Power board → everyone | docked, contacts live, charging, fault code | 1 Hz |
| Battery info (standard) | Power board → everyone | voltage, current, state of charge | 1 Hz |

IDs and byte layouts are still to be agreed with the power board team.

## Hardware

| Part | Choice | Status |
| --- | --- | --- |
| Flight controller | Cube Orange+ (ArduPilot) | Have |
| Companion computer | Raspberry Pi 3 B+| Have |
| Camera | Raspberry Pi Camera Module 3, standard lens, pointed down; its included 15-pin cable fits the Pi 3 | To buy |
| Downward LiDAR | Waveshare TOF MINIF Range Sensor, SKU 33346 (standard, 0.02–20 m, UART 115200, 30 Hz) | To buy |
| CAN interface | Waveshare RS485 CAN HAT (MCP2515) | To buy |
| GPS + compass | Holybro Micro M10 (SKU 12043), Cube GPS 2 | To buy |
| Storage | High-endurance microSD, 64 GB | To buy |
| Pi power | 5 V 3 A+ BEC (Pi 3 B+ needs 2.5 A), into GPIO 5 V or micro-USB | To buy |
| CAN cable | JST-GH 4-pin, Cube CAN 2 → HAT (no 5 V) | Check Cube cable set |
| Power board (on the drone) | Charge control + sensing, DroneCAN node | ME/EE team |
| Dock | Charging contacts, AprilTag pad, Wi-Fi AP, reference markers | ME/EE team |

No RTK: day to day image alignment absorbs normal GPS error.


## Drone sensors and connectivity

| Function | ArduPilot mode(s) | Sensor | Connected to | Notes |
| --- | --- | --- | --- | --- |
| Stabilize (attitude) | Stabilize, all modes | IMU: gyro + accelerometer | Inside the Cube Orange+ | Always on; no extra part |
| Altitude hold | AltHold, Loiter, Auto | Barometer (inside the Cube) + **downward LiDAR: Waveshare TOF MINIF, 20 m** | LiDAR on Cube TELEM 2 (UART) | Barometer holds altitude; the LiDAR adds true height above ground below 20 m (takeoff, landing). Survey altitude (40–60 m) is out of LiDAR range, and readings over water are unreliable |
| Position hold / navigation | Loiter, Auto, RTL | **GPS + compass**: Holybro Micro M10 | Cube GPS 2 | Waypoints, holding position in wind, return to dock |
| Vision | Precision landing (Lua guided descent) | **Camera Module 3**, nadir | Pi CSI port | Pi detects the AprilTag and sends LAND_TARGET offsets over CAN; also takes the survey images |
| Connectivity: onboard | All | **CAN HAT** (Waveshare RS485 CAN, MCP2515) | Pi ↔ Cube CAN 2 ↔ power board | DroneCAN bus for commands, drone state, charge status |
| Connectivity: dock | Docked | Pi 3 B+ built-in Wi-Fi (dual-band) | Dock Wi-Fi AP → laptop | Schedule, flight path, image uploads; no extra part |
| Connectivity: debug | Testing only | Unified RC + telemetry receiver | Cube TELEM 1 | Operator override + streamed drone state |
