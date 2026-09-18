#!/usr/bin/env python3
"""Watch PLC holding registers and print every change.

    python3 watch_reg.py 30           # Step_Mirror
    python3 watch_reg.py 30 0 1 10 11 # step + both robot command/status pairs

Protocol address = the 4xxxxx number minus 400001.
    400001 -> 0    400002 -> 1     Pro 600  command / status
    400011 -> 10   400012 -> 11    M1 Pro   command / status
    400021 -> 20   400022 -> 21    laser    command / status
    400031 -> 30                   Step_Mirror

Status values: 0 idle, 1 busy, 2 done, 99 fault.

Sequencer states (SIX today -- the laser will add more and may renumber,
so read this from a table you can edit, don't hardcode it):
    0 idle   1 M1 transfer   2 ack M1
    3 conveyor index         4 Pro 600 pick/place    5 ack Pro 600

READ-ONLY BY CONVENTION, NOT BY CONSTRUCTION.
Nothing here writes, but `plc` is a full Modbus client and the PLC has no
concept of a read-only peer. A stray write to register 0 or 10 during a
cycle would command a robot to move. Do not add writes to this file.
"""

import sys, time
from pymodbus.client import ModbusTcpClient

PLC_IP = "192.168.10.10"
POLL_S = 0.05                  # 20 Hz


def read_reg(plc, addr):
    """pymodbus changed this signature across 3.x releases. Try the forms."""
    for attempt in (
        lambda: plc.read_holding_registers(address=addr, count=1),
        lambda: plc.read_holding_registers(addr, count=1),
        lambda: plc.read_holding_registers(addr, 1),
    ):
        try:
            return attempt()
        except TypeError:
            continue
    raise RuntimeError("no working read_holding_registers signature found")


regs = [int(a) for a in sys.argv[1:] if a.lstrip("-").isdigit()] or [30]

plc = ModbusTcpClient(PLC_IP, port=502)
if not plc.connect():
    print(f"could not reach PLC at {PLC_IP}")
    raise SystemExit

print(f"watching registers {regs} - Ctrl+C to stop\n")

last = None
errors = 0
t0 = time.time()

try:
    while True:
        vals = []
        ok = True
        for r in regs:
            rr = read_reg(plc, r)
            if rr.isError():
                ok = False
                errors += 1
                if errors % 20 == 1:
                    print(f"{time.time() - t0:8.2f}s   read error on {r} "
                          f"({errors} total)")
                break
            vals.append(rr.registers[0])

        if ok and vals != last:
            shown = "  ".join(f"{r}={v}" for r, v in zip(regs, vals))
            print(f"{time.time() - t0:8.2f}s   {shown}")
            last = vals

        time.sleep(POLL_S)

except KeyboardInterrupt:
    print(f"\nstopped, {errors} read errors")
finally:
    plc.close()
