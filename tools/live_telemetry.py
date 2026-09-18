#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
LIVE real-to-sim bridge: both robots' telemetry -> Gazebo (cell.launch.py telemetry:=true).

    tools/live_telemetry.py                       # M1 Pro from 192.168.10.40:30004, Pro 600 from UDP 5005
    tools/live_telemetry.py --no-pro600           # one robot only
    tools/live_telemetry.py --m1-ip 127.0.0.1 --m1-port 30004 --udp-port 5005   # against tools/fake_robots.py

Sources (both READ-ONLY; nothing here can command a robot):
  M1 Pro   TCP feedback port 30004 (Alonso's m1_feedback.py offsets): 1440-byte frames, QActual as 6 doubles at
           byte 432 (J1 J2 deg, J3 mm, J4 deg), ToolVectorActual at 624; a frame is valid iff J1+J2+J4 == R.
           Read in a tight loop with NO sleep - a backed-up socket makes the arm teleport between waypoints.
  Pro 600  UDP broadcast from Alonso's bridge, JSON {"device": "pro600", "angles": [6 deg], "label": "..."} on
           port 5005 (his PC at 192.168.10.5). The robot's own socket is single-client and is never touched.

Mappings are the verified ones in tools/replay_telemetry.py. Publishes at 50 Hz:
  /<robot>_position_controller/commands   Float64MultiArray   (only after the first sample of that robot)
  /telemetry/<robot>/joint_states         sensor_msgs/JointState (URDF names, rad / m)
  /telemetry/health                       std_msgs/String JSON: per robot connected, rate_hz, age_ms, frames, bad
and prints one status line per second. Parks the wafer off the towers first unless --no-park.
"""
import argparse, json, math, socket, struct, subprocess, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_telemetry import M1_JOINTS, P6_JOINTS, m1_map, p6_map      # noqa: E402
import rclpy, rclpy.executors                                            # noqa: E402
from rclpy.node import Node                                              # noqa: E402
from sensor_msgs.msg import JointState                                   # noqa: E402
from std_msgs.msg import Float64MultiArray, String                       # noqa: E402

PACKET, OFF_Q, OFF_TOOL = 1440, 432, 624

class Source:
    def __init__(self, name): self.name = name; self.lock = threading.Lock(); self.q = None; self.t = 0.0; self.frames = 0; self.bad = 0; self.connected = False; self.times = []
    def push(self, q):
        now = time.time()
        with self.lock:
            self.q, self.t = q, now; self.frames += 1; self.times.append(now); self.times = [x for x in self.times if now - x < 2.0]
    def snapshot(self):
        with self.lock:
            rate = len(self.times) / 2.0; age = (time.time() - self.t) * 1000 if self.t else None
            return dict(connected=self.connected, rate_hz=round(rate, 1), age_ms=None if age is None else round(age), frames=self.frames, bad=self.bad), self.q

def m1_thread(src, ip, port, stop):
    while not stop.is_set():
        try:
            sock = socket.create_connection((ip, port), timeout=5); sock.settimeout(3.0); src.connected = True
            print(f'[m1pro] connected to {ip}:{port} (read-only)', flush=True)
            while not stop.is_set():
                buf = b''
                while len(buf) < PACKET:
                    chunk = sock.recv(PACKET - len(buf))
                    if not chunk: raise ConnectionError('feedback port closed')
                    buf += chunk
                q = struct.unpack_from('<6d', buf, OFF_Q); r = struct.unpack_from('<6d', buf, OFF_TOOL)[3]
                if abs((q[0] + q[1] + q[3]) - r) > 0.01:
                    src.bad += 1; continue                       # torn frame or moved offsets
                src.push(m1_map(q[0], q[1], q[2], q[3]))
        except Exception as e:                                   # noqa: BLE001
            src.connected = False; print(f'[m1pro] {e}; reconnecting in 2 s', flush=True); stop.wait(2.0)

def udp_thread(src, port, stop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.settimeout(1.0); print(f'[pro600] listening on UDP {port}', flush=True)
    while not stop.is_set():
        try: data, addr = s.recvfrom(4096)
        except socket.timeout:
            src.connected = False; continue
        try:
            p = json.loads(data)
            if p.get('device', 'pro600') != 'pro600': continue
            a = [float(v) for v in p['angles']]; assert len(a) == 6
        except Exception:                                        # noqa: BLE001
            src.bad += 1; continue
        src.connected = True; src.label = p.get('label', ''); src.push(p6_map(a))

def pro600_direct_thread(src, ip, port, stop, hz=10.0):
    """FALLBACK ONLY: polls the Pro 600 itself over its single-client socket (pymycobot ElephantRobot).
    Never run this while Alonso's Bridge.py is connected - it would take the robot's only client slot."""
    import sys as _sys
    from pathlib import Path as _P
    venv = _P.home() / 'venvs' / 'wafer_shadow' / 'lib' / f'python{_sys.version_info.major}.{_sys.version_info.minor}' / 'site-packages'
    if venv.exists() and str(venv) not in _sys.path: _sys.path.insert(0, str(venv))
    from pymycobot import ElephantRobot
    while not stop.is_set():
        try:
            arm = ElephantRobot(ip, port); arm.start_client(); src.connected = True
            print(f'[pro600] DIRECT read from {ip}:{port} (fallback; his bridge must be OFF)', flush=True)
            while not stop.is_set():
                a = arm.get_angles()
                if isinstance(a, (list, tuple)) and len(a) == 6: src.push(p6_map([float(v) for v in a]))
                else: src.bad += 1
                stop.wait(1.0 / hz)
        except Exception as e:                                   # noqa: BLE001
            src.connected = False; print(f'[pro600] direct: {e}; retry in 3 s', flush=True); stop.wait(3.0)

class Bridge(Node):
    def __init__(self, a, sources):
        super().__init__('live_telemetry'); self.sources = sources
        self.cmd = {r: self.create_publisher(Float64MultiArray, f'/{r}_position_controller/commands', 10) for r in sources}
        self.tel = {r: self.create_publisher(JointState, f'/telemetry/{r}/joint_states', 10) for r in sources}
        self.health = self.create_publisher(String, '/telemetry/health', 10)
        self.names = {'m1pro': M1_JOINTS, 'pro600': P6_JOINTS}
        self.create_timer(0.02, self.tick); self.create_timer(1.0, self.status)
    def tick(self):
        for r, src in self.sources.items():
            h, q = src.snapshot()
            if q is None: continue
            self.cmd[r].publish(Float64MultiArray(data=q))
            js = JointState(); js.header.stamp = self.get_clock().now().to_msg(); js.name = self.names[r]; js.position = q; self.tel[r].publish(js)
    def status(self):
        rep = {r: src.snapshot()[0] for r, src in self.sources.items()}
        self.health.publish(String(data=json.dumps(rep)))
        parts = []
        for r, h in rep.items():
            # Alonso's Pro 600 bridge broadcasts only while it runs a job and pauses ~2 s while a move settles,
            # so an old last packet means IDLE, not a fault; the M1 stream never stops while the robot is on
            state = 'LIVE' if h['connected'] and h['age_ms'] is not None and h['age_ms'] < 2500 else ('no data' if h['frames'] == 0 else f"IDLE (last {h['age_ms']/1000:.0f} s ago)")
            parts.append(f"{r}: {state} {h['rate_hz']:5.1f} Hz age {h['age_ms'] if h['age_ms'] is not None else '-'} ms frames {h['frames']} bad {h['bad']}")
        print(' | '.join(parts), flush=True)

def park_wafer():
    req = 'name: "wafer", position: {x: 0.68, y: -0.26, z: 0.0015}, orientation: {w: 1}'
    r = subprocess.run(['gz', 'service', '-s', '/world/wafer_cell/set_pose', '--reqtype', 'gz.msgs.Pose', '--reptype', 'gz.msgs.Boolean', '--timeout', '1500', '--req', req], capture_output=True, text=True)
    print('wafer parked at the bench corner' if 'data: true' in r.stdout else 'no wafer in this world (telemetry mode spawns none): nothing to park', flush=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--m1-ip', default='192.168.10.40'); ap.add_argument('--m1-port', type=int, default=30004)
    ap.add_argument('--udp-port', type=int, default=5005); ap.add_argument('--no-m1', action='store_true'); ap.add_argument('--no-pro600', action='store_true'); ap.add_argument('--no-park', action='store_true')
    ap.add_argument('--pro600-direct', metavar='IP', help='FALLBACK: poll the Pro 600 itself at IP:5001 instead of the UDP broadcast (only when his bridge is off)')
    a, _ = ap.parse_known_args()
    sources = {}; stop = threading.Event(); threads = []
    if not a.no_m1: sources['m1pro'] = Source('m1pro'); threads.append(threading.Thread(target=m1_thread, args=(sources['m1pro'], a.m1_ip, a.m1_port, stop), daemon=True))
    if not a.no_pro600:
        sources['pro600'] = Source('pro600')
        if a.pro600_direct: threads.append(threading.Thread(target=pro600_direct_thread, args=(sources['pro600'], a.pro600_direct, 5001, stop), daemon=True))
        else: threads.append(threading.Thread(target=udp_thread, args=(sources['pro600'], a.udp_port, stop), daemon=True))
    rclpy.init(); n = Bridge(a, sources)
    if not a.no_park: park_wafer()
    for t in threads: t.start()
    ex = rclpy.executors.SingleThreadedExecutor(); ex.add_node(n)
    try: ex.spin()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException): pass
    finally:
        stop.set(); ex.shutdown(timeout_sec=1.0); n.destroy_node(); rclpy.try_shutdown()

if __name__ == '__main__':
    main()
