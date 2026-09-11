#!/usr/bin/env python3
"""M1 Pro bridge — picks wafer, places it in the carrier on the conveyor."""

import socket, time
from pymodbus.client import ModbusTcpClient

PLC_IP, M1_IP = "192.168.10.10", "192.168.10.40"
CMD_REG, STAT_REG = 10, 11
IDLE, BUSY, DONE, FAULT = 0, 1, 2, 99
SPEED = 40

HOME = (314.38,  41.65, 157.12, 107.54)
P1   = (314.38,  41.65,  70.53, 107.54)
P2   = (314.13, 180.89,  70.53, 107.54)
P3   = (314.13, 180.89, 111.93, 107.54)
P4   = ( 69.49, 389.61, 110.40, 201.70)
P5   = ( 69.49, 389.61,  75.62, 201.70)
P6   = (203.78, 340.41,  75.62, 179.87)
P7   = (203.78, 340.41, 151.12, 179.87)


class M1:
    def __init__(self, ip):
        self.dash = socket.create_connection((ip, 29999), timeout=10)
        self.move = socket.create_connection((ip, 30003), timeout=60)

    def _send(self, sock, cmd):
        sock.sendall((cmd + "\n").encode())
        reply = sock.recv(1024).decode().strip()
        if reply and not reply.startswith("0,"):
            print(f"    warn: {cmd} -> {reply}")
        return reply

    def enable(self):
        self._send(self.dash, "ClearError()")
        self._send(self.dash, "EnableRobot()")
        time.sleep(2)
        self._send(self.dash, f"SpeedFactor({SPEED})")

    def goto(self, pose, label):
        x, y, z, r = pose
        print(f"  -> {label}")
        self._send(self.move, f"MovJ({x},{y},{z},{r})")
        self._send(self.move, "Sync()")


def job_transfer(m1):
    m1.goto(P1,   "descend to wafer")
    m1.goto(P2,   "traverse")
    m1.goto(P3,   "lift")
    m1.goto(P4,   "over conveyor")
    m1.goto(P5,   "descend into carrier")
    m1.goto(P6,   "rotate")
    m1.goto(P7,   "withdraw")
    m1.goto(HOME, "home")


def job_home(m1):
    m1.goto(HOME, "home")


JOBS = {1: ("wafer transfer", job_transfer),
        2: ("go home",        job_home)}


def main():
    m1 = M1(M1_IP)
    m1.enable()
    print("M1 Pro enabled")

    plc = ModbusTcpClient(PLC_IP, port=502)
    if not plc.connect():
        print("could not reach PLC")
        return
    plc.write_register(STAT_REG, IDLE)
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
                fn(m1)
                plc.write_register(STAT_REG, DONE)
                print("  done, waiting for PLC to clear")
            except Exception as e:
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
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")