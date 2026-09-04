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
M1PRO_YAW  = 0.0                        # UNKNOWN - never measured
PRO600_XYZ = (0.600, 0.200, 0.008)
PRO600_YAW = math.pi                    # UNKNOWN - never measured
# belt surface height from the conveyor MESH (36.0 mm above its origin)
BELT_XYZ   = (0.0, 0.135, 0.06265)      # centreline y from the rectified plan

ROBOTS = [
    ('m1pro',  'dobot_m1pro_description',    'dobot_m1pro.urdf.xacro',    'm1pro_',
     M1PRO_XYZ, (0.0, 0.0, M1PRO_YAW)),
    ('pro600', 'mycobot_pro600_description', 'mycobot_pro600.urdf.xacro', 'pro600_',
     PRO600_XYZ, (0.0, 0.0, PRO600_YAW)),
    ('belt',   'wafer_cell_bringup',         'conveyor.urdf.xacro',       'belt_',
     BELT_XYZ, (0.0, 0.0, 0.0)),
]

# ---------------------------------------------------------------- belt waypoints (belt_travel joint, m)
BELT_A = -0.14      # load: holder centre at rest in the photo
BELT_B =  0.03      # mid-belt dwell point (no dwell seen in the 09-03 video)
BELT_C =  0.20      # unload: ~75 % along the belt in the video

# ---------------------------------------------------------------- nests (model origin = wafer-seat arc centre)
# The tower STL is Y-up: its +X is the OPEN chord side. rpy (pi/2, 0, yaw)
# stands it up; yaw pi opens toward -X, yaw 0 toward +X.
NEST_YELLOW     = (-0.353, -0.162, 0.005)
NEST_YELLOW_RPY = (1.5708, 0.0, 3.14159)   # opens toward -X, toward the M1 Pro
NEST_BLUE       = (0.430, -0.153, 0.005)
NEST_BLUE_RPY   = (1.5708, 0.0, 0.0)       # opens toward +X, toward the Pro 600
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
    'm1pro_z_lift':   0.1192,
    'm1pro_shoulder': -1.0320,
    'm1pro_elbow':    1.0352,
    'm1pro_wrist':    2.0330,       # == -4.2502 rad, same pose
    'pro600_joint1':  -0.1115,
    'pro600_joint2':  0.1565,
    'pro600_joint3':  1.6460,
    'pro600_joint4':  -0.2318,
    'pro600_joint5':  -1.5708,
    'pro600_joint6':  -0.5395,
    'belt_travel':    BELT_A,
}

M1PRO_JOINTS  = ['m1pro_z_lift', 'm1pro_shoulder', 'm1pro_elbow', 'm1pro_wrist']
PRO600_JOINTS = [f'pro600_joint{i}' for i in range(1, 7)]
