#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Fake Micro850: a Modbus TCP server that runs the cell's six-state sequencer and
answers it the way the two bridge scripts do. No ROS. Used to prove the Level 1
shadow end to end with no bench.

    ~/venvs/wafer_shadow/bin/python fake_plc.py --port 5020 --cycles 0

Register map = the bench's (protocol addresses; CCW shows them as 400001 etc.):
    holding  0 / 1    Pro 600  Cmd_Word   / Status_Word
    holding 10 / 11   M1 Pro   Cmd_Word_2 / Status_Word_2
    holding 20 / 21   reserved for the conveyor - always 0
    coils    0 / 1    Vac_On / Vac_Blow
Status codes: 0 idle, 1 busy, 2 done, 99 fault.

The sequencer (verbatim from the cell notes, Structured Text):
    0 idle -> Start_Cmd ->
    1 Cmd_Word_2 := 1,      wait Status_Word_2 = 2
    2 Cmd_Word_2 := 0,      wait Status_Word_2 = 0
    3 Run_Cmd := TRUE,      wait Move_Done            (conveyor index)
    4 Cmd_Word := 1,        wait Status_Word = 2
    5 Cmd_Word := 0,        wait Status_Word = 0      -> 0

Step, Start_Cmd, Run_Cmd and Move_Done are internal to the PLC and are NOT on
Modbus, exactly as on the bench. So during state 3 every register reads zero:
the belt phase is invisible to a Modbus reader, which must infer it from the
order of events (plc_bridge.py does). Mapping Step to a register would remove
that inference; it is on the ask list.

