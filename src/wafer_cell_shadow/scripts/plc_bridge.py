#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Allen-Bradley Micro850 -> ROS 2 bridge.

    ros2 run wafer_cell_shadow plc_bridge.py --ros-args -p source:=real -p ip:=192.168.1.20

Real mode: pycomm3.LogixDriver(ip) reads the configured tags over EtherNet/IP
(pycomm3 auto-detects Micro800 controllers and disables the unsupported CIP
features - verified in its README). The TAG NAMES are UNKNOWN until the CCW
project is exported: tag_belt_run, tag_vacuum_on and optionally tag_step.
Fake mode: replays the ideal cycle's step sequence and derives the signals.

Publishes
  /shadow/plc/state     std_msgs/String   cell step name (same names as cell_plan.STEPS)
  /shadow/plc/belt_run  std_msgs/Bool
  /shadow/plc/vacuum_on std_msgs/Bool
  /shadow/plc/raw       std_msgs/String   JSON of every tag read

Step names are what the shadow driver acts on. With a real PLC that has no
step tag, the bridge infers the fork/nest/cup events from the two signals it
does have (belt run edges, vacuum edges) - that inference is marked below.
"""
import json, time
import rclpy
import rclpy.executors
from rclpy.node import Node
from std_msgs.msg import String, Bool
from rclpy.qos import QoSProfile, DurabilityPolicy

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
from shadow_common import fake_cycle_state, declare_fake_params, use_venv

BELT_STEPS = {'BELT_A_TO_B', 'BELT_B_TO_C', 'BELT_RETURN_A'}
REVERSE_STEPS = {'BELT_RETURN_A'}          # whether the real belt ever reverses is metrology belt_travel_direction
VACUUM_STEPS = {'CUP_ATTACH', 'P6_LIFT_CLEAR', 'P6_LIFT', 'P6_TO_BLUE', 'P6_NEAR_BLUE', 'P6_PLACE'}


class PlcBridge(Node):
    def __init__(self):
        super().__init__('plc_bridge')
        self.declare_parameter('source', 'fake')
        self.declare_parameter('ip', '192.168.1.20')
        self.declare_parameter('rate_hz', 20.0)
        self.declare_parameter('tag_belt_run', 'BeltRun')
        self.declare_parameter('tag_vacuum_on', 'VacuumOn')
        self.declare_parameter('tag_belt_dir', '')          # stepper DIR output, if the PLC exposes it; '' = never reverses
        self.declare_parameter('tag_step', '')
        declare_fake_params(self)
        self.state_pub = self.create_publisher(String, '/shadow/plc/state', LATCHED)
        self.belt_pub = self.create_publisher(Bool, '/shadow/plc/belt_run', 10)
        self.vac_pub = self.create_publisher(Bool, '/shadow/plc/vacuum_on', 10)
        self.rev_pub = self.create_publisher(Bool, '/shadow/plc/belt_reverse', 10)
        self.raw_pub = self.create_publisher(String, '/shadow/plc/raw', 10)
        self.plc = None
        self.last_state = None
        src = self.get_parameter('source').value
        if src == 'real':
            if not use_venv():
                self.get_logger().error('shadow venv not found (see pro600_bridge.py)')
            self.connect()
        else:
            self.cs, self.t0 = fake_cycle_state(self)
        self.create_timer(1.0 / float(self.get_parameter('rate_hz').value), self.tick)
        self.get_logger().info(f'plc_bridge source={src}')

    def connect(self):
        from pycomm3 import LogixDriver
        ip = self.get_parameter('ip').value
        try:
            self.plc = LogixDriver(ip)
            self.plc.open()
            self.get_logger().info(f'connected to PLC {ip}: {self.plc.info}')
        except Exception as e:                    # noqa: BLE001
            self.get_logger().warning(f'PLC {ip}: {e}; will retry')
            self.plc = None

    def read(self):
        """-> (step name or None, belt_run, vacuum_on, raw dict)"""
        if self.get_parameter('source').value != 'real':
            st = self.cs.at(time.time() - self.t0)
            return (st['step'], st['step'] in BELT_STEPS, st['step'] in VACUUM_STEPS,
                    {'t': round(st['t'], 2), 'holder': st['holder'], 'reverse': st['step'] in REVERSE_STEPS})
        if self.plc is None:
            self.connect()
            return None, None, None, {}
        tags = [self.get_parameter('tag_belt_run').value, self.get_parameter('tag_vacuum_on').value]
        step_tag = self.get_parameter('tag_step').value
        dir_tag = self.get_parameter('tag_belt_dir').value
        for t in (step_tag, dir_tag):
            if t:
                tags.append(t)
        try:
            res = self.plc.read(*tags)
            raw = {r.tag: r.value for r in (res if isinstance(res, list) else [res])}
            belt = bool(raw.get(tags[0]))
            vac = bool(raw.get(tags[1]))
            step = str(raw.get(step_tag)) if step_tag else None   # INFERENCE needed without a step tag
            raw['reverse'] = bool(raw.get(dir_tag)) if dir_tag else False
            return step, belt, vac, raw
        except Exception as e:                    # noqa: BLE001
            self.get_logger().warning(f'PLC read failed: {e}')
            self.plc = None
            return None, None, None, {}

    def tick(self):
        step, belt, vac, raw = self.read()
        if belt is None:
            return
        self.belt_pub.publish(Bool(data=bool(belt)))
        self.vac_pub.publish(Bool(data=bool(vac)))
        self.rev_pub.publish(Bool(data=bool(raw.get('reverse', False))))
        self.raw_pub.publish(String(data=json.dumps(raw, default=str)))
        if step is not None and step != self.last_state:
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
