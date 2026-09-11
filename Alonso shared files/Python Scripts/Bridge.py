#!/usr/bin/env python3
"""Pro 600 bridge — picks wafer off conveyor, places at drop zone.
   Instrumented version: reports vacuum coil states at each stage."""

import time
from pymodbus.client import ModbusTcpClient
from pymycobot import ElephantRobot

PLC_IP, ROBOT_IP = "192.168.10.10", "192.168.10.20"
CMD_REG, STAT_REG = 0, 1
VAC_ON, VAC_BLOW = 0, 1            # Modbus coil addresses
IDLE, BUSY, DONE, FAULT = 0, 1, 2, 99
SPEED = 1900

HOME      = [ -81.287, -102.418, 130.242, -118.125, -89.736,  -2.109]
APPROACH  = [-105.256,  -54.941,  90.283, -124.980, -89.561, -25.928]
PICK      = [-105.726,  -50.312,  91.511, -132.451, -89.561, -25.928]
DROP_OVER = [ -41.208,  -64.017, 111.022, -137.197, -89.912,  38.320]
DROP      = [ -40.992,  -61.481, 109.381, -135.791, -89.912,  38.848]


def goto(arm, pose, label):
    print(f"  -> {label}")
    arm.write_angles(pose, SPEED)
    arm.command_wait_done()
    time.sleep(0.5)


def vac_state(plc, where):
    rr = plc.read_coils(0, count=2)
    if not rr.isError():
        print(f"    [{where}] Vac_On={rr.bits[0]}  Vac_Blow={rr.bits[1]}")
    else:
        print(f"    [{where}] coil read error")


def job_transfer(arm, plc):
    vac_state(plc, "start")
    goto(arm, APPROACH,  "over wafer")
    vac_state(plc, "at approach")

    goto(arm, PICK,      "down to wafer")
    plc.write_coil(VAC_ON, True)
    time.sleep(2.0)
    vac_state(plc, "after vac on")

    goto(arm, APPROACH,  "lift")
    vac_state(plc, "after lift")

    goto(arm, DROP_OVER, "traverse")
    vac_state(plc, "after traverse")

    goto(arm, DROP,      "down to drop")
    vac_state(plc, "at drop")

    plc.write_coil(VAC_ON, False)
    plc.write_coil(VAC_BLOW, True)
    time.sleep(0.1)
    plc.write_coil(VAC_BLOW, False)
    vac_state(plc, "after blow")

    goto(arm, DROP_OVER, "lift")
    goto(arm, HOME,      "home")


def job_home(arm, plc):
    goto(arm, HOME, "home")


JOBS = {1: ("wafer pick and place", job_transfer),
        2: ("go home",              job_home)}


def main():
    arm = ElephantRobot(ROBOT_IP, 5001)
    arm.start_client()
    time.sleep(1)
    print("robot connected, at", arm.get_angles())

    plc = ModbusTcpClient(PLC_IP, port=502)
    if not plc.connect():
        print("could not reach PLC")
        return
    print("PLC connected")

    plc.write_register(STAT_REG, IDLE)
    plc.write_coil(VAC_ON, False)
    plc.write_coil(VAC_BLOW, False)
    vac_state(plc, "startup")
    print("waiting for commands...\n")

    last_unknown = None
    while True:
        rr = plc.read_holding_registers(CMD_REG, count=1)
        if rr.isError():
            time.sleep(0.5)
            continue

        cmd = rr.registers[0]

        if cmd in JOBS:
            name, fn = JOBS[cmd]
            print(f"command {cmd}: {name}")
            plc.write_register(STAT_REG, BUSY)
            try:
                fn(arm, plc)
                plc.write_register(STAT_REG, DONE)
                print("  done, waiting for PLC to clear")
            except Exception as e:
                plc.write_coil(VAC_ON, False)
                plc.write_coil(VAC_BLOW, False)
                plc.write_register(STAT_REG, FAULT)
                print("  FAULT:", e)

            while True:
                rr = plc.read_holding_registers(CMD_REG, count=1)
                if not rr.isError() and rr.registers[0] == 0:
                    break
                time.sleep(0.1)

            plc.write_register(STAT_REG, IDLE)
            print("  idle\n")

        elif cmd != 0 and cmd != last_unknown:
            print(f"unknown command {cmd}, ignoring")
            last_unknown = cmd

        time.sleep(0.1)


if __name__ == "__main__":
    plc_cleanup = ModbusTcpClient(PLC_IP, port=502)
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        if plc_cleanup.connect():
            plc_cleanup.write_coil(VAC_ON, False)
            plc_cleanup.write_coil(VAC_BLOW, False)
            plc_cleanup.close()