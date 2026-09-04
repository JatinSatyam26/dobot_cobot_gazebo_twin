#!/usr/bin/env python3
"""
Generate the combined cell description: both arms + the belt carriage as ONE
robot_description driven by ONE controller_manager.

WHY THIS EXISTS
---------------
The obvious design is three separate models, each with its own
gz_ros2_control plugin and its own controller manager. That does not work.
gz_ros2_control blocks inside Configure() waiting for robot_description, and
Gazebo loads plugins on its main thread — so a manager that never receives a
description stalls the entire simulation. Worse, with several plugin instances
in one process the per-instance <ros><namespace> is not honoured reliably:
observed behaviour was 2 of 3 plugins loading and the second subscribing to the
global /robot_description regardless of its namespace.

One description, one plugin, one manager sidesteps all of it. Every robot is
already bolted to the board and fixed to `world`, so a single URDF tree is also
the physically honest representation.

REGENERATE with:
    ros2 run wafer_cell_bringup generate_cell_urdf.py
and rebuild. Output: urdf/cell.urdf (generated — do not hand-edit).
"""
import subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
from ament_index_python.packages import get_package_share_directory

# name -> (package, xacro, prefix, xyz, rpy)   POSES ESTIMATED, see metrology spec
ROBOTS = [
    ('m1pro',  'dobot_m1pro_description',    'dobot_m1pro.urdf.xacro',    'm1pro_',
     (-0.56, 0.15, 0.008), (0, 0, 0.0)),
    ('pro600', 'mycobot_pro600_description', 'mycobot_pro600.urdf.xacro', 'pro600_',
     (0.62, 0.18, 0.008), (0, 0, 3.14159)),
    ('belt',   'wafer_cell_bringup',         'conveyor.urdf.xacro',       'belt_',
     # belt surface height comes from the conveyor MESH (36.0 mm above its
     # own origin, frame sat on the bench) -> 0.06265, not the old 0.050 guess
     (0.0, 0.13, 0.06265), (0, 0, 0)),
]

# joint -> (kind, lower, upper, initial). Initial values must sit strictly
# INSIDE the range: a joint initialised at a limit latches and ignores commands.
# HOME POSES ARE SOLVED, NOT TYPED. Both were produced by running FK over
# this very cell.urdf (scratch solver, Nelder-Mead) against a task-space
# target, then checked for limit margin and bench clearance:
#
#   M1 Pro   fork blade flat, along world -X, parked over the yellow tower
#            ready to pick: blade x -0.596..-0.406, y -0.073..-0.015,
#            z 0.125..0.153 - i.e. HOVERING 25 mm above the tower's 0.100 rim.
#            Worst limit margin 0.216 rad.
#            Found by GRID SEARCH, not an optimiser: the target is slightly
#            unreachable with an exact -X fork, so a least-squares residual
#            never falls to zero and any residual threshold rejects every
#            valid pose. The grid scores real constraints instead.
#
#            The blade is 58.2 mm WIDE, and the corridor between the belt's
#            front edge (+0.0227) and the tower's back edge (-0.0800) is only
#            102.7 mm, so no y offers more than 22 mm of side clearance - a
#            centreline-only clearance check reported 35.8 mm and was wrong.
#            Parking above the tower rim rather than beside it sidesteps it.
#   Pro 600  vacuum cup tip at (0.400, 0.020, 0.300) pointing STRAIGHT DOWN
#            (flange z-axis = 0 0 -1), residual 3.5e-21
#
# Every value sits >= 0.05 rad inside its limit on purpose: a joint whose
# initial_value lands ON a limit latches and then silently ignores every
# command for the rest of the run. That bug cost this project a whole session.
JOINTS = {
    'm1pro_z_lift':   (0.0, 0.25, 0.120),
    'm1pro_shoulder': (-1.483530, 1.483530, -0.4000),
    'm1pro_elbow':    (-2.356194, 2.356194, 2.1400),
    'm1pro_wrist':    (-6.283185, 6.283185, -0.6358),
    'pro600_joint1':  (-3.1400, 3.14159, 0.2161),
    'pro600_joint2':  (-4.7123, 1.5708, -0.4382),
    'pro600_joint3':  (-2.6179, 2.6179, 2.1570),
    'pro600_joint4':  (-4.5378, 1.3962, -0.1480),
    'pro600_joint5':  (-2.9321, 2.9321, -1.5708),
    'pro600_joint6':  (-3.0368, 3.0368, 0.0209),
    'belt_travel':    (-0.30, 0.30, -0.25),
}


