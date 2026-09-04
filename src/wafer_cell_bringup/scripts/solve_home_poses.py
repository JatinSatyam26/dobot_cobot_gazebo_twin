#!/usr/bin/env python3
"""
Solve the two rest poses (and any pick pose you like) by numerical IK on the
generated cell.urdf, then check every joint's margin to its limits.

    ros2 run wafer_cell_bringup solve_home_poses.py            # both arms, home
    ros2 run wafer_cell_bringup solve_home_poses.py --json     # machine-readable

Targets come from cell_layout.py so the rest pose follows the layout. The
result is printed; paste it into cell_layout.HOME and regenerate. The rest
pose is an ASSUMPTION until the pendant values replace it (metrology items
m1pro_home / pro600_home).

Method: scipy least_squares over the joint vector with bounds MARGIN inside
each limit, from several starts, keeping the solution with the best worst-case
limit margin among those that hit the target. FK is cell_fk.Chain - straight
off the URDF, no DH assumptions.
"""
import sys, json, math
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cell_fk import Chain
from cell_layout import (JOINT_LIMITS, NEST_YELLOW, SHELF_Z, WAFER_THICKNESS, BELT_XYZ, BELT_C,
                         M1PRO_JOINTS, PRO600_JOINTS)
from ament_index_python.packages import get_package_share_directory

MARGIN = 0.10          # rad inside every revolute limit
PRISMATIC = {'m1pro_z_lift', 'belt_travel'}
MARGIN_M = 0.01        # m inside a prismatic limit (0.10 would eat 80 % of the Z stroke)


def lim_margin(j):
    return MARGIN_M if j in PRISMATIC else MARGIN


def solve(chain, joints, link, target, axes, starts=12, seed=0):
    """axes: dict {column index 0/1/2 of the link's rotation: world unit vector}."""
    lo = np.array([JOINT_LIMITS[j][0] + lim_margin(j) for j in joints])
    hi = np.array([JOINT_LIMITS[j][1] - lim_margin(j) for j in joints])
    rng = np.random.default_rng(seed)

    def resid(q):
        M = chain.pose(link, dict(zip(joints, q)))
        r = [M[:3, 3] - np.array(target)]
        for col, vec in axes.items():
            r.append(0.3 * (M[:3, col] - np.array(vec)))
        return np.concatenate(r)

    best = None
    for k in range(starts):
        q0 = lo + rng.random(len(joints)) * (hi - lo) if k else (lo + hi) / 2
        sol = least_squares(resid, q0, bounds=(lo, hi), xtol=1e-10, ftol=1e-10)
        err = np.linalg.norm(resid(sol.x)[:3])
        margin = min(min(q - JOINT_LIMITS[j][0], JOINT_LIMITS[j][1] - q)
                     for j, q in zip(joints, sol.x))
        cand = (err > 2e-3, -margin, err, sol.x)          # hit target first, then margin
        if best is None or cand[:3] < best[:3]:
            best = cand
    miss, negm, err, q = best
    q = [float(v) for v in q]
    # a +/-2pi joint (the M1 Pro wrist) may come back at -4.25 rad; the same
    # pose at 2.03 rad reads better and starts nearer the middle of the range
    for i, j in enumerate(joints):
        lo_j, hi_j = JOINT_LIMITS[j]
        if hi_j - lo_j >= 2 * math.pi - 1e-6 and j not in PRISMATIC:
            q[i] = math.atan2(math.sin(q[i]), math.cos(q[i]))
    return dict(zip(joints, [round(v, 4) for v in q])), err, -negm


def main():
    share = Path(get_package_share_directory('wafer_cell_bringup'))
    chain = Chain(str(share / 'urdf' / 'cell.urdf'))
    out = {}

    # M1 Pro home: fork seat 25 mm above the wafer on the yellow nest's top
    # shelf, blade flat (tool z up) and pointing +X (tool x = world +X), so it
    # is exactly the retreat pose of a pick on this layout.
    t = (NEST_YELLOW[0], NEST_YELLOW[1], SHELF_Z[2] + WAFER_THICKNESS + 0.025)
    q, err, m = solve(chain, M1PRO_JOINTS, 'm1pro_fork_seat', t, {0: (1, 0, 0), 2: (0, 0, 1)})
    out['m1pro'] = dict(q=q, target=t, pos_err_mm=round(err * 1e3, 2), min_margin=round(m, 3))

    # Pro 600 home: cup tip 0.30 above the belt at point C, pointing straight
    # down (cup z = world -z).
    t = (BELT_C, BELT_XYZ[1], 0.30)
    q, err, m = solve(chain, PRO600_JOINTS, 'pro600_cup_tip', t, {2: (0, 0, -1)})
    out['pro600'] = dict(q=q, target=t, pos_err_mm=round(err * 1e3, 2), min_margin=round(m, 3))

    if '--json' in sys.argv:
        print(json.dumps(out, indent=1))
        return
    for arm, r in out.items():
        print(f"{arm}: target {tuple(round(v, 3) for v in r['target'])}  "
              f"pos err {r['pos_err_mm']} mm  worst limit margin {r['min_margin']} rad")
        for j, v in r['q'].items():
            print(f"    '{j}': {v},")


if __name__ == '__main__':
    main()
