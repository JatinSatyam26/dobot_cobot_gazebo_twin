import math
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
The cell's cycle as ONE table, used by three consumers:

  * cell_sequencer.py      executes it in the sim (Digital Model)
  * fake devices           replay it as if the real robots/PLC produced it
  * shadow tests           compare a recorded real cycle against it

STEPS rows: (state name, kind, payload, nominal duration s)
  kind 'm1pro' / 'pro600' : payload = waypoint key from build_waypoints()
  kind 'belt'             : payload = (x_from, x_to); duration = |dx| / belt_speed
  kind 'dwell'            : duration = dwell_b parameter
  kind 'grasp'            : payload = (carrier, attach?) ; instantaneous + settle
  kind 'event'            : marker only
Durations are the 2026-09-03 video timings, rounded; the PLC program is the
authority (metrology robot_cycle_times, point_positions).
"""
from cell_layout import (HOME, M1PRO_JOINTS, PRO600_JOINTS, NEST_YELLOW, NEST_BLUE, SHELF_Z,
                         BELT_SURFACE_Y, BELT_A, BELT_B, BELT_C, BELT_A_X, BELT_C_X, NEST_SEAT_Z, HOLDER_POST_TOP,
                         WAFER_THICKNESS, FORK_UNDER, FORK_LIFT, CUP_GAP)
from solve_home_poses import solve

FORK_AX = {0: (1, 0, 0), 2: (0, 0, 1)}      # blade flat, pointing +X (yellow nest, opens -X)
FORK_TURN = math.radians(201.70 - 107.54)   # taught: R at P5 minus R at P2, the wrist turn from the pick to the carrier (+94.16 deg)
FORK_AX_BELT = {0: (math.cos(FORK_TURN), math.sin(FORK_TURN), 0), 2: (0, 0, 1)}   # blade 4 deg past straight-across, from the front # blade flat, pointing +Y: the wrist turns the fork 90 deg on the way
                                            # to the belt and it enters the holder ACROSS the belt from the front
M1_HOME_ABOVE = 0.0866  # taught: HOME is 86.6 mm straight above the approach point (HOME -> P1 is a pure descent)
M1_LIFT_OUT   = 0.0414  # taught: P2 -> P3, the wafer is lifted 41.4 mm straight up out of the tower
CARRIER_ABOVE = 0.0348  # taught: P4 sits 34.8 mm above P5, the fork enters the carrier VERTICALLY
SWING_OUT_RAD = math.radians(19.75)   # taught: P5 -> P6 rotates J1 alone, 71.53 -> 51.78 deg, at constant height
LIFT_OUT      = 0.0755  # taught: P6 -> P7, a pure vertical lift out of the carrier
P6_PICK_ABOVE = 0.028   # taught: APPROACH -> PICK is a 28 mm vertical descent; the traverse runs at that height
P6_DROP_ABOVE = 0.037   # taught: DROP_OVER -> DROP is a 37 mm vertical descent
CUP_AX = {2: (0, 0, -1)}                     # cup pointing straight down
APPROACH = 0.139   # seat behind the nest centre: the TAUGHT insert (P1->P2 traverse, 139 mm); must exceed 93.5 mm (30 mm tip overhang + 63.5 mm wafer radius) so a vertical descent clears the rim
CLEAR = 0.045                                # lift above a nest rim before travelling
GRASP_SETTLE = 0.8          # let the JTC reach its (tight) goal band before welding/releasing

STEPS = [
    ('RELEASE_ALL',           'event',  None,                 0.0),
    ('M1_DESCEND',            'm1pro',  'approach',           2.0),   # HOME -> P1: 86.6 mm straight down, in front of the opening
    ('M1_INSERT_UNDER_WAFER', 'm1pro',  'insert',             2.5),   # P1 -> P2: 139 mm in under the wafer through the opening
    ('M1_ENGAGE_WAFER',       'm1pro',  'engage',             0.8),
    ('FORK_ATTACH',           'grasp',  ('fork', True),       GRASP_SETTLE),
    ('M1_LIFT',               'm1pro',  'lift',               1.0),   # P2 -> P3: 41.4 mm straight up out of the top slot
    ('M1_TO_BELT',            'm1pro',  'above_carrier',      3.0),   # P3 -> P4: swing to directly above the carrier, wrist turned 90 deg
    ('M1_SET_DOWN',           'm1pro',  'belt_set',           1.5),   # P4 -> P5, first part: 34.8 mm straight down, wafer to 0.3 mm above the seat
    ('FORK_DETACH',           'grasp',  ('fork', False),      GRASP_SETTLE),
    ('M1_DROP_BLADE',         'm1pro',  'belt_free',          0.8),   # P5, second part: tines on down to 4 mm below the seated wafer
    ('NEST_ATTACH',           'grasp',  ('nest', True),       GRASP_SETTLE),
    ('M1_SWING_OUT',          'm1pro',  'belt_swing',         1.5),   # P5 -> P6: J1 alone, -19.75 deg, constant height; the tines slide out under the wafer
    ('M1_LIFT_OUT',           'm1pro',  'belt_lift',          1.5),   # P6 -> P7: 75.5 mm straight up
    ('M1_HOME',               'm1pro',  'home',               3.0),
    ('BELT_A_TO_B',           'belt',   (BELT_A, BELT_B),     None),
    ('BELT_DWELL_B',          'dwell',  None,                 None),
    ('BELT_B_TO_C',           'belt',   (BELT_B, BELT_C),     None),
    ('NEST_DETACH',           'grasp',  ('nest', False),      GRASP_SETTLE),
    ('P6_TO_C',               'pro600', 'approach_c',         3.0),   # HOME -> APPROACH: 28 mm above the wafer on the carrier
    ('P6_DESCEND',            'pro600', 'pick',               1.0),   # APPROACH -> PICK: 28 mm straight down
    ('CUP_ATTACH',            'grasp',  ('cup', True),        GRASP_SETTLE),
    ('P6_LIFT',               'pro600', 'approach_c',         1.5),   # PICK -> APPROACH
    ('P6_TO_BLUE',            'pro600', 'over_blue',          3.0),   # APPROACH -> DROP_OVER: the near-flat traverse, 37 mm above the drop
    ('P6_PLACE',              'pro600', 'place',              1.0),   # DROP_OVER -> DROP: 37 mm straight down
    ('CUP_DETACH',            'grasp',  ('cup', False),       GRASP_SETTLE),
    ('P6_UP',                 'pro600', 'over_blue',          1.5),   # DROP -> DROP_OVER
    ('P6_HOME',               'pro600', 'home',               3.0),
    ('CYCLE_DONE',            'event',  None,                 0.0),
    # The bench carries the carriage back BY HAND (it indexes one way only): this
    # step is the stand-in for that, outside the cycle, so the next cycle can run.
    ('MANUAL_RETURN_A',       'belt',   (BELT_C, BELT_A),     None),
]


def build_waypoints(chain, log=None):
    """IK for every waypoint from the current layout. Returns ({m1pro key: q}, {pro600 key: q})."""
    yx, yy = NEST_YELLOW[0], NEST_YELLOW[1]
    bx, by = NEST_BLUE[0], NEST_BLUE[1]
    belt_y = BELT_SURFACE_Y            # the carriage rides the belt band, not the mesh box centre
    z_pick = SHELF_Z[2] - FORK_UNDER      # slide in well under the wafer
    z_engage = SHELF_Z[2] + FORK_LIFT     # raise: the tines lift the wafer 1 mm off its shelf, then it is welded
    z_carry = z_pick + M1_LIFT_OUT        # taught 41.4 mm lift: clears the 6 mm of wall above the top slot
    # Belt holder hand-off from the TAUGHT poses (P4..P7): arrive directly above the
    # carrier, descend vertically (wafer into the lip, tines on down between the
    # posts), swing out on J1 alone at constant height, lift straight up.
    z_set = NEST_SEAT_Z + 0.0003                  # wafer underside 0.3 mm above the seat at release
    z_free = NEST_SEAT_Z - FORK_UNDER             # blade top 4 mm below the seat (blade bottom 36 mm, plate top 3 mm)
    z_above = z_set + CARRIER_ABOVE               # P4
    w_top_nest = NEST_SEAT_Z + WAFER_THICKNESS
    w_top_blue = SHELF_Z[2] + WAFER_THICKNESS

    def ik(joints, link, target, axes, seed):
        q, err, margin = solve(chain, joints, link, target, axes, seed=seed)
        if err > 0.004 and log:
            log(f'IK {link} -> {tuple(round(v, 3) for v in target)}: {err * 1e3:.1f} mm off, margin {margin:.2f}')
        return [q[j] for j in joints]

    m = {}
    s = [HOME[j] for j in M1PRO_JOINTS]
    # HOME sits 86.6 mm straight above the approach point (taught), so the first move
    # of the cycle is a pure descent in front of the opening and never crosses the rim.
    for key, tgt, ax in [('approach', (yx - APPROACH, yy, z_pick), FORK_AX), ('insert', (yx, yy, z_pick), FORK_AX),
                         ('engage', (yx, yy, z_engage), FORK_AX), ('lift', (yx, yy, z_carry), FORK_AX),
                         ('above_carrier', (BELT_A_X, belt_y, z_above), FORK_AX_BELT),
                         ('belt_set', (BELT_A_X, belt_y, z_set), FORK_AX_BELT),
                         ('belt_free', (BELT_A_X, belt_y, z_free), FORK_AX_BELT)]:
        s = m[key] = ik(M1PRO_JOINTS, 'm1pro_fork_seat', tgt, ax, s)
    # P5 -> P6 is J1 ALONE: a joint-space waypoint, not an IK target. The sign is the one
    # that moves the seat back along the blade (retreat), found by FK, never assumed.
    q_free = dict(zip(M1PRO_JOINTS, m['belt_free']))
    M0 = chain.pose('m1pro_fork_seat', q_free)
    best = None
    for sgn in (+1.0, -1.0):
        q = dict(q_free); q['m1pro_shoulder'] += sgn * SWING_OUT_RAD
        d = chain.pose('m1pro_fork_seat', q)[:3, 3] - M0[:3, 3]
        along = float(d @ M0[:3, 0])
        if best is None or along < best[0]:
            best = (along, q)
    if best[0] >= 0 and log:
        log(f'swing-out: neither shoulder sign retreats the blade (best along-blade {best[0]*1e3:.1f} mm)')
    m['belt_swing'] = [best[1][j] for j in M1PRO_JOINTS]
    q_lift = dict(best[1]); q_lift['m1pro_z_lift'] += LIFT_OUT      # P6 -> P7, Z only
    m['belt_lift'] = [q_lift[j] for j in M1PRO_JOINTS]
    m['home'] = [HOME[j] for j in M1PRO_JOINTS]

    p = {}
    s = [HOME[j] for j in PRO600_JOINTS]
    cup_gap = CUP_GAP
    # His nine-move cycle: APPROACH 28 mm above the pick, DROP_OVER 37 mm above the drop,
    # and the traverse between them at that height (7 mm of lift across a 550 mm swing).
    for key, tgt in [('approach_c', (BELT_C_X, belt_y, w_top_nest + cup_gap + P6_PICK_ABOVE)),
                     ('pick', (BELT_C_X, belt_y, w_top_nest + cup_gap)),
                     ('over_blue', (bx, by, w_top_blue + cup_gap + 0.0005 + P6_DROP_ABOVE)),
                     ('place', (bx, by, w_top_blue + cup_gap + 0.0005))]:
        s = p[key] = ik(PRO600_JOINTS, 'pro600_cup_tip', tgt, CUP_AX, s)
    p['home'] = [HOME[j] for j in PRO600_JOINTS]
    return m, p


def expand_timeline(belt_speed=0.07, dwell_b=0.0, speed_scale=1.0):
    """[(t0, t1, name, kind, payload)] with absolute times from cycle start."""
    t = 0.0
    out = []
    for name, kind, payload, dur in STEPS:
        if kind == 'belt':
            dur = abs(payload[1] - payload[0]) / belt_speed
        elif kind == 'dwell':
            dur = dwell_b
        elif kind in ('m1pro', 'pro600'):
            dur = dur * speed_scale
        out.append((t, t + dur, name, kind, payload))
        t += dur
    return out


class CycleState:
    """What every device would read at elapsed time t of an ideal cycle:
    joint vectors (linear interpolation between waypoints), belt position,
    the current step name, and which carrier holds the wafer."""

    def __init__(self, m1, p6, belt_speed=0.07, dwell_b=0.0, speed_scale=1.0, cycles=1):
        self.m1, self.p6 = m1, p6
        self.tl = expand_timeline(belt_speed, dwell_b, speed_scale)
        self.total = self.tl[-1][1]
        self.cycles = cycles                 # the real cell does not loop by itself; after the
                                             # last cycle every device holds its final reading

    def at(self, t):
        if t < 0:
            t = 0.0                                              # before the epoch: hold the start
        elif self.cycles > 0 and t >= self.cycles * self.total:
            t = self.total                                       # after the last cycle: hold the end
        elif self.total > 0:
            t = t % self.total
        q1, q6 = list(self.m1['home']), list(self.p6['home'])
        belt = BELT_A
        step = self.tl[0][2]
        holder = None
        for t0, t1, name, kind, payload in self.tl:
            if t0 > t:
                break
            step = name
            f = min(1.0, (t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            if kind == 'm1pro':
                q1 = [a + (b - a) * f for a, b in zip(q1, self.m1[payload])]
            elif kind == 'pro600':
                q6 = [a + (b - a) * f for a, b in zip(q6, self.p6[payload])]
            elif kind == 'belt':
                belt = payload[0] + (payload[1] - payload[0]) * f
            elif kind == 'grasp':
                holder = payload[0] if payload[1] else None
        return dict(t=t, step=step, m1pro=q1, pro600=q6, belt=belt, holder=holder)
