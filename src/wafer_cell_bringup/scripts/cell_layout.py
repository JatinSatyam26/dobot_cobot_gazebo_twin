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
# ---------------------------------------------------------------------------
# TAUGHT_LAYOUT (2026-09-10). The M1 Pro side is placed from the PLC programmer's
# taught poses (Cartesian, mm, robot base frame = J1 axis; verified to be the
# wrist axis: his J1 readings at P5/P6 trail the point bearings by 8.36/7.32 deg,
# exactly acos(r/400) for r 395.8/396.8 with 200+200 mm links):
#   P2 (under the wafer)  (314.13, 180.89)   P5 (in the carrier) (69.49, 389.61)
#   R 107.54 at P2 -> 201.70 at P5: the wrist turns +94.16 deg between them
# With the sim's fork (seat 147 mm ahead of the wrist axis) and base yaw -pi/2
# (insert along +X, so the tower opens -X as the owner says), the nest sits at
# J1 + (0.328, -0.314) and the carrier seat at J1 + (0.379, 0.077). The Pro 600
# side uses only his distances (base->C 468, base->blue 403, C->blue 477 mm),
# which do not depend on that arm's frame convention, with the blue nest PINNED
# to the yellow nest's line (the owner's design intent from the 09-04 look; not
# measured) - that fixes C and the Pro 600 base. The conveyor is shifted +20 mm
# in x so the carrier keeps its 09-04 place on the belt (BELT_A -0.25) while its
# seat lands at the taught world x (-0.23). Photo positions were off by 55-70 mm
# on the conveyor and the yellow tower (parallax), 13 mm on the M1 column. Still 🟡: the real fork's seat offset, the
# Pro 600's URDF yaw, and the heights (both robots say the carrier's wafer is
# ~5 mm lower relative to the towers than the meshes put it).
M1PRO_XYZ  = (-0.609, 0.204, 0.0)       # TAUGHT (2026-09-10): J1 axis = carrier A - (0.379, 0.077); column 13 mm from its photo spot
# KINEMATICALLY INFERRED, not measured (2026-09-04). With yaw 0 (carriage
# toward +X) the fork cannot withdraw along -X out of the belt nest at A: the
# wrist would have to come within 0.10 m of the shoulder and the elbow limit
# allows 0.15 m. The cycle video shows exactly that withdrawal. With the
# carriage facing the FRONT of the bench (-Y, yaw -pi/2) every waypoint of the
# cycle is reachable, which also matches the reference render and the
# parallax-corrected link positions in the overhead photo. Replace with the
# two-point measurement (metrology m1pro_base_yaw).
M1PRO_YAW  = -math.pi / 2
PRO600_XYZ = (0.600, 0.124, 0.008)      # solved from his distances (468 mm to C, 403 mm to the blue nest) with the blue nest pinned, see TAUGHT_LAYOUT
PRO600_YAW = -1.6144                    # -92.5 deg, FITTED 2026-09-11: his taught poses through the verified joint mapping land on
                                        # C, the blue nest and his HOME within 4 mm in the plane (tools/replay_telemetry.py docstring)
# belt surface height from the conveyor MESH (36.0 mm above its origin)
BELT_XYZ   = (0.02, 0.191, 0.06265)     # x: the conveyor is shifted 20 mm so the carrier keeps its 09-04 place on the belt (owner, 2026-09-10)      # conveyor MESH anchor: its bounding-box centre y from the rectified plan
# The mesh's box includes the motor housing on the rear side, so its centre is NOT the
# belt's running surface. A cross-section of dobot_conveyor.stl at mid-length puts the
# belt band at world y 0.045..0.165 (owner's GUI screenshot 2026-09-04: the holder sat
# 30 mm toward the rear). The carriage, the wafer targets and the belt cameras use this.
BELT_SURFACE_Y = 0.161   # TAUGHT: 77 mm behind the M1 J1 axis; the only belt line that keeps column, conveyor and pick tower on the bench
CARRIAGE_XYZ   = (BELT_XYZ[0], BELT_SURFACE_Y, BELT_XYZ[2])

ROBOTS = [
    ('m1pro',  'dobot_m1pro_description',    'dobot_m1pro.urdf.xacro',    'm1pro_',
     M1PRO_XYZ, (0.0, 0.0, M1PRO_YAW)),
    ('pro600', 'mycobot_pro600_description', 'mycobot_pro600.urdf.xacro', 'pro600_',
     PRO600_XYZ, (0.0, 0.0, PRO600_YAW)),
    ('belt',   'wafer_cell_bringup',         'conveyor.urdf.xacro',       'belt_',
     CARRIAGE_XYZ, (0.0, 0.0, 0.0)),
]

# ---------------------------------------------------------------- belt waypoints (belt_travel joint, m)
BELT_A = -0.25      # load, JOINT position (from the belt base): as in the 09-04 recording; the conveyor's x shift puts the seat at world -0.23
BELT_B = -0.069     # mid-belt dwell point (no dwell seen in the 09-03 video)
BELT_C =  0.113     # unload, JOINT position: world 0.133 = TAUGHT, 468 mm from the Pro 600 base on the belt line
# Stations are belt JOINT positions; the world x of a station is BELT_XYZ[0] + station.
BELT_A_X = BELT_XYZ[0] + BELT_A
BELT_C_X = BELT_XYZ[0] + BELT_C

# The belt carriage is meshes/belt_holder.stl lying plate-down on the belt:
# posts 45 mm tall at the belt-axis ends, ring seat at 43 mm, lip r ~64 mm.
NEST_SEAT_Z     = BELT_XYZ[2] + 0.043      # wafer underside on the holder's seat ring
HOLDER_POST_TOP = BELT_XYZ[2] + 0.045      # a fork blade must stay above this along the belt

# ---------------------------------------------------------------- nests (model origin = wafer-seat arc centre)
# The tower STL is Y-up: its +X is the OPEN chord side. rpy (pi/2, 0, yaw)
# stands it up; yaw pi opens toward -X, yaw 0 toward +X.
NEST_YELLOW     = (-0.281, -0.230, 0.005)   # TAUGHT: J1 axis + (0.328, -0.314); photo had (-0.353, -0.162)
NEST_YELLOW_RPY = (1.5708, 0.0, 3.14159)   # opens toward -X, toward the M1 Pro
NEST_BLUE       = (0.407, -0.230, 0.005)    # on the yellow nest's line (owner's design intent, 2026-09-10); x from his Pro 600 distances
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
# Pro 600 rest pose: HIS taught HOME joint angles through the verified mapping (joint 2 and 4 +90 deg),
# so the arm starts where the real one rests and the telemetry needs no jump. Solve nothing for it.
# M1 Pro rest pose: from the TAUGHT shape (2026-09-10) - the fork seat 86.6 mm straight above
# the approach point in front of the yellow nest (HOME -> P1 is a pure descent), blade +X.
# Solved by solve_home_poses.solve(); regenerate the URDF after touching it.
HOME = {
    'm1pro_z_lift':   0.1815,
    'm1pro_shoulder': -0.5238,
    'm1pro_elbow':    -1.2782,
    'm1pro_wrist':    0.7821,       # == -4.2502 rad, same pose
    'pro600_joint1':  -1.4187,
    'pro600_joint2':  -0.2167,
    'pro600_joint3':  2.2732,
    'pro600_joint4':  -0.4909,
    'pro600_joint5':  -1.5662,
    'pro600_joint6':  -0.0368,
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
