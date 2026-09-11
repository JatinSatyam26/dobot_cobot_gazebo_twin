#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Streamed pose check of one sequencer cycle.

  stream:  python3 tools/cycle_check.py stream out.csv          (runs until SIGINT; logs wafer + belt_carriage)
  report:  python3 tools/cycle_check.py report out.csv seq_log.txt

The report prints, per sequencer step, the wafer pose at the END of the step, the
peak tilt during it and the carriage x, plus the wafer-to-carriage offset during
the two belt moves. A streamed log is the only way to see a 20 deg tilt that a
2 s sample misses (CLAUDE.md, pick trap).
"""
import math, re, subprocess, sys, time

def stream(out_path):
    out = open(out_path, 'w')
    p = subprocess.Popen(['gz', 'topic', '-e', '-t', '/world/wafer_cell/dynamic_pose/info'], stdout=subprocess.PIPE, text=True)
    name = None; blk = None; pos = {}; ori = {}; sec = 0; nsec = 0
    try:
        for line in p.stdout:
            s = line.strip()
            if s.startswith('sec:'): sec = int(s.split()[1])
            elif s.startswith('nsec:'): nsec = int(s.split()[1])
            elif s.startswith('name:'): name = s.split('"')[1]; pos = {}; ori = {}
            elif s == 'position {': blk = pos
            elif s == 'orientation {': blk = ori
            elif blk is not None and s[:2] in ('x:', 'y:', 'z:', 'w:'):
                blk[s[0]] = float(s.split()[1])
                if blk is ori and 'w' in ori and name in ('wafer', 'belt_carriage'):
                    x, y, z, w = ori.get('x', 0), ori.get('y', 0), ori.get('z', 0), ori['w']
                    tilt = math.degrees(math.acos(max(-1, min(1, 1 - 2 * (x * x + y * y)))))
                    out.write(f"{time.time():.3f},{sec + nsec * 1e-9:.3f},{name},{pos.get('x', 0):.4f},{pos.get('y', 0):.4f},{pos.get('z', 0):.4f},{tilt:.2f}\n")
                    out.flush(); blk = None
    finally:
        p.kill()

def report(csv_path, log_path):
    rows = [l.strip().split(',') for l in open(csv_path)]
    W = [(float(r[0]), float(r[3]), float(r[4]), float(r[5]), float(r[6])) for r in rows if r[2] == 'wafer']
    C = [(float(r[0]), float(r[3]), float(r[4]), float(r[5])) for r in rows if r[2] == 'belt_carriage']
    steps = []
    for l in open(log_path):
        m = re.search(r'\[(\d+\.\d+)\].*>> ([A-Z_0-9]+)', l)
        if m: steps.append((float(m.group(1)), m.group(2)))
    if not W or not steps: print('no data'); return 1
    steps.append((W[-1][0] + 1, 'END'))
    def at(seq, t):
        best = None
        for r in seq:
            if r[0] <= t: best = r
            else: break
        return best
    print(f"{'step':22s} {'wafer x':>8s} {'y':>8s} {'z':>8s} {'tilt':>6s} {'peak':>6s}  {'carr x':>7s}")
    for (t0, n), (t1, _) in zip(steps, steps[1:]):
        w = at(W, t1 - 0.05); c = at(C, t1 - 0.05); peak = max([r[4] for r in W if t0 <= r[0] < t1] or [0])
        if w: print(f"{n:22s} {w[1]:8.4f} {w[2]:8.4f} {w[3]:8.4f} {w[4]:6.2f} {peak:6.2f}  {c[1] if c else 0:7.4f}")
    for name in ('BELT_A_TO_B', 'BELT_B_TO_C'):
        for (t0, n), (t1, _) in zip(steps, steps[1:]):
            if n == name:
                tm = (t0 + t1) / 2; w = at(W, tm); c = at(C, tm)
                print(f"ride {name}: wafer-carriage dx {(w[1]-c[1])*1e3:+.1f} dy {(w[2]-c[2])*1e3:+.1f} dz {(w[3]-c[3])*1e3:+.1f} mm, tilt {w[4]:.2f} deg")
    return 0

if __name__ == '__main__':
    if sys.argv[1] == 'stream': stream(sys.argv[2])
    else: sys.exit(report(sys.argv[2], sys.argv[3]))
