"""Shared helpers for the shadow bridges."""
import os, sys, math, time
from pathlib import Path
from ament_index_python.packages import get_package_prefix

# cell_layout / cell_plan / solver live in the bringup package's lib dir
sys.path.insert(0, os.path.join(get_package_prefix('wafer_cell_bringup'), 'lib', 'wafer_cell_bringup'))
from cell_layout import M1PRO_JOINTS, PRO600_JOINTS, HOME, BELT_A          # noqa: E402

# Real-mode client libraries (pymycobot, pycomm3) live in a venv so the system
# python stays clean: ~/venvs/wafer_shadow, created with --system-site-packages.
SHADOW_VENV = os.environ.get('SHADOW_VENV', os.path.expanduser('~/venvs/wafer_shadow'))


def use_venv():
    sp = Path(SHADOW_VENV) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    if sp.exists() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))
    return sp.exists()


# ---- unit mapping: real device -> sim joints (radians, metres) and back
def m1pro_real_to_sim(j_deg_mm, sign, offset):
    """Dobot label order [J1 deg, J2 deg, J3 mm, J4 deg] -> sim joint dict."""
    j1, j2, j3, j4 = j_deg_mm[:4]
    return {'m1pro_shoulder': sign[0] * math.radians(j1) + offset[0],
            'm1pro_elbow':    sign[1] * math.radians(j2) + offset[1],
            'm1pro_z_lift':   sign[2] * (j3 / 1000.0) + offset[2],
            'm1pro_wrist':    sign[3] * math.radians(j4) + offset[3]}


def m1pro_sim_to_real(q, sign, offset):
    """Inverse of the above; used by the fake device so the round trip is exercised."""
    return [math.degrees((q['m1pro_shoulder'] - offset[0]) / sign[0]),
            math.degrees((q['m1pro_elbow'] - offset[1]) / sign[1]),
            1000.0 * (q['m1pro_z_lift'] - offset[2]) / sign[2],
            math.degrees((q['m1pro_wrist'] - offset[3]) / sign[3])]


def pro600_real_to_sim(deg6, sign, offset):
    return {f'pro600_joint{i + 1}': sign[i] * math.radians(deg6[i]) + offset[i] for i in range(6)}


def pro600_sim_to_real(q, sign, offset):
    return [math.degrees((q[f'pro600_joint{i + 1}'] - offset[i]) / sign[i]) for i in range(6)]


def fake_cycle_state(node):
    """Build the ideal-cycle model (IK from the current layout) for fake sources.
    All fakes share the same absolute epoch (parameter fake_t0, set by the
    launch file) so the three devices stay in step."""
    from cell_fk import Chain
    from cell_plan import build_waypoints, CycleState
    from ament_index_python.packages import get_package_share_directory
    urdf = Path(get_package_share_directory('wafer_cell_bringup')) / 'urdf' / 'cell.urdf'
    m1, p6 = build_waypoints(Chain(str(urdf)), log=node.get_logger().warning)
    cs = CycleState(m1, p6,
                    belt_speed=float(node.get_parameter('fake_belt_speed').value),
                    dwell_b=float(node.get_parameter('fake_dwell_b').value))
    t0 = float(node.get_parameter('fake_t0').value) or time.time()
    node.get_logger().info(f'fake source: {cs.total:.1f} s cycle, epoch {t0:.1f}')
    return cs, t0


def declare_fake_params(node):
    node.declare_parameter('fake_t0', 0.0)
    node.declare_parameter('fake_belt_speed', 0.07)
    node.declare_parameter('fake_dwell_b', 0.0)
