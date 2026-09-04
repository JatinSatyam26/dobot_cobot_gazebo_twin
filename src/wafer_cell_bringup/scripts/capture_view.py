#!/usr/bin/env python3
"""
Save one frame from the world's inspection camera to a PNG.

Exists because this project spent hours shipping changes that passed every
numeric check and were visually broken — an invisible robot, arms collapsed
under gravity. Headless tests cannot catch those. This can.

    ros2 run wafer_cell_bringup capture_view.py [output.png] [topic]

Topics: /cell_cam (front three-quarter) and /plan_cam (straight down).
"""
import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class Grab(Node):
    def __init__(self, out, topic='/cell_cam'):
        super().__init__('capture_view')
        self.out, self.got = out, False
        self.create_subscription(Image, topic, self.cb, 10)
        self.create_timer(20.0, self.timeout)

    def cb(self, m):
        if self.got:
            return
        self.got = True
        try:
            from PIL import Image as PImage
        except ImportError:
            sys.exit('PIL not available: pip install pillow')
        mode = {'rgb8': 'RGB', 'bgr8': 'RGB'}.get(m.encoding)
        if mode is None:
            sys.exit(f'unhandled encoding {m.encoding}')
        img = PImage.frombytes(mode, (m.width, m.height), bytes(m.data))
        if m.encoding == 'bgr8':
            b, g, r = img.split()
            img = PImage.merge('RGB', (r, g, b))
        img.save(self.out)
        print(f'saved {self.out}  ({m.width}x{m.height}, {m.encoding})')
        raise SystemExit(0)

    def timeout(self):
        sys.exit('no image within 20 s — is the sim running and the '
                 'image bridge up?')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cell_view.png'
    topic = sys.argv[2] if len(sys.argv) > 2 else '/cell_cam'
    rclpy.init()
    n = Grab(out, topic)
    try:
        rclpy.spin(n)
    except SystemExit:
        pass


if __name__ == '__main__':
    main()
