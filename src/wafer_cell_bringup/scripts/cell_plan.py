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
                         BELT_XYZ, BELT_A, BELT_B, BELT_C, NEST_SEAT_Z, WAFER_THICKNESS, WAFER_GAP)
from solve_home_poses import solve

FORK_AX = {0: (1, 0, 0), 2: (0, 0, 1)}      # blade flat, pointing +X
CUP_AX = {2: (0, 0, -1)}                     # cup pointing straight down
APPROACH = 0.09                              # tine tips 20 mm outside a nest's open chord
CLEAR = 0.045                                # lift above a nest rim before travelling
GRASP_SETTLE = 0.4

STEPS = [
    ('RELEASE_ALL',           'event',  None,                 0.0),
    ('M1_APPROACH_YELLOW',    'm1pro',  'approach',           3.0),
    ('M1_INSERT_UNDER_WAFER', 'm1pro',  'insert',             2.0),
    ('FORK_ATTACH',           'grasp',  ('fork', True),       GRASP_SETTLE),
    ('M1_LIFT',               'm1pro',  'lift',               1.0),
    ('M1_TO_BELT',            'm1pro',  'to_belt',            3.0),
    ('M1_LOWER_TO_NEST',      'm1pro',  'belt_approach',      1.0),
    ('M1_INSERT_INTO_NEST',   'm1pro',  'belt_insert',        2.0),
    ('FORK_DETACH',           'grasp',  ('fork', False),      GRASP_SETTLE),
    ('M1_DROP_BLADE',         'm1pro',  'belt_lower',         0.8),
    ('M1_RETREAT',            'm1pro',  'belt_retreat',       1.5),
    ('NEST_ATTACH',           'grasp',  ('nest', True),       GRASP_SETTLE),
    ('M1_HOME',               'm1pro',  'home',               3.0),
    ('BELT_A_TO_B',           'belt',   (BELT_A, BELT_B),     None),
    ('BELT_DWELL_B',          'dwell',  None,                 None),
    ('BELT_B_TO_C',           'belt',   (BELT_B, BELT_C),     None),
    ('NEST_DETACH',           'grasp',  ('nest', False),      GRASP_SETTLE),
    ('P6_ABOVE_C',            'pro600', 'above_c',            3.0),
    ('P6_DESCEND',            'pro600', 'pick',               2.0),
    ('CUP_ATTACH',            'grasp',  ('cup', True),        GRASP_SETTLE),
    ('P6_LIFT',               'pro600', 'lift',               1.5),
    ('P6_TO_BLUE',            'pro600', 'above_blue',         3.0),
    ('P6_PLACE',              'pro600', 'place',              2.0),
    ('CUP_DETACH',            'grasp',  ('cup', False),       GRASP_SETTLE),
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
    z_pick = SHELF_Z[2] - WAFER_GAP
    z_carry = SHELF_Z[2] + CLEAR
    z_place = NEST_SEAT_Z - WAFER_GAP + 0.0005
    z_free = NEST_SEAT_Z - 0.010
    w_top_nest = NEST_SEAT_Z + WAFER_THICKNESS
    w_top_blue = SHELF_Z[2] + WAFER_THICKNESS

    def ik(joints, link, target, axes, seed):
        q, err, margin = solve(chain, joints, link, target, axes, seed=seed)
        if err > 0.004 and log:
            log(f'IK {link} -> {tuple(round(v, 3) for v in target)}: {err * 1e3:.1f} mm off, margin {margin:.2f}')
        return [q[j] for j in joints]

    m = {}
    s = [HOME[j] for j in M1PRO_JOINTS]
    for key, tgt in [('approach', (yx - APPROACH, yy, z_pick)), ('insert', (yx, yy, z_pick)),
                     ('lift', (yx, yy, z_carry)), ('to_belt', (BELT_A - APPROACH, belt_y, z_place + CLEAR)),
                     ('belt_approach', (BELT_A - APPROACH, belt_y, z_place)), ('belt_insert', (BELT_A, belt_y, z_place)),
                     ('belt_lower', (BELT_A, belt_y, z_free)), ('belt_retreat', (BELT_A - APPROACH, belt_y, z_free))]:
        s = m[key] = ik(M1PRO_JOINTS, 'm1pro_fork_seat', tgt, FORK_AX, s)
    m['home'] = [HOME[j] for j in M1PRO_JOINTS]

    p = {}
    s = [HOME[j] for j in PRO600_JOINTS]
    for key, tgt in [('above_c', (BELT_C, belt_y, w_top_nest + 0.12)), ('pick', (BELT_C, belt_y, w_top_nest + WAFER_GAP)),
                     ('lift', (BELT_C, belt_y, w_top_nest + 0.12)), ('above_blue', (bx, by, w_top_blue + 0.12)),
                     ('place', (bx, by, w_top_blue + WAFER_GAP + 0.0005)), ('up', (bx, by, w_top_blue + 0.12))]:
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

    def __init__(self, m1, p6, belt_speed=0.07, dwell_b=0.0, speed_scale=1.0):
        self.m1, self.p6 = m1, p6
        self.tl = expand_timeline(belt_speed, dwell_b, speed_scale)
        self.total = self.tl[-1][1]

    def at(self, t):
        t = 0.0 if t < 0 else (t % self.total if self.total > 0 else 0.0)   # before the epoch: hold the start
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
