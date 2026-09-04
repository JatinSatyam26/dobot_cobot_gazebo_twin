#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Save frames from an inspection camera at a fixed sim-time interval, with the
sim time in the file name, so a whole cycle can be reviewed as a contact sheet.

    ros2 run wafer_cell_bringup record_frames.py <out_dir> [topic] [interval_s]

Also appends every /cell/state change to <out_dir>/states.txt with sim time.
"""
import sys, os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


class Rec(Node):
    def __init__(self, out, topic, dt):
        super().__init__('record_frames')
        os.makedirs(out, exist_ok=True)
        self.out, self.dt, self.last, self.n = out, dt, -1e9, 0
        self.create_subscription(Image, topic, self.cb, 10)
        self.create_subscription(String, '/cell/state', self.st, 10)
        self.states = open(os.path.join(out, 'states.txt'), 'a')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def st(self, m):
        self.states.write(f'{self.now():8.2f}  {m.data}\n'); self.states.flush()

    def cb(self, m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if t - self.last < self.dt:
            return
        self.last = t
        from PIL import Image as P
        img = P.frombytes('RGB', (m.width, m.height), bytes(m.data))
        if m.encoding == 'bgr8':
            b, g, r = img.split(); img = P.merge('RGB', (r, g, b))
        img.save(os.path.join(self.out, f'f{self.n:04d}_t{t:07.2f}.jpg'), quality=85)
        self.n += 1


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/frames'
    topic = sys.argv[2] if len(sys.argv) > 2 else '/cell_cam'
    dt = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    rclpy.init()
    n = Rec(out, topic, dt)
    n.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
