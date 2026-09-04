#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""Cut a collision STL into horizontal bands so a mesh collider can cull by height.

usage: split_collision_mesh.py <in.stl> <out.stl> <band_mm> [height_axis 0|1|2]

Tall, thin wall triangles have bounding boxes spanning the part's full height,
so every query near the part tests all of them. Clipping each triangle to
horizontal slabs keeps the surface identical (no chord change) and lets the
collider's AABB tree skip the bands a query does not reach.
"""
import struct, sys
import numpy as np


def read_stl(path):
    with open(path, 'rb') as f:
        f.read(80); n = struct.unpack('<I', f.read(4))[0]
        d = np.frombuffer(f.read(), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n)
    return d['v'].astype(np.float64)


def write_stl(path, tris):
    tris = np.asarray(tris, dtype=np.float64)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1); ok = ln > 1e-12
    nrm[ok] /= ln[ok][:, None]
    rec = np.zeros(len(tris), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    rec['n'] = nrm; rec['v'] = tris
    with open(path, 'wb') as f:
        f.write(b'band-split collision mesh'.ljust(80, b'\0')); f.write(struct.pack('<I', len(tris))); f.write(rec.tobytes())


def clip_polygon(poly, axis, lo, hi):
    """Sutherland-Hodgman clip of a convex polygon to lo <= p[axis] <= hi."""
    def clip(poly, keep, edge):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            ka, kb = keep(a), keep(b)
            if ka: out.append(a)
            if ka != kb:
                t = (edge - a[axis]) / (b[axis] - a[axis]); out.append(a + t * (b - a))
        return out
    poly = clip(poly, lambda p: p[axis] >= lo - 1e-9, lo)
    if len(poly) < 3: return []
    poly = clip(poly, lambda p: p[axis] <= hi + 1e-9, hi)
    return poly if len(poly) >= 3 else []


def split(tris, band, axis):
    out = []
    for t in tris:
        y0, y1 = t[:, axis].min(), t[:, axis].max()
        if y1 - y0 <= band + 1e-9:
            out.append(t); continue
        k0, k1 = int(np.floor(y0 / band)), int(np.ceil(y1 / band))
        for k in range(k0, k1):
            poly = clip_polygon([t[0], t[1], t[2]], axis, k * band, (k + 1) * band)
            for i in range(1, len(poly) - 1):
                tri = np.array([poly[0], poly[i], poly[i + 1]])
                if np.linalg.norm(np.cross(tri[1] - tri[0], tri[2] - tri[0])) > 1e-9: out.append(tri)
    return out


if __name__ == '__main__':
    src, dst, band = sys.argv[1], sys.argv[2], float(sys.argv[3])
    axis = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    tris = read_stl(src); out = split(tris, band, axis)
    write_stl(dst, out)
    ext = np.ptp(tris.reshape(-1, 3), axis=0)
    print(f"{src}: {len(tris)} triangles -> {dst}: {len(out)} triangles, bands of {band:g} along axis {axis} (extent {np.round(ext, 1)})")
