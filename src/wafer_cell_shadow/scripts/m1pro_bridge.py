#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Dobot M1 Pro -> ROS 2 bridge (one third of the Digital Shadow).

    ros2 run wafer_cell_shadow m1pro_bridge.py --ros-args -p source:=real -p ip:=192.168.1.6

Real mode: connects to the controller's real-time feedback port (30004) and
parses the 1440-byte RealTimeData packet (layout verified in
Dobot-Arm/M1Pro-ROS bringup/include/bringup/commander.h): len uint16 @0,
digital_input_bits uint64 @8, digital_outputs @16, robot_mode @24,
q_actual double[6] @432, tool_vector_actual double[6] @624.
Fake mode: replays the ideal cycle (cell_plan) as the robot would report it.

Publishes
  /shadow/m1pro/joint_states   sensor_msgs/JointState  (sim joint names, rad / m)
  /shadow/m1pro/raw            std_msgs/String         JSON of the device-native values
UNKNOWN until one single-joint jog per axis: the sign of each axis, the Z zero,
and whether J3 is reported in mm (Dobot's ROS driver runs deg2rad on all six).
"""
import json, socket, struct, time, threading
import rclpy
import rclpy.executors
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from shadow_common import (M1PRO_JOINTS, m1pro_real_to_sim, m1pro_sim_to_real,
                           fake_cycle_state, declare_fake_params)

PACKET = 1440
OFF_LEN, OFF_DI, OFF_DO, OFF_MODE, OFF_Q, OFF_TCP = 0, 8, 16, 24, 432, 624


class M1ProBridge(Node):
    def __init__(self):
        super().__init__('m1pro_bridge')
        self.declare_parameter('source', 'fake')
        self.declare_parameter('ip', '192.168.1.6')
        self.declare_parameter('feedback_port', 30004)
        self.declare_parameter('rate_hz', 50.0)
        self.declare_parameter('sign', [1.0, 1.0, 1.0, 1.0])
        self.declare_parameter('offset', [0.0, 0.0, 0.0, 0.0])
        self.declare_parameter('z_unit_mm', True)
        declare_fake_params(self)
        self.sign = list(self.get_parameter('sign').value)
        self.offset = list(self.get_parameter('offset').value)
        self.js_pub = self.create_publisher(JointState, '/shadow/m1pro/joint_states', 10)
        self.raw_pub = self.create_publisher(String, '/shadow/m1pro/raw', 10)
        self.latest = None                     # (q_dobot[4], mode, di, tcp[6])
        src = self.get_parameter('source').value
        if src == 'real':
            threading.Thread(target=self.reader, daemon=True).start()
        else:
            self.cs, self.t0 = fake_cycle_state(self)
        self.create_timer(1.0 / float(self.get_parameter('rate_hz').value), self.tick)
        self.get_logger().info(f'm1pro_bridge source={src}')

    # ---------------------------------------------------------------- real
    def reader(self):
        ip, port = self.get_parameter('ip').value, int(self.get_parameter('feedback_port').value)
        while rclpy.ok():
            try:
                with socket.create_connection((ip, port), timeout=5.0) as s:
                    self.get_logger().info(f'connected to {ip}:{port}')
                    buf = b''
                    while rclpy.ok():
                        chunk = s.recv(4096)
                        if not chunk:
                            raise ConnectionError('closed')
                        buf += chunk
                        while len(buf) >= PACKET:
                            pkt, buf = buf[:PACKET], buf[PACKET:]
                            if struct.unpack_from('<H', pkt, OFF_LEN)[0] != PACKET:
                                buf = b''          # lost sync; resync on the next packet
                                break
                            q = struct.unpack_from('<6d', pkt, OFF_Q)
                            di = struct.unpack_from('<Q', pkt, OFF_DI)[0]
                            mode = struct.unpack_from('<Q', pkt, OFF_MODE)[0]
                            tcp = struct.unpack_from('<6d', pkt, OFF_TCP)
                            self.latest = (list(q[:4]), mode, di, list(tcp))
            except Exception as e:                # noqa: BLE001
                self.get_logger().warning(f'{ip}:{port}: {e}; retrying in 3 s')
                time.sleep(3.0)

    # ---------------------------------------------------------------- fake
    def fake_read(self):
        st = self.cs.at(time.time() - self.t0)
        q_sim = dict(zip(M1PRO_JOINTS, st['m1pro']))
        q_dobot = m1pro_sim_to_real(q_sim, self.sign, self.offset)
        if not self.get_parameter('z_unit_mm').value:
            q_dobot[2] /= 1000.0
        return (q_dobot, 5, 0, [0.0] * 6)

    # ---------------------------------------------------------------- publish
    def tick(self):
        data = self.latest if self.get_parameter('source').value == 'real' else self.fake_read()
        if data is None:
            return
        q_dobot, mode, di, tcp = data
        q = list(q_dobot)
        if not self.get_parameter('z_unit_mm').value:
            q[2] *= 1000.0                     # bridge expects mm for J3
        sim = m1pro_real_to_sim(q, self.sign, self.offset)
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = M1PRO_JOINTS
        msg.position = [sim[j] for j in M1PRO_JOINTS]
        self.js_pub.publish(msg)
        self.raw_pub.publish(String(data=json.dumps(
            {'q_dobot': [round(v, 3) for v in q_dobot], 'robot_mode': mode, 'di': di,
             'tcp': [round(v, 2) for v in tcp]})))


def main():
    rclpy.init()
    n = M1ProBridge()
    try:
        rclpy.spin(n)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
