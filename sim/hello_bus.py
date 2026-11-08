#!/usr/bin/env python3
"""First DroneCAN test: a fake Pi and a fake Cube talking over the bus.

Run two terminals on the same CAN interface:

    python3 sim/hello_bus.py cube --iface vcan0     # node 10, answers commands
    python3 sim/hello_bus.py pi   --iface vcan0     # node 20, sends ARM every 2 s

Pass: the "pi" side prints "ACK seq=N result=OK" for every command it sends.
Use --iface mcast:0 to run without a CAN interface (UDP multicast, any OS).
"""
import argparse
import os
import time

import dronecan

DSDL = os.path.join(os.path.dirname(__file__), "..", "dsdl", "capstone")
dronecan.load_dsdl(DSDL)
cap = dronecan.thirdparty.capstone

NODE_IDS = {"cube": 10, "pi": 20}


def run_cube(node):
    def on_cmd(event):
        msg = event.message
        print(f"[cube] DroneCmd command={msg.command} seq={msg.seq} from node {event.transfer.source_node_id}")
        node.broadcast(cap.CmdAck(seq=msg.seq, result=0, reason=0))

    node.add_handler(cap.DroneCmd, on_cmd)
    print("[cube] listening for DroneCmd ...")
    while True:
        node.spin(1)


def run_pi(node):
    acks = {}

    def on_ack(event):
        msg = event.message
        acks[msg.seq] = msg.result
        result = "OK" if msg.result == 0 else f"REFUSED reason={msg.reason}"
        print(f"[pi]   ACK seq={msg.seq} result={result}")

    node.add_handler(cap.CmdAck, on_ack)
    seq = 0
    while True:
        seq = (seq + 1) % 256
        node.broadcast(cap.DroneCmd(command=1, seq=seq))  # 1 = ARM
        print(f"[pi]   sent DroneCmd ARM seq={seq}")
        deadline = time.time() + 2.0
        while time.time() < deadline:
            node.spin(0.1)
        if seq not in acks:
            print(f"[pi]   no ACK for seq={seq} within 2 s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=NODE_IDS)
    ap.add_argument("--iface", default="vcan0", help="vcan0, can0, or mcast:0")
    args = ap.parse_args()
    node = dronecan.make_node(args.iface, node_id=NODE_IDS[args.role], bitrate=1000000)
    try:
        (run_cube if args.role == "cube" else run_pi)(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()


if __name__ == "__main__":
    main()