def expand(pkg, xacro_file, prefix):
    path = Path(get_package_share_directory(pkg)) / 'urdf' / xacro_file
    out = subprocess.run(
        ['xacro', str(path), f'prefix:={prefix}',
         'use_gz_control:=false', 'fix_to_world:=false'],
        capture_output=True, text=True)
    if out.returncode:
        sys.exit(f'xacro failed for {path}:\n{out.stderr}')
    return ET.fromstring(out.stdout)


def main():
    cell = ET.Element('robot', {'name': 'wafer_cell'})
    ET.SubElement(cell, 'link', {'name': 'world'})

    for name, pkg, xf, prefix, xyz, rpy in ROBOTS:
        root = expand(pkg, xf, prefix)
        base = None
        for child in root:
            if child.tag in ('link', 'joint'):
                if child.tag == 'link' and child.get('name') == 'world':
                    continue          # each file brings its own; we made one
                cell.append(child)
        # the first link of each subtree that is never a child is its base
        # findall, NOT iter: iter() also returns the <joint> entries inside
        # a <ros2_control> block, which have no <child> element.
        children = {j.find('child').get('link') for j in root.findall('joint')}
        links = [l.get('name') for l in root.findall('link') if l.get('name') != 'world']
        roots = [l for l in links if l not in children]
        if len(roots) != 1:
            sys.exit(f'{name}: expected exactly one root link, got {roots}')
        base = roots[0]
        j = ET.SubElement(cell, 'joint',
                          {'name': f'{name}_mount', 'type': 'fixed'})
        ET.SubElement(j, 'parent', {'link': 'world'})
        ET.SubElement(j, 'child', {'link': base})
        ET.SubElement(j, 'origin', {'xyz': ' '.join(map(str, xyz)),
                                    'rpy': ' '.join(map(str, rpy))})
        print(f'  {name}: base link "{base}" mounted at {xyz} rpy {rpy}')

    # Every link needs an <inertial>. sdformat drops massless links during
    # URDF->SDF conversion, which tears holes in the frame graph:
    #   "FrameAttachedToGraph unable to find unique frame [belt_base]"
    #   "PoseRelativeToGraph unable to find path to source vertex"
    # and the whole model silently fails to spawn. Pure frame links (tcp,
    # flange, belt_base) are the usual victims.
    patched = []
    for link in cell.findall('link'):
        if link.get('name') == 'world' or link.find('inertial') is not None:
            continue
        inertial = ET.SubElement(link, 'inertial')
        ET.SubElement(inertial, 'origin', {'xyz': '0 0 0', 'rpy': '0 0 0'})
        ET.SubElement(inertial, 'mass', {'value': '1e-3'})
        ET.SubElement(inertial, 'inertia',
                      {'ixx': '1e-6', 'ixy': '0', 'ixz': '0',
                       'iyy': '1e-6', 'iyz': '0', 'izz': '1e-6'})
        patched.append(link.get('name'))
    if patched:
        print('  added placeholder inertia to massless links: ' + ', '.join(patched))

    rc = ET.SubElement(cell, 'ros2_control',
                       {'name': 'wafer_cell_system', 'type': 'system'})
    ET.SubElement(ET.SubElement(rc, 'hardware'), 'plugin').text = \
        'gz_ros2_control/GazeboSimSystem'
    for jn, (lo, hi, init) in JOINTS.items():
        je = ET.SubElement(rc, 'joint', {'name': jn})
        ci = ET.SubElement(je, 'command_interface', {'name': 'position'})
        ET.SubElement(ci, 'param', {'name': 'min'}).text = str(lo)
        ET.SubElement(ci, 'param', {'name': 'max'}).text = str(hi)
        si = ET.SubElement(je, 'state_interface', {'name': 'position'})
        ET.SubElement(si, 'param', {'name': 'initial_value'}).text = str(init)
        ET.SubElement(je, 'state_interface', {'name': 'velocity'})
        ET.SubElement(je, 'state_interface', {'name': 'effort'})

    gz = ET.SubElement(cell, 'gazebo')
    pl = ET.SubElement(gz, 'plugin',
                       {'filename': 'gz_ros2_control-system',
                        'name': 'gz_ros2_control::GazeboSimROS2ControlPlugin'})
    ET.SubElement(pl, 'parameters').text = str(
        Path(get_package_share_directory('wafer_cell_bringup')) /
        'config' / 'cell_controllers.yaml')

    ET.indent(cell, space='  ')
    src = Path(__file__).resolve().parents[1] / 'urdf' / 'cell.urdf'
    hdr = ('<?xml version="1.0"?>\n<!-- GENERATED by '
           'scripts/generate_cell_urdf.py - do not hand-edit.\n'
           '     Regenerate after changing any robot xacro or a cell pose. -->\n')
    src.write_text(hdr + ET.tostring(cell, encoding='unicode') + '\n')
    print(f'wrote {src}')


if __name__ == '__main__':
    main()
