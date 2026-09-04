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
                         BELT_XYZ, BELT_A, BELT_B, BELT_C, NEST_SEAT_Z, HOLDER_POST_TOP,
                         WAFER_THICKNESS, FORK_UNDER, FORK_LIFT, CUP_GAP)
from solve_home_poses import solve

FORK_AX = {0: (1, 0, 0), 2: (0, 0, 1)}      # blade flat, pointing +X (yellow nest, opens -X)
FORK_AX_BELT = {0: (0, 1, 0), 2: (0, 0, 1)} # blade flat, pointing +Y: the wrist turns the fork 90 deg on the way
                                            # to the belt and it enters the holder ACROSS the belt from the front
APPROACH_BELT = 0.08   # front approach: the wafer rides above the post tops, only the blade must clear, and it passes between the posts
CUP_AX = {2: (0, 0, -1)}                     # cup pointing straight down
APPROACH = 0.115   # seat behind the nest centre: the blade tip overhangs the seat 30 mm and the wafer rim is 63.5 mm out, so >93.5 mm or the descent lands the tip on the rim (cycle 9)
CLEAR = 0.045                                # lift above a nest rim before travelling
GRASP_SETTLE = 0.8          # let the JTC reach its (tight) goal band before welding/releasing

STEPS = [
    ('RELEASE_ALL',           'event',  None,                 0.0),
    ('M1_BACK_HIGH',          'm1pro',  'back_high',          2.5),
    ('M1_APPROACH_YELLOW',    'm1pro',  'approach',           1.5),
    ('M1_INSERT_UNDER_WAFER', 'm1pro',  'insert',             2.0),
    ('M1_ENGAGE_WAFER',       'm1pro',  'engage',             0.8),
    ('FORK_ATTACH',           'grasp',  ('fork', True),       GRASP_SETTLE),
    ('M1_LIFT',               'm1pro',  'lift',               1.0),
    ('M1_TO_BELT',            'm1pro',  'to_belt',            3.0),
    ('M1_LOWER_TO_NEST',      'm1pro',  'belt_approach',      1.0),
    ('M1_INSERT_INTO_NEST',   'm1pro',  'belt_insert',        2.0),   # wafer 2 mm above the lip, blade between the posts
    # Hand-off as in the owner's videos (2026-09-04): the fork, turned 90 deg
    # on its wrist during M1_TO_BELT, enters ACROSS the belt from the front
    # between the two posts (which stand at the belt-axis ends).
    ('M1_SET_DOWN',           'm1pro',  'belt_set',           1.0),   # lower until the wafer is 0.3 mm above the seat
    ('FORK_DETACH',           'grasp',  ('fork', False),      GRASP_SETTLE),
    ('M1_DROP_BLADE',         'm1pro',  'belt_free',          0.8),   # blade 4 mm below the seated wafer
    ('NEST_ATTACH',           'grasp',  ('nest', True),       GRASP_SETTLE),
    ('M1_RETREAT',            'm1pro',  'belt_retreat',       1.5),   # back out under the wafer, between the posts
    ('M1_HOME',               'm1pro',  'home',               3.0),
    ('BELT_A_TO_B',           'belt',   (BELT_A, BELT_B),     None),
    ('BELT_DWELL_B',          'dwell',  None,                 None),
    ('BELT_B_TO_C',           'belt',   (BELT_B, BELT_C),     None),
    ('NEST_DETACH',           'grasp',  ('nest', False),      GRASP_SETTLE),
    ('P6_ABOVE_C',            'pro600', 'above_c',            3.0),
    ('P6_NEAR_C',             'pro600', 'near_c',             1.5),
    ('P6_DESCEND',            'pro600', 'pick',               1.0),
    ('CUP_ATTACH',            'grasp',  ('cup', True),        GRASP_SETTLE),
    ('P6_LIFT_CLEAR',         'pro600', 'near_c',             1.0),
    ('P6_LIFT',               'pro600', 'lift',               1.5),
    ('P6_TO_BLUE',            'pro600', 'above_blue',         3.0),
    ('P6_NEAR_BLUE',          'pro600', 'near_blue',          1.5),
    ('P6_PLACE',              'pro600', 'place',              1.0),
    ('CUP_DETACH',            'grasp',  ('cup', False),       GRASP_SETTLE),
    ('P6_UP_CLEAR',           'pro600', 'near_blue',          1.0),
    ('P6_UP',                 'pro600', 'up',                 1.5),
    ('P6_HOME',               'pro600', 'home',               3.0),
    ('BELT_RETURN_A',         'belt',   (BELT_C, BELT_A),     None),
    ('CYCLE_DONE',            'event',  None,                 0.0),
]


