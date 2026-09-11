#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Allen-Bradley Micro850 -> ROS 2, over Modbus TCP, READ-ONLY.

    ros2 run wafer_cell_shadow plc_bridge.py --ros-args -p source:=real -p ip:=192.168.10.10
    ros2 run wafer_cell_shadow plc_bridge.py --ros-args -p source:=real -p ip:=127.0.0.1 -p port:=5020   # fake_plc.py

The cell publishes its whole state as Modbus registers and two bridge scripts
already read them; this node is a third client that only ever reads. It never
writes a register or a coil.

Register map (protocol addresses; the CCW mapping table shows 400001 etc.):
    holding  0 / 1    Pro 600  Cmd_Word   / Status_Word
    holding 10 / 11   M1 Pro   Cmd_Word_2 / Status_Word_2
    coils    0 / 1    Vac_On / Vac_Blow
Status: 0 idle, 1 busy, 2 done, 99 fault.

Cell phase is DERIVED from those six values, mirroring the PLC's six-state
sequencer one for one:
    IDLE        nothing commanded, nothing reported
    M1_JOB      Cmd_Word_2 = 1                      (Step 1; M1_DONE once Status_Word_2 = 2)
    M1_ACK      Cmd_Word_2 = 0, Status_Word_2 = 2   (Step 2)
    BELT_INDEX  all zero, AFTER the M1 half         (Step 3)  <- inference, see below
    P6_JOB      Cmd_Word = 1                        (Step 4; P6_DONE once Status_Word = 2)
    P6_ACK      Cmd_Word = 0, Status_Word = 2       (Step 5)
    FAULT       either status = 99
The belt phase is invisible on Modbus (Run_Cmd / Move_Done are internal), so
"all registers zero" means BELT_INDEX if the M1 half just finished and IDLE
otherwise. That is the one inference here; a Step register would remove it.

Publishes
  /shadow/plc/phase        std_msgs/String   the six names above (latched, on change)
  /shadow/plc/step         std_msgs/Int32    0..5, 99 (latched, on change)
  /shadow/plc/state        std_msgs/String   a cell_plan step name, for shadow_driver.py (latched)
  /shadow/plc/belt_run     std_msgs/Bool     phase == BELT_INDEX
  /shadow/plc/vacuum_on    std_msgs/Bool     coil 0
  /shadow/plc/blow         std_msgs/Bool     coil 1
  /shadow/plc/belt_reverse std_msgs/Bool     always False - the belt runs one way
  /shadow/plc/raw          std_msgs/String   JSON of every value read