The Pro 600 bridge drives the vacuum coils itself: Vac_On at PICK, then at
DROP Vac_On off and a Vac_Blow pulse (Bridge.py). Timings default to the
bench's tuned values where the notes give them and to plausible move times
where they do not; all are flags.
"""
import argparse
import sys
import threading
import time
from pathlib import Path

VENV_SP = Path.home() / 'venvs' / 'wafer_shadow' / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
if VENV_SP.exists() and str(VENV_SP) not in sys.path:
    sys.path.insert(0, str(VENV_SP))

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext  # noqa: E402
from pymodbus.server import StartTcpServer  # noqa: E402

HR, CO = 3, 1                        # pymodbus function codes for getValues/setValues
P6_CMD, P6_STAT, M1_CMD, M1_STAT = 0, 1, 10, 11
VAC_ON, VAC_BLOW = 0, 1
IDLE, BUSY, DONE, FAULT = 0, 1, 2, 99
BRIDGE_LATENCY = 0.15                # bridge poll loop is 0.1 s; add a little


class FakeCell:
    def __init__(self, a):
        self.a = a
        self.ctx = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0] * 64),
            co=ModbusSequentialDataBlock(0, [0] * 16),
            di=ModbusSequentialDataBlock(0, [0] * 16),
            ir=ModbusSequentialDataBlock(0, [0] * 16),
            zero_mode=True)          # protocol address 0 == index 0, as pymodbus clients expect
        self.t0 = time.time()
        self.step = 0
        self.cycle = 0
        self.t_enter = time.time()
        self.events = []             # (t, what) for the run summary

    # ------------------------------------------------------------ registers
    def hr(self, addr, val=None):
        if val is None:
            return self.ctx.getValues(HR, addr, 1)[0]
        old = self.ctx.getValues(HR, addr, 1)[0]
        if old != val:
            self.ctx.setValues(HR, addr, [int(val)])
            self.log(f'holding[{addr:2d}] {old} -> {val}')

    def co(self, addr, val=None):
        if val is None:
            return bool(self.ctx.getValues(CO, addr, 1)[0])
        old = bool(self.ctx.getValues(CO, addr, 1)[0])
        if old != bool(val):
            self.ctx.setValues(CO, addr, [bool(val)])
            self.log(f'coil[{addr}] {int(old)} -> {int(bool(val))}')

    def log(self, msg):
        t = time.time() - self.t0
        self.events.append((t, msg))
        print(f'[{t:7.2f}s] {msg}', flush=True)

    # ------------------------------------------------------------ sequencer
    def enter(self, step):
        self.step = step
        self.t_enter = time.time()
        self.log(f'--- Step := {step}')

    def since(self):
        return time.time() - self.t_enter

    def run(self):
        a = self.a
        next_start = self.t0 + a.start_delay
        self.log(f'fake Micro850 up on port {a.port}; first cycle in {a.start_delay:.0f} s, '
                 f'{"endless" if a.cycles == 0 else str(a.cycles)} cycle(s)')
        while True:
            time.sleep(0.02)
            s = self.step
            if s == 0:
                if time.time() >= next_start and (a.cycles == 0 or self.cycle < a.cycles):
                    self.cycle += 1
                    self.log(f'===== cycle {self.cycle}: Start_Cmd (button)')
                    self.enter(1)
                    self.hr(M1_CMD, 1)
                elif a.cycles and self.cycle >= a.cycles and not getattr(self, '_finished', False):
                    self._finished = True
                    self.log('all cycles done; holding idle (Ctrl+C to stop)')
            elif s == 1:                                      # M1 Pro job 1, the fake bridge answers
                d = self.since()
                if d > BRIDGE_LATENCY and self.hr(M1_STAT) == IDLE:
                    self.hr(M1_STAT, BUSY)
                if a.fault_m1_cycle == self.cycle and d > a.m1_job * 0.6 and self.hr(M1_STAT) == BUSY:
                    self.hr(M1_STAT, FAULT)                   # e.g. the rotate-out stalled
                    self.log('M1 bridge: FAULT 99 - sequencer holds at Step 1 (as on the bench)')
                    self.t_fault = time.time()
                if self.hr(M1_STAT) == FAULT:
                    if a.fault_hold and time.time() - self.t_fault > a.fault_hold:
                        self.log('operator recovery: Ctrl+C bridges, force Step/Cmd to 0, clear coils')
                        self.hr(M1_CMD, 0); self.hr(M1_STAT, 0); self.enter(0)
                        next_start = time.time() + a.cycle_gap
                    continue
                if d > a.m1_job and self.hr(M1_STAT) == BUSY:
                    self.hr(M1_STAT, DONE)
                if self.hr(M1_STAT) == DONE:
                    self.enter(2)
                    self.hr(M1_CMD, 0)
            elif s == 2:                                      # acknowledge M1 Pro
                if self.since() > BRIDGE_LATENCY and self.hr(M1_STAT) == DONE:
                    self.hr(M1_STAT, IDLE)
                if self.hr(M1_STAT) == IDLE:
                    self.enter(3)
                    self.log('Run_Cmd := TRUE (internal, not on Modbus): MC_MoveRelative 170 @ 20')
            elif s == 3:                                      # conveyor index; nothing visible on Modbus
                if self.since() > a.belt:
                    self.log('Move_Done (internal)')
                    self.enter(4)
                    self.hr(P6_CMD, 1)
                    self.p6_marks = set()
            elif s == 4:                                      # Pro 600 job 1 with the vacuum coils
                d = self.since()
                if d > BRIDGE_LATENCY and self.hr(P6_STAT) == IDLE:
                    self.hr(P6_STAT, BUSY)
                t_pick = a.p6_approach
                t_lift = t_pick + a.p6_settle
                t_drop = t_lift + a.p6_traverse
                t_blow_off = t_drop + a.p6_blow
                t_done = t_blow_off + a.p6_return
                if d > t_pick and 'pick' not in self.p6_marks:
                    self.p6_marks.add('pick'); self.co(VAC_ON, True)
                if d > t_drop and 'drop' not in self.p6_marks:
                    self.p6_marks.add('drop'); self.co(VAC_ON, False); self.co(VAC_BLOW, True)
                if d > t_blow_off and 'blow' not in self.p6_marks:
                    self.p6_marks.add('blow'); self.co(VAC_BLOW, False)
                if d > t_done and self.hr(P6_STAT) == BUSY:
                    self.hr(P6_STAT, DONE)
                if self.hr(P6_STAT) == DONE:
                    self.enter(5)
                    self.hr(P6_CMD, 0)
            elif s == 5:                                      # acknowledge Pro 600, cycle complete
                if self.since() > BRIDGE_LATENCY and self.hr(P6_STAT) == DONE:
                    self.hr(P6_STAT, IDLE)
                if self.hr(P6_STAT) == IDLE:
                    self.log(f'===== cycle {self.cycle} complete: Start_Cmd := FALSE')
                    self.enter(0)
                    next_start = time.time() + a.cycle_gap


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=5020, help='502 needs root; the reader takes port:=')
    ap.add_argument('--cycles', type=int, default=0, help='0 = run forever')
    ap.add_argument('--start-delay', type=float, default=5.0)
    ap.add_argument('--cycle-gap', type=float, default=6.0, help='idle between cycles; the bench waits for a button')
    ap.add_argument('--m1-job', type=float, default=22.0, help='s for the SCARA transfer, 8 moves at SpeedFactor 15')
    ap.add_argument('--belt', type=float, default=8.5, help='s for MC_MoveRelative 170 @ 20 (Distance / Velocity)')
    ap.add_argument('--p6-approach', type=float, default=5.0, help='s HOME -> APPROACH -> PICK')
    ap.add_argument('--p6-settle', type=float, default=2.0, help='s vacuum settle at PICK (Bridge.py sleeps 2.0)')
    ap.add_argument('--p6-traverse', type=float, default=7.0, help='s lift, traverse, descend to DROP')
    ap.add_argument('--p6-blow', type=float, default=0.5, help='s Vac_Blow pulse (notes: 0.5, code: 0.1)')
    ap.add_argument('--p6-return', type=float, default=5.0, help='s DROP_OVER -> HOME')
    ap.add_argument('--fault-m1-cycle', type=int, default=0, help='inject Status 99 on the M1 Pro in this cycle (0 = never)')
    ap.add_argument('--fault-hold', type=float, default=8.0, help='s the fault is held before the fake operator recovers')
    a = ap.parse_args()

    cell = FakeCell(a)
    server = threading.Thread(
        target=StartTcpServer,
        kwargs=dict(context=ModbusServerContext(slaves=cell.ctx, single=True), address=(a.host, a.port)),
        daemon=True)
    server.start()
    time.sleep(0.5)
    try:
        cell.run()
    except KeyboardInterrupt:
        print('\nstopped', flush=True)


if __name__ == '__main__':
    main()