def build_waypoints(chain, log=None):
    """IK for every waypoint from the current layout. Returns ({m1pro key: q}, {pro600 key: q})."""
    yx, yy = NEST_YELLOW[0], NEST_YELLOW[1]
    bx, by = NEST_BLUE[0], NEST_BLUE[1]
    belt_y = BELT_XYZ[1]
    z_pick = SHELF_Z[2] - FORK_UNDER      # slide in well under the wafer
    z_engage = SHELF_Z[2] + FORK_LIFT     # raise: the tines lift the wafer 1 mm off its shelf, then it is welded
    z_carry = SHELF_Z[2] + CLEAR
    # Belt holder hand-off as in the owner's videos: the blade, turned to point +Y,
    # travels ACROSS the belt from the front between the posts. Carry the wafer in
    # 2 mm above the lip, lower it to 0.3 mm above the seat, release, drop the
    # blade 4 mm under the seated wafer and back out to the front.
    z_hi = HOLDER_POST_TOP + 0.002                # blade top = wafer underside while sliding in over the lip
    z_set = NEST_SEAT_Z + 0.0003                  # wafer underside 0.3 mm above the seat at release
    z_free = NEST_SEAT_Z - FORK_UNDER             # blade top 4 mm below the seat (blade bottom 36 mm, plate top 3 mm)
    w_top_nest = NEST_SEAT_Z + WAFER_THICKNESS
    w_top_blue = SHELF_Z[2] + WAFER_THICKNESS

    def ik(joints, link, target, axes, seed):
        q, err, margin = solve(chain, joints, link, target, axes, seed=seed)
        if err > 0.004 and log:
            log(f'IK {link} -> {tuple(round(v, 3) for v in target)}: {err * 1e3:.1f} mm off, margin {margin:.2f}')
        return [q[j] for j in joints]

    m = {}
    s = [HOME[j] for j in M1PRO_JOINTS]
    # 'back_high' first: the rest pose parks the fork 26 mm ABOVE this nest, and a straight
    # joint-space move from there to the low approach point sweeps the blade down through
    # the wafer's rim (streamed probe 2026-09-04: pitched it 20 deg, later flipped it).
    for key, tgt, ax in [('back_high', (yx - APPROACH, yy, z_carry), FORK_AX),
                         ('approach', (yx - APPROACH, yy, z_pick), FORK_AX), ('insert', (yx, yy, z_pick), FORK_AX),
                         ('engage', (yx, yy, z_engage), FORK_AX), ('lift', (yx, yy, z_carry), FORK_AX),
                         ('to_belt', (BELT_A, belt_y - APPROACH_BELT, z_hi + CLEAR), FORK_AX_BELT),
                         ('belt_approach', (BELT_A, belt_y - APPROACH_BELT, z_hi), FORK_AX_BELT),
                         ('belt_insert', (BELT_A, belt_y, z_hi), FORK_AX_BELT),
                         ('belt_set', (BELT_A, belt_y, z_set), FORK_AX_BELT), ('belt_free', (BELT_A, belt_y, z_free), FORK_AX_BELT),
                         ('belt_retreat', (BELT_A, belt_y - APPROACH_BELT, z_free), FORK_AX_BELT)]:
        s = m[key] = ik(M1PRO_JOINTS, 'm1pro_fork_seat', tgt, ax, s)
    m['home'] = [HOME[j] for j in M1PRO_JOINTS]

    p = {}
    s = [HOME[j] for j in PRO600_JOINTS]
    cup_gap = CUP_GAP
    # 'near_*' waypoints 20 mm above the pick and the place: a joint-space move of a 6-axis arm
    # bows sideways mid-path (5 mm over a 120 mm descent, cycle 10), and the nests leave the
    # wafer 1 mm radial clearance, so the last stretch must be short enough to be straight.
    for key, tgt in [('above_c', (BELT_C, belt_y, w_top_nest + 0.12)), ('near_c', (BELT_C, belt_y, w_top_nest + 0.02)),
                     ('pick', (BELT_C, belt_y, w_top_nest + cup_gap)),
                     ('lift', (BELT_C, belt_y, w_top_nest + 0.12)), ('above_blue', (bx, by, w_top_blue + 0.12)),
                     ('near_blue', (bx, by, w_top_blue + 0.02)), ('place', (bx, by, w_top_blue + cup_gap + 0.0005)),
                     ('up', (bx, by, w_top_blue + 0.12))]:
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
