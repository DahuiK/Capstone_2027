#!/usr/bin/env python3
"""Fake power board (DroneCAN node 30) for testing without the real board.

Broadcasts ChargeStatus at 1 Hz and answers ChargeCmd with CmdAck, using the
same message spec the real firmware will implement.

    python3 sim/fake_power_board.py --iface vcan0              # docked, charging
    python3 sim/fake_power_board.py --iface vcan0 --undocked   # drone away from dock

Behaviour:
  - STOP  -> charging off, contacts de-energized (contacts_live = False)
  - START -> refused unless docked; otherwise charging on, contacts live
"""
import argparse
import os
import time

import dronecan

DSDL = os.path.join(os.path.dirname(__file__), "..", "dsdl", "capstone")
dronecan.load_dsdl(DSDL)
cap = dronecan.thirdparty.capstone

START, STOP = 1, 2
OK, REFUSED = 0, 1
REASON_NONE, REASON_WRONG_STATE = 0, 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default="vcan0")
    ap.add_argument("--undocked", action="store_true")
    args = ap.parse_args()

    state = {"docked": not args.undocked, "charging": not args.undocked}
    state["contacts_live"] = state["charging"]

    node = dronecan.make_node(args.iface, node_id=30, bitrate=1000000)

    def on_charge_cmd(event):
        msg = event.message
        if msg.command == STOP:
            state["charging"] = False
            state["contacts_live"] = False
            result, reason = OK, REASON_NONE
        elif msg.command == START and state["docked"]:
            state["charging"] = True
            state["contacts_live"] = True
            result, reason = OK, REASON_NONE
        else:
            result, reason = REFUSED, REASON_WRONG_STATE
        print(f"[power] ChargeCmd {msg.command} seq={msg.seq} -> {'OK' if result == OK else 'REFUSED'}; state={state}")
        node.broadcast(cap.CmdAck(seq=msg.seq, result=result, reason=reason))

    node.add_handler(cap.ChargeCmd, on_charge_cmd)
    print(f"[power] node 30 on {args.iface}, state={state}")

    next_status = 0.0
    try:
        while True:
            if time.time() >= next_status:
                node.broadcast(cap.ChargeStatus(docked=state["docked"],
                                                contacts_live=state["contacts_live"],
                                                charging=state["charging"],
                                                fault_code=0))
                next_status = time.time() + 1.0
            node.spin(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()


if __name__ == "__main__":
    main()
