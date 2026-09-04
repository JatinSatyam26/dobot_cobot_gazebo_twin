#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Axis-aligned bounding box of EVERY visual in the cell, checked against the
bench top rectangle.

    ros2 run wafer_cell_bringup check_extents.py

WHY THIS EXISTS
---------------
An earlier check verified that every footprint CENTRE landed on the bench.
Every centre passed while the M1 Pro's base casting hung 30 mm off the rear
edge and its mounting plate 45 mm. Centres are not extents. This walks the
real STL vertices and primitive corners through the full transform chain -
world model poses from the SDF, robot link poses from FK on cell.urdf at the
home pose - and reports anything that pokes past the bench.

Links held in the AIR beyond the edge (the Pro 600's elbow, for instance) are
reported as OVERHANG rather than OFF BENCH: an arm reaching past the edge is
normal, a base resting past it is not.
"""
import math, re, struct, sys
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
from ament_index_python.packages import get_package_share_directory

BENCH = (-0.7620, 0.7620, -0.3048, 0.3048)   # x0 x1 y0 y1, top surface z = 0
RESTING_Z = 0.05                              # below this, "resting on the bench"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cell_layout import HOME, NEST_YELLOW, NEST_YELLOW_RPY, NEST_BLUE, NEST_BLUE_RPY, BELT_XYZ

SKIP = {'floor', 'floor_grid', 'workbench', 'inspection_cam', 'plan_cam'}


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r), math.sin(r), math.cos(p),
                              math.sin(p), math.cos(y), math.sin(y))
    return (np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]) @
            np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]) @
            np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]]))


def stl_pts(path):
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    a = np.frombuffer(d[84:84 + n * 50], dtype=np.uint8).reshape(n, 50)
    return np.frombuffer(a[:, 12:48].tobytes(), dtype='<f4').reshape(-1, 3).astype(float)


def box_pts(sx, sy, sz):
    return np.array([[i * sx / 2, j * sy / 2, k * sz / 2]
                     for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])


def resolve(uri):
    m = re.match(r'package://([^/]+)/(.*)', uri)
    if not m:
        return None
    p = Path(get_package_share_directory(m.group(1))) / m.group(2)
    return p if p.exists() else None


def geom_pts(g, mesh_attr):
    """Vertices of one <geometry>, in its own frame."""
    if g.find('mesh') is not None:
        m = g.find('mesh')
        uri = m.get(mesh_attr) if mesh_attr else m.findtext('uri')
        p = resolve(uri)
        if p is None:
            return None
        sc = m.get('scale') if mesh_attr else m.findtext('scale')
        sc = [float(v) for v in (sc or '1 1 1').split()]
        return stl_pts(p) * np.array(sc)
    if g.find('box') is not None:
        b = g.find('box')
        s = b.get('size') if mesh_attr else b.findtext('size')
        return box_pts(*[float(v) for v in s.split()])
    if g.find('cylinder') is not None:
        cy = g.find('cylinder')
        r = float(cy.get('radius') if mesh_attr else cy.findtext('radius'))
        ln = float(cy.get('length') if mesh_attr else cy.findtext('length'))
        return box_pts(2 * r, 2 * r, ln)
    return None


def report(name, pts):
    lo, hi = pts.min(0), pts.max(0)
    over = max(BENCH[0] - lo[0], hi[0] - BENCH[1],
               BENCH[2] - lo[1], hi[1] - BENCH[3], 0.0)
    tag = ''
    if over > 1e-4:
        kind = 'OFF BENCH' if lo[2] < RESTING_Z else 'overhang (in air)'
        tag = f'   <== {kind} by {over * 1000:.0f} mm'
    print(f'{name:26s} x {lo[0]:+.4f}..{hi[0]:+.4f}  y {lo[1]:+.4f}..{hi[1]:+.4f}'
          f'  z {lo[2]:+.4f}..{hi[2]:+.4f}{tag}')
    return over > 1e-4 and lo[2] < RESTING_Z


def main():
    share = Path(get_package_share_directory('wafer_cell_bringup'))
    sys.path.insert(0, str(share / 'scripts'))
    from cell_fk import Chain                      # noqa: E402

    bad = 0
    world = ET.parse(share / 'worlds' / 'wafer_cell.sdf').getroot().find('world')
    # The SDF is static XML and cannot import cell_layout.py, so make sure
    # nobody edited one without the other.
    sdf_pose = {m.get('name'): [float(v) for v in m.findtext('pose').split()]
                for m in world.findall('model') if m.findtext('pose')}
    expect = {'tower_yellow': (*NEST_YELLOW, *NEST_YELLOW_RPY),
              'tower_blue':   (*NEST_BLUE,   *NEST_BLUE_RPY),
              'conveyor_collision': (0.0, BELT_XYZ[1], None, 0, 0, 0)}
    for name, exp in expect.items():
        got = sdf_pose[name]
        for i, (e, g) in enumerate(zip(exp, got)):
            if e is not None and abs(e - g) > 1e-4:
                sys.exit(f'LAYOUT MISMATCH: wafer_cell.sdf {name} pose[{i}]={g} '
                         f'but cell_layout.py says {e}. Fix one of them.')
    print('=== SDF poses agree with cell_layout.py ===')
    print('=== static world models ===')
    for m in world.findall('model'):
        if m.get('name') in SKIP:
            continue
        mp = [float(v) for v in (m.findtext('pose') or '0 0 0 0 0 0').split()]
        MR, Mt = rpy(*mp[3:6]), np.array(mp[0:3])
        for link in m.findall('link'):
            lp = [float(v) for v in (link.findtext('pose') or '0 0 0 0 0 0').split()]
            LR, Lt = rpy(*lp[3:6]), np.array(lp[0:3])
            for vis in link.findall('visual'):
                vp = [float(v) for v in (vis.findtext('pose') or '0 0 0 0 0 0').split()]
                pts = geom_pts(vis.find('geometry'), None)
                if pts is None:
                    continue
                w = (pts @ rpy(*vp[3:6]).T + np.array(vp[0:3])) @ LR.T + Lt
                bad += report(f'{m.get("name")}/{vis.get("name")}', w @ MR.T + Mt)

    print('=== robot links at home ===')
    urdf = share / 'urdf' / 'cell.urdf'
    c = Chain(str(urdf))
    for link in ET.parse(urdf).getroot().findall('link'):
        nm = link.get('name')
        if nm == 'world':
            continue
        try:
            M = c.pose(nm, HOME)
        except Exception:
            continue
        allpts = []
        for vis in link.findall('visual'):
            o = vis.find('origin')
            xyz = np.array([float(v) for v in
                            (o.get('xyz', '0 0 0') if o is not None else '0 0 0').split()])
            rr = [float(v) for v in
                  (o.get('rpy', '0 0 0') if o is not None else '0 0 0').split()]
            pts = geom_pts(vis.find('geometry'), 'filename')
            if pts is not None:
                allpts.append(pts @ rpy(*rr).T + xyz)
        if allpts:
            P = np.vstack(allpts)
            bad += report(nm, P @ M[:3, :3].T + M[:3, 3])

    print(f'\nparts RESTING off the bench: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