Fake mode (source:=fake) replays the ideal cycle from cell_plan as before.
"""
import json
import time
import rclpy
import rclpy.executors
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import Bool, Int32, String

from shadow_common import declare_fake_params, fake_cycle_state, use_venv

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
IDLE, BUSY, DONE, FAULT = 0, 1, 2, 99

# fake-mode helpers (cell_plan step names)
BELT_STEPS = {'BELT_A_TO_B', 'BELT_B_TO_C'}          # MANUAL_RETURN_A is not a PLC move
VACUUM_STEPS = {'CUP_ATTACH', 'P6_LIFT', 'P6_TO_BLUE', 'P6_PLACE'}

STEP_OF = {'IDLE': 0, 'M1_JOB': 1, 'M1_DONE': 1, 'M1_ACK': 2, 'BELT_INDEX': 3,
           'P6_JOB': 4, 'P6_DONE': 4, 'P6_ACK': 5, 'FAULT': 99}
# what the old time-replay driver understands: the first cell_plan step of each phase
STATE_OF = {'M1_JOB': 'M1_DESCEND', 'M1_DONE': 'M1_HOME', 'M1_ACK': 'M1_HOME',
            'BELT_INDEX': 'BELT_A_TO_B', 'P6_JOB': 'P6_TO_C', 'P6_DONE': 'P6_HOME',
            'P6_ACK': 'P6_HOME', 'IDLE': 'CYCLE_DONE', 'FAULT': 'FAULT'}
M1_HALF = {'M1_JOB', 'M1_DONE', 'M1_ACK', 'BELT_INDEX'}


def derive_phase(m1_cmd, m1_st, p6_cmd, p6_st, prev):
    """The six PLC states from the four registers; see the module docstring."""
    if FAULT in (m1_st, p6_st):
        return 'FAULT'
    if m1_cmd == 1:
        return 'M1_DONE' if m1_st == DONE else 'M1_JOB'
    if p6_cmd == 1:
        return 'P6_DONE' if p6_st == DONE else 'P6_JOB'
    if m1_st == DONE:
        return 'M1_ACK'
    if p6_st == DONE:
        return 'P6_ACK'
    return 'BELT_INDEX' if prev in M1_HALF else 'IDLE'


class PlcBridge(Node):
    def __init__(self):
        super().__init__('plc_bridge')
        self.declare_parameter('source', 'fake')
        self.declare_parameter('ip', '192.168.10.10')
        self.declare_parameter('port', 502)
        self.declare_parameter('unit', 1)
        self.declare_parameter('rate_hz', 20.0)
        self.declare_parameter('reg_p6_cmd', 0)
        self.declare_parameter('reg_p6_status', 1)
        self.declare_parameter('reg_m1_cmd', 10)
        self.declare_parameter('reg_m1_status', 11)
        self.declare_parameter('coil_vac_on', 0)
        self.declare_parameter('coil_vac_blow', 1)
        declare_fake_params(self)

        self.phase_pub = self.create_publisher(String, '/shadow/plc/phase', LATCHED)
        self.step_pub = self.create_publisher(Int32, '/shadow/plc/step', LATCHED)
        self.state_pub = self.create_publisher(String, '/shadow/plc/state', LATCHED)
        self.belt_pub = self.create_publisher(Bool, '/shadow/plc/belt_run', 10)
        self.vac_pub = self.create_publisher(Bool, '/shadow/plc/vacuum_on', 10)
        self.blow_pub = self.create_publisher(Bool, '/shadow/plc/blow', 10)
        self.rev_pub = self.create_publisher(Bool, '/shadow/plc/belt_reverse', 10)
        self.raw_pub = self.create_publisher(String, '/shadow/plc/raw', 10)

        self.plc = None
        self.phase = None
        self.last_state = None
        self.cycles_seen = 0
        self.next_retry = 0.0
        self.fail_count = 0
        src = self.get_parameter('source').value
        if src == 'real':
            if not use_venv():
                self.get_logger().error('shadow venv not found: ~/venvs/wafer_shadow with pymodbus==3.6.9')
            self.connect()
        else:
            self.cs, self.t0 = fake_cycle_state(self)
        self.create_timer(1.0 / float(self.get_parameter('rate_hz').value), self.tick)
        self.get_logger().info(f'plc_bridge source={src} (read-only Modbus TCP client)')

    # ------------------------------------------------------------ Modbus
    def connect(self):
        from pymodbus.client import ModbusTcpClient
        ip, port = self.get_parameter('ip').value, int(self.get_parameter('port').value)
        try:
            c = ModbusTcpClient(ip, port=port, timeout=2)
            if not c.connect():
                raise ConnectionError('connect() returned False')
            self.plc = c
            self.fail_count = 0
            self.get_logger().info(f'connected to PLC {ip}:{port}')
        except Exception as e:                    # noqa: BLE001
            self.plc = None
            self.next_retry = time.time() + 3.0
            self.get_logger().warning(f'PLC {ip}:{port}: {e}; retry in 3 s')

    def read_registers(self):
        """-> dict of the six values, or None on a failed read."""
        p = self.get_parameter
        unit = int(p('unit').value)
        regs = [int(p(k).value) for k in ('reg_p6_cmd', 'reg_p6_status', 'reg_m1_cmd', 'reg_m1_status')]
        coils = [int(p(k).value) for k in ('coil_vac_on', 'coil_vac_blow')]
        lo, hi = min(regs), max(regs)
        clo, chi = min(coils), max(coils)
        try:
            rr = self.plc.read_holding_registers(lo, count=hi - lo + 1, slave=unit)
            rc = self.plc.read_coils(clo, count=chi - clo + 1, slave=unit)
            if rr.isError() or rc.isError():
                raise IOError(f'modbus error: {rr if rr.isError() else rc}')
        except Exception as e:                    # noqa: BLE001
            self.fail_count += 1
            if self.fail_count in (1, 10) or self.fail_count % 100 == 0:
                self.get_logger().warning(f'PLC read failed ({self.fail_count}): {e}')
            try:
                self.plc.close()
            except Exception:                     # noqa: BLE001
                pass
            self.plc = None
            self.next_retry = time.time() + 2.0
            return None
        self.fail_count = 0
        h = lambda addr: int(rr.registers[addr - lo])          # noqa: E731
        c = lambda addr: bool(rc.bits[addr - clo])              # noqa: E731
        return {'p6_cmd': h(regs[0]), 'p6_status': h(regs[1]),
                'm1_cmd': h(regs[2]), 'm1_status': h(regs[3]),
                'vac_on': c(coils[0]), 'vac_blow': c(coils[1])}

    # ------------------------------------------------------------ loop
    def tick(self):
        if self.get_parameter('source').value != 'real':
            st = self.cs.at(time.time() - self.t0)
            self.publish_fake(st)
            return
        if self.plc is None:
            if time.time() >= self.next_retry:
                self.connect()
            return
        v = self.read_registers()
        if v is None:
            return
        phase = derive_phase(v['m1_cmd'], v['m1_status'], v['p6_cmd'], v['p6_status'], self.phase)
        if phase != self.phase:
            if phase == 'IDLE' and self.phase == 'P6_ACK':
                self.cycles_seen += 1
            self.get_logger().info(f'phase {self.phase} -> {phase}   '
                                   f'(m1 {v["m1_cmd"]}/{v["m1_status"]}  p6 {v["p6_cmd"]}/{v["p6_status"]}  '
                                   f'vac {int(v["vac_on"])} blow {int(v["vac_blow"])})')
            self.phase = phase
            self.phase_pub.publish(String(data=phase))
            self.step_pub.publish(Int32(data=STEP_OF[phase]))
            state = STATE_OF[phase]
            if phase == 'IDLE' and self.cycles_seen == 0:
                state = 'RELEASE_ALL'                  # nothing has run yet: the old driver detaches everything
            if state != self.last_state:
                self.last_state = state
                self.state_pub.publish(String(data=state))
        self.belt_pub.publish(Bool(data=phase == 'BELT_INDEX'))
        self.vac_pub.publish(Bool(data=v['vac_on']))
        self.blow_pub.publish(Bool(data=v['vac_blow']))
        self.rev_pub.publish(Bool(data=False))
        v.update(phase=phase, step=STEP_OF[phase], cycles_seen=self.cycles_seen)
        self.raw_pub.publish(String(data=json.dumps(v)))

    def publish_fake(self, st):
        step = st['step']
        self.belt_pub.publish(Bool(data=step in BELT_STEPS))
        self.vac_pub.publish(Bool(data=step in VACUUM_STEPS))
        self.blow_pub.publish(Bool(data=False))
        self.rev_pub.publish(Bool(data=False))
        self.raw_pub.publish(String(data=json.dumps({'t': round(st['t'], 2), 'holder': st['holder'], 'step': step})))
        if step != self.last_state:
            self.last_state = step
            self.state_pub.publish(String(data=step))


def main():
    rclpy.init()
    n = PlcBridge()
    try:
        rclpy.spin(n)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
