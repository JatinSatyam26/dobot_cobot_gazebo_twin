#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""Compose six record_frames.py recordings into one video: 3x2 grid, step name overlay, sim-time rate.

usage: make_cycle_video.py <recdir> <out.mp4> [fps]
<recdir> holds one sub-directory per camera (cell_cam, plan_cam, detail_yellow_cam,
detail_belt_cam, detail_beltc_cam, detail_blue_cam) written by record_frames.py at
interval 1/fps; the video runs from 1 s before the first step to 2 s after CYCLE_DONE."""
import sys, glob, os, subprocess, bisect
from PIL import Image, ImageDraw, ImageFont
rec, out = sys.argv[1], sys.argv[2]; fps = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
cams = [('cell_cam', 'front'), ('plan_cam', 'plan'), ('detail_yellow_cam', 'yellow nest (pick)'),
        ('detail_belt_cam', 'belt holder, from behind the belt'), ('detail_beltc_cam', 'unloading end'), ('detail_blue_cam', 'blue nest (place)')]
def frames(cam):
    fs = sorted(glob.glob(os.path.join(rec, cam, 'f*.jpg')))
    ts = [float(os.path.basename(f).split('_t')[1][:-4]) for f in fs]
    return ts, fs
data = {c: frames(c) for c, _ in cams}
states = []
for c, _ in cams:
    p = os.path.join(rec, c, 'states.txt')
    if os.path.exists(p):
        states = [(float(l.split()[0]), l.split()[1]) for l in open(p) if l.strip()]; break
t_start = min(ts[0] for ts, _ in data.values()); t_end = max(ts[-1] for ts, _ in data.values())
# trim to the cycle: from 1 s before the first step to 2 s after CYCLE_DONE
if states:
    t0 = max(t_start, states[0][0] - 1.0)
    done = [t for t, n in states if n == 'CYCLE_DONE']
    t1 = min(t_end, (done[0] + 2.0) if done else t_end)
else:
    t0, t1 = t_start, t_end
W, H = 640, 400; cols = 3
tmp = os.path.join(rec, 'composite'); os.makedirs(tmp, exist_ok=True)
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
except Exception: font = ImageFont.load_default()
def nearest(ts, fs, t):
    i = bisect.bisect_left(ts, t); i = min(max(i, 0), len(fs) - 1)
    if i > 0 and abs(ts[i-1] - t) < abs(ts[i] - t): i -= 1
    return fs[i]
n = 0; t = t0
while t <= t1:
    sheet = Image.new('RGB', (W * cols, H * 2 + 36), 'black'); d = ImageDraw.Draw(sheet)
    for k, (c, label) in enumerate(cams):
        ts, fs = data[c]
        im = Image.open(nearest(ts, fs, t)).convert('RGB').resize((W, H))
        x, y = (k % cols) * W, (k // cols) * H + 36; sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 330, y + 22], fill='black'); d.text((x + 4, y + 2), label, fill='yellow')
    step = [nm for tt, nm in states if tt <= t]; step = step[-1] if step else ''
    d.text((8, 6), f"t = {t - t0:5.1f} s    {step}", fill='white', font=font)
    sheet.save(os.path.join(tmp, f'c{n:05d}.jpg'), quality=90); n += 1; t += 1.0 / fps
print(f"{n} composite frames, {t1 - t0:.1f} s of sim time")
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-i', os.path.join(tmp, 'c%05d.jpg'),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out], check=True)
print("wrote", out, os.path.getsize(out) // 1024, "kB")
