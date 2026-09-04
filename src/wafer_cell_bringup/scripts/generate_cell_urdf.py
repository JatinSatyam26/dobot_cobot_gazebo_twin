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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ament_index_python.packages import get_package_share_directory

# Every pose and the home pose come from ONE place. Edit cell_layout.py,
# never the numbers here. The layout is INTERIM (photo-derived, +/-20 mm) -
# read the provenance block at the top of cell_layout.py.
from cell_layout import ROBOTS, JOINT_LIMITS, HOME, GRASP_LINKS, WAFER_MODEL

# joint -> (lower, upper, initial). Initial values sit strictly INSIDE the
# range: a joint initialised at a limit latches and ignores every command.
JOINTS = {name: (lo, hi, HOME[name]) for name, (lo, hi) in JOINT_LIMITS.items()}
for _n, (_lo, _hi, _q) in JOINTS.items():
    assert _lo + 0.02 <= _q <= _hi - 0.02, f'{_n}: home {_q} too close to limit [{_lo}, {_hi}]'


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

    # Grasp = a fixed joint created/destroyed on demand (gz DetachableJoint).
    # Starts DETACHED and keeps looking for the wafer model until it spawns
    # (verified in gz-sim8 source). Attach accepts any message, detach wants
    # gz.msgs.Empty; cell.launch.py bridges std_msgs/Empty to both. One per
    # carrier: the fork (M1 Pro), the cup (Pro 600) and the belt nest, so the
    # wafer rides the belt by a joint, not by friction (contact physics is the
    # one layer this model does not try to reproduce - PROJECT_CONTEXT 9).
    for carrier, link in GRASP_LINKS.items():
        dj = ET.SubElement(gz, 'plugin',
                           {'filename': 'gz-sim-detachable-joint-system',
                            'name': 'gz::sim::systems::DetachableJoint'})
        ET.SubElement(dj, 'parent_link').text = link
        ET.SubElement(dj, 'child_model').text = WAFER_MODEL
        ET.SubElement(dj, 'child_link').text = 'link'
        ET.SubElement(dj, 'attach_topic').text = f'/wafer/{carrier}/attach'
        ET.SubElement(dj, 'detach_topic').text = f'/wafer/{carrier}/detach'
        ET.SubElement(dj, 'output_topic').text = f'/wafer/{carrier}/state'
        # keep the warning: it is the only sign the plugin cannot find the wafer
        ET.SubElement(dj, 'suppress_child_warning').text = 'false'

    ET.indent(cell, space='  ')
    src = Path(__file__).resolve().parents[1] / 'urdf' / 'cell.urdf'
    hdr = ('<?xml version="1.0"?>\n<!-- GENERATED by '
           'scripts/generate_cell_urdf.py - do not hand-edit.\n'
           '     Regenerate after changing any robot xacro or a cell pose. -->\n')
    src.write_text(hdr + ET.tostring(cell, encoding='unicode') + '\n')
    print(f'wrote {src}')


if __name__ == '__main__':
    main()
