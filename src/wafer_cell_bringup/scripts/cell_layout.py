# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Single source of truth for every numeric pose in the cell.

Imported by generate_cell_urdf.py, go_home.py, check_extents.py and
cell.launch.py. worlds/wafer_cell.sdf carries the SAME numbers by hand
(static XML); check_extents.py asserts the two agree, so a mismatch fails
loudly instead of drifting.

Frame: world origin at the bench-top centre, +X from the M1 Pro toward the
Pro 600 (wafer flow), +Y toward the REAR edge, +Z up. Bench top is z = 0.

PROVENANCE OF THE LAYOUT (2026-09-03, interim)
----------------------------------------------
Positions below are ESTIMATED from the owner's overhead photograph
docs/reference_photos_2/20260902_114748.heic, rectified to a 1 px = 1 mm
plan by a homography on the four board corners and corrected for parallax
(camera solved at 1.72 m above the board). Expected accuracy +/-20 mm. See
docs/research_2026-09-03/RESEARCH_REVIEW.md section 4. They replace two
rounds of eyeballed guesses and are themselves to be replaced by the
metrology-spec measurements when they land.

  VERIFIED from photo : nest opening directions, motor end of the conveyor
  ESTIMATED +/-20 mm  : every xyz below
  UNKNOWN             : both base YAW angles (kept at the old values),
                        both rest poses (solved by FK, not read off a pendant)
