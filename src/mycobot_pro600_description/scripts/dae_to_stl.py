#!/usr/bin/env python3
"""
Convert the Elephant Robotics Pro 600 COLLADA meshes to binary STL.

WHY
---
The upstream .dae files were exported from Rhinoceros and store their faces as
COLLADA <polygons>. Gazebo Harmonic's Ogre2 mesh loader handles <triangles> and
<polylist> but NOT <polygons>, so it reports

    [Err] [Ogre2MeshFactory.cc:598] Cannot load mesh with zero sub-meshes
    [Err] [SceneManager.cc:426]     Failed to load geometry for visual: ...

and the whole arm renders invisible. Physics is unaffected (collision is
primitives), which is why this only shows up with a GUI — every headless test
passed with the arm tracking trajectories perfectly while being unrenderable.

The .dae also declares <unit meter="0.001">. A correct COLLADA loader applies
that; STL carries no units, so the scale is baked in here and the URDF then
references the STL with scale 1.

Run:  ros2 run mycobot_pro600_description dae_to_stl.py
"""
import struct, sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'c': 'http://www.collada.org/2005/11/COLLADASchema'}


def floats(root, url):
    """Resolve a #source url to its float_array, following <vertices> if needed."""
    ident = url.lstrip('#')
    for v in root.iter(f'{{{NS["c"]}}}vertices'):
        if v.get('id') == ident:
            for inp in v.findall('c:input', NS):
                if inp.get('semantic') == 'POSITION':
                    return floats(root, inp.get('source'))
    for s in root.iter(f'{{{NS["c"]}}}source'):
        if s.get('id') == ident:
            arr = s.find('c:float_array', NS)
            return [float(x) for x in arr.text.split()]
    raise KeyError(ident)


def convert(path: Path) -> int:
    root = ET.parse(path).getroot()
    unit = root.find('.//c:unit', NS)
    scale = float(unit.get('meter')) if unit is not None else 1.0

    tris = []
    for mesh in root.iter(f'{{{NS["c"]}}}mesh'):
        for polys in mesh.findall('c:polygons', NS):
            inputs = polys.findall('c:input', NS)
            stride = max(int(i.get('offset', 0)) for i in inputs) + 1
            voff, vsrc = 0, None
            for i in inputs:
                if i.get('semantic') == 'VERTEX':
                    voff, vsrc = int(i.get('offset', 0)), i.get('source')
            pos = floats(root, vsrc)
            for p in polys.findall('c:p', NS):
                idx = [int(x) for x in p.text.split()]
                vids = idx[voff::stride]
                pts = [(pos[3 * v] * scale, pos[3 * v + 1] * scale,
                        pos[3 * v + 2] * scale) for v in vids]
                for k in range(1, len(pts) - 1):        # fan-triangulate
                    tris.append((pts[0], pts[k], pts[k + 1]))

    out = path.with_suffix('.stl')
    with open(out, 'wb') as f:
        f.write(f'from {path.name} via dae_to_stl.py'.encode().ljust(80, b'\0'))
        f.write(struct.pack('<I', len(tris)))
        for a, b, c in tris:
            ux, uy, uz = (b[i] - a[i] for i in range(3))
            vx, vy, vz = (c[i] - a[i] for i in range(3))
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            m = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            f.write(struct.pack('<12fH', nx / m, ny / m, nz / m,
                                *a, *b, *c, 0))
    print(f'  {path.name:12s} -> {out.name:12s} {len(tris):7d} tris  '
          f'(unit {scale} applied)')
    return len(tris)


def main():
    d = Path(__file__).resolve().parents[1] / 'meshes'
    files = sorted(d.glob('*.dae'))
    if not files:
        sys.exit(f'no .dae files in {d}')
    for f in files:
        convert(f)


if __name__ == '__main__':
    main()
