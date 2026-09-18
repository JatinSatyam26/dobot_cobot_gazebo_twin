#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Desk stand-ins for the two robots' telemetry, replaying the 2026-09-11 recordings in their WIRE formats,
so tools/live_telemetry.py can be tested with no bench:
  - a TCP server on --m1-port (default 30004) streaming 1440-byte M1 Pro feedback frames at 125 Hz
    (QActual at byte 432, ToolVectorActual at 624 with R = J1+J2+J4 so the integrity check passes)
  - UDP JSON packets {"device":"pro600","angles":[...],"label":...} to --udp-host:--udp-port at the recorded pace

    tools/fake_robots.py --m1 <m1 log> --pro600 <udp log> [--loop] [--udp-host 127.0.0.1]
"""
import argparse, json, re, socket, struct, threading, time

def parse_m1(path):
    out = []
    for l in open(path):
        m = re.search(r'([\d.]+)s\s+J1\s+([-\d.]+)\s+J2\s+([-\d.]+)\s+J3\s+([-\d.]+)mm\s+J4\s+([-\d.]+)', l)
        if m: out.append((float(m.group(1)), [float(v) for v in m.groups()[1:]]))
    return out
def parse_p6(path):
    out = []; t = 0.0
    for l in open(path):
        m = re.match(r'\s*pro600\s+' + r'([-\d.]+)\s+' * 6 + r'(.*?)(?:\s+\(\+\s*(\d+) ms\))?\s*$', l)
        if not m: continue
        t += int(m.group(8) or 0) / 1000.0; out.append((t, [float(v) for v in m.groups()[:6]], m.group(7).strip()))
    return out
def interp(samples, t):
    if t <= samples[0][0]: return samples[0][1]
    if t >= samples[-1][0]: return samples[-1][1]
    for (t0, a), (t1, b) in zip(samples, samples[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0; return [x + f * (y - x) for x, y in zip(a, b)]
def frame(j):
    buf = bytearray(1440); struct.pack_into('<H', buf, 0, 1440)
    struct.pack_into('<6d', buf, 432, j[0], j[1], j[2], j[3], 0.0, 0.0)
    struct.pack_into('<6d', buf, 624, 314.0, 41.0, j[2], j[0] + j[1] + j[3], 0.0, 0.0)
    return bytes(buf)
def m1_server(samples, port, loop):
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(('0.0.0.0', port)); srv.listen(1)
    print(f'[fake m1] serving 1440-byte frames on {port}', flush=True)
    while True:
        c, addr = srv.accept(); print(f'[fake m1] client {addr[0]}', flush=True); t0 = time.time()
        try:
            while True:
                t = time.time() - t0
                if t > samples[-1][0] + 1:
                    if not loop: t = samples[-1][0]
                    else: t0 = time.time(); continue
                c.sendall(frame(interp(samples, t))); time.sleep(0.008)
        except (BrokenPipeError, ConnectionResetError): print('[fake m1] client left', flush=True)
def udp_sender(samples, host, port, loop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print(f'[fake pro600] sending JSON to {host}:{port}', flush=True)
    while True:
        t0 = time.time()
        for (t, a, label) in samples:
            while time.time() - t0 < t: time.sleep(0.005)
            s.sendto(json.dumps({'device': 'pro600', 'angles': a, 'label': label}).encode(), (host, port))
        if not loop:
            while True: s.sendto(json.dumps({'device': 'pro600', 'angles': samples[-1][1], 'label': 'home (settled)'}).encode(), (host, port)); time.sleep(0.05)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--m1'); ap.add_argument('--pro600'); ap.add_argument('--m1-port', type=int, default=30004)
    ap.add_argument('--udp-host', default='127.0.0.1'); ap.add_argument('--udp-port', type=int, default=5005); ap.add_argument('--loop', action='store_true')
    a = ap.parse_args(); th = []
    if a.m1: th.append(threading.Thread(target=m1_server, args=(parse_m1(a.m1), a.m1_port, a.loop), daemon=True))
    if a.pro600: th.append(threading.Thread(target=udp_sender, args=(parse_p6(a.pro600), a.udp_host, a.udp_port, a.loop), daemon=True))
    for t in th: t.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: pass
if __name__ == '__main__':
    main()