"""
import math

# ---------------------------------------------------------------- robots
# name -> (package, xacro, prefix, xyz, rpy)
M1PRO_XYZ  = (-0.600, 0.188, 0.008)     # base flush with the rear edge in the photo
# KINEMATICALLY INFERRED, not measured (2026-09-04). With yaw 0 (carriage
# toward +X) the fork cannot withdraw along -X out of the belt nest at A: the
# wrist would have to come within 0.10 m of the shoulder and the elbow limit
# allows 0.15 m. The cycle video shows exactly that withdrawal. With the
# carriage facing the FRONT of the bench (-Y, yaw -pi/2) every waypoint of the
# cycle is reachable, which also matches the reference render and the
# parallax-corrected link positions in the overhead photo. Replace with the
# two-point measurement (metrology m1pro_base_yaw).
M1PRO_YAW  = -math.pi / 2
PRO600_XYZ = (0.600, 0.200, 0.008)
PRO600_YAW = math.pi                    # UNKNOWN - never measured
# belt surface height from the conveyor MESH (36.0 mm above its origin)
BELT_XYZ   = (0.0, 0.135, 0.06265)      # conveyor MESH anchor: its bounding-box centre y from the rectified plan
# The mesh's box includes the motor housing on the rear side, so its centre is NOT the
# belt's running surface. A cross-section of dobot_conveyor.stl at mid-length puts the
# belt band at world y 0.045..0.165 (owner's GUI screenshot 2026-09-04: the holder sat
# 30 mm toward the rear). The carriage, the wafer targets and the belt cameras use this.
BELT_SURFACE_Y = 0.105
CARRIAGE_XYZ   = (0.0, BELT_SURFACE_Y, BELT_XYZ[2])

ROBOTS = [
    ('m1pro',  'dobot_m1pro_description',    'dobot_m1pro.urdf.xacro',    'm1pro_',
     M1PRO_XYZ, (0.0, 0.0, M1PRO_YAW)),
    ('pro600', 'mycobot_pro600_description', 'mycobot_pro600.urdf.xacro', 'pro600_',
     PRO600_XYZ, (0.0, 0.0, PRO600_YAW)),
    ('belt',   'wafer_cell_bringup',         'conveyor.urdf.xacro',       'belt_',
     CARRIAGE_XYZ, (0.0, 0.0, 0.0)),
]

# ---------------------------------------------------------------- belt waypoints (belt_travel joint, m)
BELT_A = -0.25      # load: holder beside the M1 Pro column, its end at the belt's end (owner's hand-off video); the photo had -0.14
BELT_B =  0.03      # mid-belt dwell point (no dwell seen in the 09-03 video)
BELT_C =  0.20      # unload: ~75 % along the belt in the video

# The belt carriage is meshes/belt_holder.stl lying plate-down on the belt:
# posts 45 mm tall at the belt-axis ends, ring seat at 43 mm, lip r ~64 mm.
NEST_SEAT_Z     = BELT_XYZ[2] + 0.043      # wafer underside on the holder's seat ring
HOLDER_POST_TOP = BELT_XYZ[2] + 0.045      # a fork blade must stay above this along the belt

# ---------------------------------------------------------------- nests (model origin = wafer-seat arc centre)
# The tower STL is Y-up: its +X is the OPEN chord side. rpy (pi/2, 0, yaw)
# stands it up; yaw pi opens toward -X, yaw 0 toward +X.
NEST_YELLOW     = (-0.353, -0.162, 0.005)
NEST_YELLOW_RPY = (1.5708, 0.0, 3.14159)   # opens toward -X, toward the M1 Pro
NEST_BLUE       = (0.430, -0.153, 0.005)
NEST_BLUE_RPY   = (1.5708, 0.0, 3.14159)   # opens toward -X, same as the yellow one (owner, 2026-09-04;
                                           # the 2026-09-02 photo showed it opening +X)
SHELF_Z         = (0.0550, 0.0770, 0.0990) # measured off the mesh, settled

# ---------------------------------------------------------------- wafer
WAFER_RADIUS    = 0.0635
WAFER_THICKNESS = 0.0015                   # exaggerated for contact stability
WAFER_SPAWN     = (NEST_YELLOW[0], NEST_YELLOW[1], SHELF_Z[2] + WAFER_THICKNESS / 2)

# ---------------------------------------------------------------- joints
# (lower, upper). Initial values must sit strictly INSIDE: a joint
# initialised at a limit latches and ignores every command.
JOINT_LIMITS = {
    'm1pro_z_lift':   (0.0, 0.25),
    'm1pro_shoulder': (-1.483530, 1.483530),
    'm1pro_elbow':    (-2.356194, 2.356194),
    'm1pro_wrist':    (-6.283185, 6.283185),
    'pro600_joint1':  (-3.1400, 3.14159),
    'pro600_joint2':  (-4.7123, 1.5708),
    'pro600_joint3':  (-2.6179, 2.6179),
    'pro600_joint4':  (-4.5378, 1.3962),
    'pro600_joint5':  (-2.9321, 2.9321),
    'pro600_joint6':  (-3.0368, 3.0368),
    'belt_travel':    (-0.30, 0.30),
}

# Home / rest pose. SOLVED by scripts/solve_home_poses.py against this
# layout, NOT read off a pendant (that is metrology item m1pro_home /
# pro600_home). M1 Pro: fork flat, pointing +X, hovering above the yellow
# nest. Pro 600: cup pointing straight down above belt point C.
HOME = {
    'm1pro_z_lift':   0.1181,
    'm1pro_shoulder': -0.4821,
    'm1pro_elbow':    -1.7612,
    'm1pro_wrist':    0.2567,       # == -4.2502 rad, same pose
    'pro600_joint1':  -0.1115,
    'pro600_joint2':  0.1565,
    'pro600_joint3':  1.6460,
    'pro600_joint4':  -0.2318,
    'pro600_joint5':  -1.5708,
    'pro600_joint6':  -0.5395,
    'belt_travel':    BELT_A,
}

M1PRO_JOINTS  = ['m1pro_z_lift', 'm1pro_shoulder', 'm1pro_elbow', 'm1pro_wrist']

# ---------------------------------------------------------------- grasp (DetachableJoint carriers)
WAFER_MODEL = 'wafer'
# The DetachableJoint parent must be a link that SURVIVES the URDF->SDF
# conversion: sdformat merges every link that hangs off a FIXED joint into
# its parent, so m1pro_fork lives inside m1pro_wrist_link and pro600_cup
# inside pro600_link6 (the plugin logged "Link ... not found in model
# wafer_cell" for both on 2026-09-04). A fixed joint to the merged parent is
# the same rigid grasp. belt_carriage is on a prismatic joint and survives.
GRASP_LINKS = {'fork': 'm1pro_wrist_link', 'cup': 'pro600_link6', 'nest': 'belt_carriage'}
FORK_SEAT_X = 0.147     # wafer centre on the blade, from the wrist axis (tine tips 30 mm past it)
FORK_UNDER  = 0.004     # blade top this far under the wafer while sliding in (the ledge below leaves 19 mm)
FORK_LIFT   = 0.001     # blade then rises to this far ABOVE the wafer's resting underside: it lifts the wafer, which then rests on the tines
CUP_GAP     = 0.002     # cup lip stops this far above the wafer (a joint needs no contact)
PRO600_JOINTS = [f'pro600_joint{i}' for i in range(1, 7)]
