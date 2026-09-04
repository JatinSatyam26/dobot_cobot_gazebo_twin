#!/usr/bin/env python3
"""Place the wafer on the belt holder's seat (STAND-IN for the unknown real mechanism).

The fork cannot lower the wafer into the holder: the blade must clear the
45 mm posts, so the wafer sits 5.5 mm above the 43 mm seat when the holder
takes it. A free fall from there onto the two crescent seats of a
position-driven carriage kicked the disc in 3 of 5 runs on 2026-09-04 (it was
welded standing 23 deg for the ride). Until the owner says how the real cell
does it, NEST_SEAT sets the wafer's pose onto the seat through Gazebo's
set_pose service and the holder joint then grips it there.
"""
import subprocess
from cell_layout import WAFER_MODEL


def seat_wafer(x, y, z, world='wafer_cell', timeout_ms=1500):
    req = (f'name: "{WAFER_MODEL}", position: {{x: {x:.5f}, y: {y:.5f}, z: {z:.5f}}}, '
           f'orientation: {{x: 0, y: 0, z: 0, w: 1}}')
    r = subprocess.run(['gz', 'service', '-s', f'/world/{world}/set_pose', '--reqtype', 'gz.msgs.Pose',
                        '--reptype', 'gz.msgs.Boolean', '--timeout', str(timeout_ms), '--req', req],
                       capture_output=True, text=True)
    return 'data: true' in r.stdout
