#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
myCobot Pro 600 -> ROS 2 bridge.

    ros2 run wafer_cell_shadow pro600_bridge.py --ros-args -p source:=real -p ip:=192.168.1.159

Real mode: pymycobot.ElephantRobot(host, port) over TCP (verified in
elephantrobotics/pymycobot elephantrobot.py): get_angles() -> 6 floats in
degrees, get_coords() -> [x y z rx ry rz], get_digital_in(pin). The library
lives in the shadow venv (~/venvs/wafer_shadow); the bridge adds it to
sys.path in real mode only. Port 5001 is Elephant's documented default for
the Pro 600 socket server - UNVERIFIED on this bench.
Fake mode: replays the ideal cycle.

Publishes /shadow/pro600/joint_states (sim joint names, rad) and /shadow/pro600/raw.
Joint sign / zero conventions are UNKNOWN (metrology pro600_joint_zero_convention).
"""
import json, time
import rclpy
import rclpy.executors
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from shadow_common import (PRO600_JOINTS, pro600_real_to_sim, pro600_sim_to_real,
                           fake_cycle_state, declare_fake_params, use_venv)


class Pro600Bridge(Node):
    def __init__(self):
        super().__init__('pro600_bridge')
        self.declare_parameter('source', 'fake')
        self.declare_parameter('ip', '192.168.1.159')
        self.declare_parameter('port', 5001)
        self.declare_parameter('rate_hz', 20.0)
        self.declare_parameter('sign', [1.0] * 6)
        self.declare_parameter('offset', [0.0] * 6)
        self.declare_parameter('vacuum_input_pin', -1)     # DI pin of the pressure switch, if wired to the arm; -1 = none
        declare_fake_params(self)
        self.sign = list(self.get_parameter('sign').value)
        self.offset = list(self.get_parameter('offset').value)
        self.js_pub = self.create_publisher(JointState, '/shadow/pro600/joint_states', 10)
        self.raw_pub = self.create_publisher(String, '/shadow/pro600/raw', 10)
        self.robot = None
        src = self.get_parameter('source').value
        if src == 'real':
            if not use_venv():
                self.get_logger().error('shadow venv not found; python3 -m venv --system-site-packages ~/venvs/wafer_shadow && pip install pymycobot pycomm3')
            self.connect()
        else:
            self.cs, self.t0 = fake_cycle_state(self)
        self.create_timer(1.0 / float(self.get_parameter('rate_hz').value), self.tick)
        self.get_logger().info(f'pro600_bridge source={src}')

    def connect(self):
        from pymycobot import ElephantRobot
        ip, port = self.get_parameter('ip').value, int(self.get_parameter('port').value)
        try:
            self.robot = ElephantRobot(ip, port)
            self.robot.start_client()
            self.get_logger().info(f'connected to Pro 600 at {ip}:{port}')
        except Exception as e:                    # noqa: BLE001
            self.get_logger().warning(f'Pro 600 {ip}:{port}: {e}; will retry')
            self.robot = None

    def read(self):
        if self.get_parameter('source').value != 'real':
            st = self.cs.at(time.time() - self.t0)
            q_sim = dict(zip(PRO600_JOINTS, st['pro600']))
            return pro600_sim_to_real(q_sim, self.sign, self.offset), None, None
        if self.robot is None:
            self.connect()
            return None, None, None
        try:
            angles = self.robot.get_angles()
            coords = self.robot.get_coords()
            pin = int(self.get_parameter('vacuum_input_pin').value)
            vac = self.robot.get_digital_in(pin) if pin >= 0 else None
            return list(angles), list(coords), vac
        except Exception as e:                    # noqa: BLE001
            self.get_logger().warning(f'Pro 600 read failed: {e}')
            self.robot = None
            return None, None, None

    def tick(self):
        deg, coords, vac = self.read()
        if deg is None or len(deg) != 6:
            return
        sim = pro600_real_to_sim(deg, self.sign, self.offset)
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = PRO600_JOINTS
        msg.position = [sim[j] for j in PRO600_JOINTS]
        self.js_pub.publish(msg)
        self.raw_pub.publish(String(data=json.dumps(
            {'angles_deg': [round(v, 3) for v in deg], 'coords': coords, 'vacuum_in': vac})))


def main():
    rclpy.init()
    n = Pro600Bridge()
    try:
        rclpy.spin(n)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
