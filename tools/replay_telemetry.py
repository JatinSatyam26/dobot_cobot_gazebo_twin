#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Replay recorded robot telemetry into Gazebo (telemetry mode of cell.launch.py).

    tools/replay_telemetry.py --m1 <m1_feedback.md> --pro600 <udp_log.md> [--rate 1.0] [--loop] [--no-park]

Input formats are the two first-test logs of 2026-09-11:
  M1 Pro (port 30004 reader):   "   7.70s  J1  -30.004  J2   75.101  J3  156.766mm  J4   62.443"
  Pro 600 (Alonso's UDP 5005):  "pro600  -81.287 -102.418  130.242 -118.125  -89.824   -2.285  over wafer  (+   53 ms)"

Joint mapping, verified on the M1 recording against the taught waypoints (0.1 deg):
  shoulder = J1,  elbow = -J2 + 1.961 deg (the URDF elbow zero),  wrist = J4 - 17.54 deg,
  z_lift = J3 + 24.4 mm  (tower reference; the carrier reads 30.3 - the model's 6 mm carrier-height error).
The Pro 600 mapping is PRO600_MAP below: per joint (sign, offset_deg) into the URDF chain.

Publishes Float64MultiArray on /<robot>_position_controller/commands at 50 Hz (linearly
interpolated between samples) and the telemetry contract sensor_msgs/JointState on
/telemetry/<robot>/joint_states with the URDF joint names. Parks the wafer off the
towers first (no grasp is simulated; the fork would otherwise hit it) unless --no-park.
At the end prints the tracking error per joint from /joint_states.
"""
import argparse, math, re, subprocess, threading, time
import rclpy
import rclpy.executors
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

M1_JOINTS = ['m1pro_z_lift', 'm1pro_shoulder', 'm1pro_elbow', 'm1pro_wrist']
P6_JOINTS = [f'pro600_joint{i}' for i in range(1, 7)]
ELBOW_ZERO_DEG, WRIST_OFFSET_DEG, Z_OFFSET_MM = 1.961, 17.54, 24.4
# Pro 600 (sign, offset_deg) per joint into the URDF chain: fitted 2026-09-11 on his four confirmed
# taught pose pairs (cup tip within 7 mm, cup straight down at every pose, base frames coincident
# to 0.2 deg / 2 cm). Joint 6's offset is unknown (a round cup cannot show it).
PRO600_MAP = [(1, 0.0), (1, 90.0), (1, 0.0), (1, 90.0), (1, 0.0), (1, 0.0)]

def m1_map(j1, j2, j3mm, j4):
    return [(j3mm + Z_OFFSET_MM) / 1000.0, math.radians(j1), math.radians(-j2 + ELBOW_ZERO_DEG), math.radians(j4 - WRIST_OFFSET_DEG)]
def p6_map(a):
    return [math.radians(s * v + o) for (s, o), v in zip(PRO600_MAP, a)]

def parse_m1(path):
    out = []
    for l in open(path):
        m = re.search(r'([\d.]+)s\s+J1\s+([-\d.]+)\s+J2\s+([-\d.]+)\s+J3\s+([-\d.]+)mm\s+J4\s+([-\d.]+)', l)
        if m: out.append((float(m.group(1)), m1_map(*[float(v) for v in m.groups()[1:]])))
    return out
def parse_p6(path):
    out = []; t = 0.0
    for l in open(path):
        m = re.match(r'\s*pro600\s+' + r'([-\d.]+)\s+' * 6 + r'(.*?)(?:\s+\(\+\s*(\d+) ms\))?\s*$', l)
        if not m: continue
        t += int(m.group(8) or 0) / 1000.0
        out.append((t, p6_map([float(v) for v in m.groups()[:6]])))
    return out

def interp(samples, t):
    if t <= samples[0][0]: return samples[0][1]
    if t >= samples[-1][0]: return samples[-1][1]
    lo, hi = 0, len(samples) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if samples[mid][0] <= t: lo = mid
        else: hi = mid
    t0, a = samples[lo]; t1, b = samples[hi]; f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return [x + f * (y - x) for x, y in zip(a, b)]

class Replay(Node):
    def __init__(self, a):
        super().__init__('replay_telemetry'); self.a = a
        self.streams = {}
        if a.m1: self.streams['m1pro'] = (M1_JOINTS, parse_m1(a.m1))
        if a.pro600: self.streams['pro600'] = (P6_JOINTS, parse_p6(a.pro600))
        self.cmd = {r: self.create_publisher(Float64MultiArray, f'/{r}_position_controller/commands', 10) for r in self.streams}
        self.tel = {r: self.create_publisher(JointState, f'/telemetry/{r}/joint_states', 10) for r in self.streams}
        self.last_cmd = {}; self.err = {}
        self.create_subscription(JointState, '/joint_states', self.on_js, 10)
        for r, (names, s) in self.streams.items():
            self.get_logger().info(f'{r}: {len(s)} samples, {s[-1][0]:.1f} s')

    def on_js(self, m):
        pos = dict(zip(m.name, m.position))
        for r, (names, _) in self.streams.items():
            if r not in self.last_cmd: continue
            for n, c in zip(names, self.last_cmd[r]):
                if n in pos:
                    e = abs(pos[n] - c); self.err[n] = max(self.err.get(n, 0.0), e)

    def park_wafer(self):
        req = 'name: "wafer", position: {x: 0.68, y: -0.26, z: 0.0015}, orientation: {w: 1}'
        r = subprocess.run(['gz', 'service', '-s', '/world/wafer_cell/set_pose', '--reqtype', 'gz.msgs.Pose', '--reptype', 'gz.msgs.Boolean',
                            '--timeout', '1500', '--req', req], capture_output=True, text=True)
        self.get_logger().info(f'wafer parked at the bench corner: {"data: true" in r.stdout}')

    def run(self):
        if not self.a.no_park: self.park_wafer()
        dur = max(s[-1][0] for _, s in self.streams.values())
        while rclpy.ok():
            t0 = time.time(); self.err = {}
            while rclpy.ok():
                t = (time.time() - t0) * self.a.rate
                if t > dur + 0.5: break
                for r, (names, s) in self.streams.items():
                    q = interp(s, t); self.last_cmd[r] = q
                    self.cmd[r].publish(Float64MultiArray(data=q))
                    js = JointState(); js.header.stamp = self.get_clock().now().to_msg(); js.name = names; js.position = q
                    self.tel[r].publish(js)
                time.sleep(0.02)
            for r, (names, _) in self.streams.items():
                worst = max((self.err.get(n, 0.0) for n in names), default=0.0)
                msg = (f'{r}: replay done, worst tracking error {math.degrees(worst):.2f} deg-equivalent ' +
                       ' '.join(f'{n.split("_", 1)[1]}={self.err.get(n, 0.0):.4f}' for n in names))
                self.get_logger().info(msg); print(msg, flush=True)
            if not self.a.loop: break

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--m1'); ap.add_argument('--pro600'); ap.add_argument('--rate', type=float, default=1.0)
    ap.add_argument('--loop', action='store_true'); ap.add_argument('--no-park', action='store_true')
    a, _ = ap.parse_known_args()
    rclpy.init(); n = Replay(a)
    ex = rclpy.executors.SingleThreadedExecutor(); ex.add_node(n)
    th = threading.Thread(target=ex.spin, daemon=True); th.start(); time.sleep(0.5)
    try: n.run()
    except KeyboardInterrupt: pass
    finally:
        # shut the executor down BEFORE the interpreter exits, or rclpy aborts ("terminate called
        # without an active exception") and a piped stdout loses everything that was logged
        ex.shutdown(timeout_sec=1.0); th.join(timeout=2.0); n.destroy_node(); rclpy.try_shutdown()

if __name__ == '__main__':
    main()
