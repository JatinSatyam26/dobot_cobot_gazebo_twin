#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Level 1 (task-level) digital shadow: the simulated cell follows the PLC's
phases. Needs cell.launch.py running and plc_bridge.py publishing
/shadow/plc/phase (from the real Micro850 or from fake_plc.py).

    ros2 run wafer_cell_shadow task_shadow.py

For each phase the PLC reports, this plays the matching stretch of the
simulation's own cycle table (cell_plan.STEPS) through the joint trajectory
controllers - the same primitives cell_sequencer.py uses:

    M1_JOB      M1_BACK_HIGH .. M1_HOME       pick from the tower, place in the carrier
    BELT_INDEX  BELT_A_TO_B  .. BELT_B_TO_C   index to the far station
    P6_JOB      NEST_DETACH  .. P6_HOME       pick off the carrier, place in the far tower
    IDLE        BELT_RETURN_A, CYCLE_DONE, then the wafer is put back in the pick tower

The last line is a declared stand-in: on the bench the carriage is carried
back by hand and a fresh wafer is loaded by a person. Neither is on Modbus, so
the simulation does both during the idle gap and logs that it did.

Gating: phases queue up and play in order. The simulation cannot finish a
phase before the cell does (it waits for the next phase), but it can fall
behind if a real job is quicker than the simulated one - that is logged as
lag rather than hidden, and speed_scale can be lowered to catch up.
"""
import queue
import subprocess
import threading
import time
import rclpy
import rclpy.executors
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

import shadow_common  # noqa: F401  (puts the bringup lib dir on sys.path)
from cell_layout import WAFER_MODEL, WAFER_SPAWN
from cell_plan import STEPS
from cell_sequencer import Sequencer

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
SEGMENT = {                                # phase -> inclusive range of cell_plan step names
    'M1_JOB': ('M1_BACK_HIGH', 'M1_HOME'),
    'BELT_INDEX': ('BELT_A_TO_B', 'BELT_B_TO_C'),
    'P6_JOB': ('NEST_DETACH', 'P6_HOME'),
    'IDLE': ('BELT_RETURN_A', 'CYCLE_DONE'),
}
NAMES = [s[0] for s in STEPS]


def step_range(a, b):
    i, j = NAMES.index(a), NAMES.index(b)
    return STEPS[i:j + 1]


class TaskShadow(Sequencer):
    def __init__(self):
        super().__init__()
        self.declare_parameter('reset_wafer', True)       # put the wafer back in the pick tower at IDLE
        self.q = queue.Queue()
        self.cycles = 0
        self.busy = None
        self.create_subscription(String, '/shadow/plc/phase', self.on_phase, LATCHED)
        self.get_logger().info('task shadow up: waiting for /shadow/plc/phase')

    def on_phase(self, m):
        phase = m.data
        pending = self.q.qsize() + (1 if self.busy else 0)
        if phase in SEGMENT:
            if phase == 'IDLE' and self.cycles == 0 and self.busy is None and self.q.empty():
                self.get_logger().info('cell idle, nothing has run yet')
                return
            self.q.put(phase)
            if pending:
                self.get_logger().warning(f'phase {phase} arrived while {pending} segment(s) still playing: '
                                          f'the simulation is lagging the cell')
        elif phase == 'FAULT':
            self.get_logger().error('cell reports FAULT (status 99); the simulation holds where it is')
        else:
            self.get_logger().info(f'phase {phase}: no motion in this phase')

    # ------------------------------------------------------------ segments
    def play(self, phase):
        a, b = SEGMENT[phase]
        self.busy = phase
        self.get_logger().info(f'=== playing {phase}: {a} .. {b}')
        dwell = float(self.get_parameter('dwell_b').value)
        try:
            for name, kind, payload, dur in step_range(a, b):
                self.say(name)
                if kind == 'm1pro':
                    self.move('m1pro', self.m1[payload], dur)
                elif kind == 'pro600':
                    self.move('pro600', self.p6[payload], dur)
                elif kind == 'belt':
                    self.belt(*payload)
                elif kind == 'dwell':
                    if dwell > 0:
                        time.sleep(dwell)
                elif kind == 'grasp':
                    self.grab(payload[0], payload[1], settle=dur)
            if phase == 'IDLE':
                self.cycles += 1
                if bool(self.get_parameter('reset_wafer').value):
                    self.reload_wafer()
        except Exception as e:                    # noqa: BLE001
            self.get_logger().error(f'segment {phase} failed: {e}')
        finally:
            self.busy = None

    def reload_wafer(self):
        """Stand-in for the operator loading the next wafer into the pick tower."""
        self.release_all()
        x, y, z = WAFER_SPAWN
        req = f'name: "{WAFER_MODEL}", position: {{x: {x:.5f}, y: {y:.5f}, z: {z:.5f}}}, orientation: {{w: 1}}'
        r = subprocess.run(['gz', 'service', '-s', '/world/wafer_cell/set_pose', '--reqtype', 'gz.msgs.Pose',
                            '--reptype', 'gz.msgs.Boolean', '--timeout', '1500', '--req', req],
                           capture_output=True, text=True)
        ok = 'data: true' in r.stdout
        self.get_logger().info(f'wafer reloaded into the pick tower (operator stand-in): {ok}')

    def worker(self):
        while rclpy.ok():
            try:
                phase = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            self.play(phase)


def main():
    rclpy.init()
    node = TaskShadow()
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()
    time.sleep(1.0)
    node.release_all()
    try:
        node.worker()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
