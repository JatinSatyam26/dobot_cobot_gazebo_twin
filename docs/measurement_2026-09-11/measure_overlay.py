#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Draw the catalogue's dimension lines onto the Gazebo camera renders, by projecting
their world endpoints through the camera model in wafer_cell.sdf (pinhole: the
sensor's +X is the optical axis, image right = -Y, image down = -Z,
f = (W/2)/tan(hfov/2)).  The projection is self-checked by drawing the bench
outline: if it does not sit on the bench's edges in the render, do not trust it.

    python3 measure_overlay.py <renders_dir>       (plan_cam.png, plan_cam_C.png, cell_cam.png)
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent; FIG = HERE / 'figures'
D = json.load(open(HERE / 'dims.json'))
CAMS = {'plan_cam': ((0, -0.30, 1.90, 0, 1.44, 1.5708), 0.95, (1280, 800)),
        'cell_cam': ((-0.150, -1.750, 0.620, 0, 0.28800, 1.48538), 1.05, (1280, 800))}
RED = (200, 0, 0)
try: FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
except Exception: FONT = ImageFont.load_default()

def rot(r, p, y):
    Rx = np.array([[1,0,0],[0,math.cos(r),-math.sin(r)],[0,math.sin(r),math.cos(r)]]); Ry = np.array([[math.cos(p),0,math.sin(p)],[0,1,0],[-math.sin(p),0,math.cos(p)]]); Rz = np.array([[math.cos(y),-math.sin(y),0],[math.sin(y),math.cos(y),0],[0,0,1]])
    return Rz @ Ry @ Rx
class Cam:
    def __init__(self, name):
        pose, hfov, (W, H) = CAMS[name]; self.t = np.array(pose[:3]); self.R = rot(*pose[3:]); self.W, self.H = W, H
        self.f = (W / 2) / math.tan(hfov / 2)
    def uv(self, p):
        c = self.R.T @ (np.array(p, dtype=float) - self.t)
        if c[0] <= 0.05: return None
        return (self.W / 2 - self.f * c[1] / c[0], self.H / 2 - self.f * c[2] / c[0])

def arrow(dr, a, b, w=3):
    dr.line([a, b], fill=RED, width=w)
    for tip, other in ((a, b), (b, a)):
        ang = math.atan2(other[1] - tip[1], other[0] - tip[0])
        for s in (+0.45, -0.45):
            dr.line([tip, (tip[0] + 14 * math.cos(ang + s), tip[1] + 14 * math.sin(ang + s))], fill=RED, width=w)
def label(dr, xy, text, anchor='mm'):
    x, y = xy; bb = dr.textbbox((x, y), text, font=FONT, anchor=anchor)
    dr.rectangle((bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2), fill=(255, 255, 255)); dr.text((x, y), text, font=FONT, fill=RED, anchor=anchor)

# which render each dimension is drawn on, and at what height / depth its endpoints sit
Z_PLAN = {'conveyor': 0.0626, 'carrier': 0.0656, 'towers': 0.10, 'm1': 0.068, 'p6': 0.008, 'bench': 0.0}
Y_FRONT = {'D13': 0.0839, 'D23': 0.126, 'D24': 0.126, 'D36': -0.2975, 'D58': 0.05, 'D60': -0.05, 'D62': 0.13, 'D63': 0.069}
def render_plan(src, out, groups, title):
    cam = Cam('plan_cam'); im = Image.open(src).convert('RGB'); dr = ImageDraw.Draw(im)
    corners = [(-0.762, -0.3048, 0), (0.762, -0.3048, 0), (0.762, 0.3048, 0), (-0.762, 0.3048, 0)]
    pts = [cam.uv(c) for c in corners]; dr.line(pts + [pts[0]], fill=(0, 120, 255), width=2)
    for d in D:
        if d['fig'] not in groups or d['kind'] not in ('x', 'y', 'd'): continue
        z = Z_PLAN.get(d['fig'], 0.0); at = d['at']; k = d['kind']
        if k == 'x': a, b = (d['p1'], at, z), (d['p2'], at, z)
        elif k == 'y': a, b = (at, d['p1'], z), (at, d['p2'], z)
        else: a, b = (*d['p1'], z), (*d['p2'], z)
        A, B = cam.uv(a), cam.uv(b)
        if A is None or B is None: continue
        f = 0.5 + (0.17 if int(d['id'][1:]) % 2 else -0.17)          # stagger neighbouring labels
        arrow(dr, A, B); label(dr, (A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1])), f"{d['id']} {d['value_cm']:.1f}")
    label(dr, (im.width / 2, 22), title + '  (blue = the bench top as the model projects it)')
    im.save(out)
def render_front(src, out):
    cam = Cam('cell_cam'); im = Image.open(src).convert('RGB'); dr = ImageDraw.Draw(im)
    corners = [(-0.762, -0.3048, 0), (0.762, -0.3048, 0), (0.762, 0.3048, 0), (-0.762, 0.3048, 0)]
    pts = [cam.uv(c) for c in corners]; dr.line(pts + [pts[0]], fill=(0, 120, 255), width=2)
    for d in D:
        if d['fig'] != 'elev' or d['kind'] != 'z' or d['id'] not in Y_FRONT: continue
        x = d['at']; yv = Y_FRONT[d['id']]
        A, B = cam.uv((x, yv, d['p1'])), cam.uv((x, yv, d['p2']))
        if A is None or B is None: continue
        arrow(dr, A, B); txt = f"{d['id']} {d['value_cm']:.1f}"
        if abs(B[1] - A[1]) < 70:                                   # short line: label above (odd id) or below (even id)
            top, bot = min(A[1], B[1]), max(A[1], B[1])
            label(dr, (A[0], top - 14), txt) if int(d['id'][1:]) % 2 else label(dr, (A[0], bot + 14), txt)
        else:
            f = 0.5 + (0.2 if int(d['id'][1:]) % 2 else -0.2)
            label(dr, (A[0] + 50, A[1] + f * (B[1] - A[1])), txt)
    label(dr, (im.width / 2, 22), 'Heights, front camera  (blue outline = the bench top as the model projects it)')
    im.save(out)

if __name__ == '__main__':
    src = Path(sys.argv[1])
    render_plan(src / 'plan_cam.png', FIG / 'render_conveyor.png', ('conveyor',), 'Conveyor D5-D12')
    render_plan(src / 'plan_cam.png', FIG / 'render_towers.png', ('towers',), 'Towers D25-D34')
    render_plan(src / 'plan_cam.png', FIG / 'render_m1.png', ('m1',), 'M1 Pro base D40-D48')
    render_plan(src / 'plan_cam.png', FIG / 'render_p6.png', ('p6',), 'Pro 600 base D50-D56')
    render_plan(src / 'plan_cam_C.png', FIG / 'render_carrier.png', ('carrier',), 'Carrier D14-D22 (holder shown at the unload station)')
    render_plan(src / 'plan_cam.png', FIG / 'render_bench.png', ('bench',), 'Bench D1-D4')
    render_front(src / 'cell_cam.png', FIG / 'render_heights.png')
    print('overlays written')
