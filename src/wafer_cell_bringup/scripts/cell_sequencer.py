#!/usr/bin/env python3
"""
Cell sequencer - the Micro850's state machine as a ROS 2 node (Digital Model).

    ros2 run wafer_cell_bringup cell_sequencer.py
    ros2 run wafer_cell_bringup cell_sequencer.py --ros-args -p dwell_b:=5.0 -p cycles:=2

Yellow nest -> [fork lifts wafer] -> belt nest at A -> belt A->B (dwell) ->C
-> [cup lifts wafer] -> blue nest. Every waypoint is solved by IK at start-up
from the poses in cell_layout.py, so a layout change moves the whole cycle.
Timing comes from the 2026-09-03 cycle video (docs/research_2026-09-03);
the PLC program is the authority and these are parameters.

Grasps are gz DetachableJoint fixed joints (attach/detach over
/wafer/<carrier>/attach|detach, bridged in cell.launch.py). The belt nest
also grabs the wafer while the belt runs, so the ride is a joint, not friction.

The step names published on /cell/state are the hooks for the Digital Shadow:
a PLC bridge that publishes the same names replaces this node's timer.
"""
import sys, math, time, threading
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from std_msgs.msg import Empty, String
from ament_index_python.packages import get_package_share_directory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cell_fk import Chain
from cell_layout import (HOME, M1PRO_JOINTS, PRO600_JOINTS, NEST_YELLOW, NEST_BLUE, SHELF_Z,
                         BELT_XYZ, BELT_A, BELT_B, BELT_C, NEST_SEAT_Z, WAFER_THICKNESS, WAFER_GAP,
                         GRASP_LINKS)
from solve_home_poses import solve

FORK_AX = {0: (1, 0, 0), 2: (0, 0, 1)}      # blade flat, pointing +X (enters both nests along +X)
CUP_AX = {2: (0, 0, -1)}                     # cup pointing straight down
APPROACH = 0.09                              # tine tips 20 mm outside a nest's open chord
CLEAR = 0.045                                # lift above a nest rim before travelling


class Sequencer(Node):
    def __init__(self):
        super().__init__('cell_sequencer')
        self.declare_parameter('belt_speed', 0.07)    # m/s, from the video (~6 s for ~0.4 m)
        self.declare_parameter('dwell_b', 0.0)        # s at point B; none seen in the video
        self.declare_parameter('speed_scale', 1.0)    # >1 slows every arm move
        self.declare_parameter('cycles', 1)
        self.state_pub = self.create_publisher(String, '/cell/state', 10)
        self.grasp = {f'{c}/{op}': self.create_publisher(Empty, f'/wafer/{c}/{op}', 10)
                      for c in GRASP_LINKS for op in ('attach', 'detach')}
        self.grasp_state = {}
        for c in GRASP_LINKS:
            self.create_subscription(String, f'/wafer/{c}/state',
                                     lambda m, c=c: self.grasp_state.__setitem__(c, m.data), 10)
        self.arms = {
            'm1pro': ActionClient(self, FollowJointTrajectory, '/m1pro_arm_controller/follow_joint_trajectory'),
            'pro600': ActionClient(self, FollowJointTrajectory, '/pro600_arm_controller/follow_joint_trajectory'),
            'belt': ActionClient(self, FollowJointTrajectory, '/belt_controller/follow_joint_trajectory'),
        }
        share = Path(get_package_share_directory('wafer_cell_bringup'))
        self.chain = Chain(str(share / 'urdf' / 'cell.urdf'))
        self.plan()

    # ------------------------------------------------------------ IK plan
    def ik(self, arm, target, axes, seed):
        joints, link = ((M1PRO_JOINTS, 'm1pro_fork_seat') if arm == 'm1pro'
                        else (PRO600_JOINTS, 'pro600_cup_tip'))
        q, err, margin = solve(self.chain, joints, link, target, axes, seed=seed)
        if err > 0.004:
            self.get_logger().error(f'IK {arm} -> {tuple(round(v, 3) for v in target)}: '
                                    f'{err * 1e3:.1f} mm off, limit margin {margin:.2f}')
        return [q[j] for j in joints]

    def plan(self):
        yx, yy = NEST_YELLOW[0], NEST_YELLOW[1]
        bx, by = NEST_BLUE[0], NEST_BLUE[1]
        belt_y = BELT_XYZ[1]
        w_bot_yellow = SHELF_Z[2]                         # wafer underside on the top shelf
        w_bot_nest = NEST_SEAT_Z                          # wafer underside on the belt nest ledge
        z_pick = w_bot_yellow - WAFER_GAP                 # blade top 1 mm under the wafer
        z_carry = w_bot_yellow + CLEAR
        z_place = w_bot_nest - WAFER_GAP + 0.0005         # wafer 0.5 mm above the ledge when detached
        z_free = w_bot_nest - 0.010                       # blade clear under the wafer after detach
        w_top_nest = w_bot_nest + WAFER_THICKNESS
        w_top_blue = SHELF_Z[2] + WAFER_THICKNESS

        m = {}
        s = [HOME[j] for j in M1PRO_JOINTS]
        s = m['approach'] = self.ik('m1pro', (yx - APPROACH, yy, z_pick), FORK_AX, s)
        s = m['insert'] = self.ik('m1pro', (yx, yy, z_pick), FORK_AX, s)
        s = m['lift'] = self.ik('m1pro', (yx, yy, z_carry), FORK_AX, s)
        s = m['to_belt'] = self.ik('m1pro', (BELT_A - APPROACH, belt_y, z_place + CLEAR), FORK_AX, s)
        s = m['belt_approach'] = self.ik('m1pro', (BELT_A - APPROACH, belt_y, z_place), FORK_AX, s)
        s = m['belt_insert'] = self.ik('m1pro', (BELT_A, belt_y, z_place), FORK_AX, s)
        s = m['belt_lower'] = self.ik('m1pro', (BELT_A, belt_y, z_free), FORK_AX, s)
        s = m['belt_retreat'] = self.ik('m1pro', (BELT_A - APPROACH, belt_y, z_free), FORK_AX, s)
        m['home'] = [HOME[j] for j in M1PRO_JOINTS]
        self.m1 = m

        p = {}
        s = [HOME[j] for j in PRO600_JOINTS]
        s = p['above_c'] = self.ik('pro600', (BELT_C, belt_y, w_top_nest + 0.12), CUP_AX, s)
        s = p['pick'] = self.ik('pro600', (BELT_C, belt_y, w_top_nest + WAFER_GAP), CUP_AX, s)
        s = p['lift'] = self.ik('pro600', (BELT_C, belt_y, w_top_nest + 0.12), CUP_AX, s)
        s = p['above_blue'] = self.ik('pro600', (bx, by, w_top_blue + 0.12), CUP_AX, s)
        s = p['place'] = self.ik('pro600', (bx, by, w_top_blue + WAFER_GAP + 0.0005), CUP_AX, s)
        s = p['up'] = self.ik('pro600', (bx, by, w_top_blue + 0.12), CUP_AX, s)
        p['home'] = [HOME[j] for j in PRO600_JOINTS]
        self.p6 = p
        self.get_logger().info('IK plan ready')

    # ------------------------------------------------------------ primitives
    def say(self, step):
        self.state_pub.publish(String(data=step))
        self.get_logger().info(f'>> {step}')

    def move(self, arm, positions, seconds):
        joints = {'m1pro': M1PRO_JOINTS, 'pro600': PRO600_JOINTS, 'belt': ['belt_travel']}[arm]
        seconds *= float(self.get_parameter('speed_scale').value) if arm != 'belt' else 1.0
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = JointTrajectory()
        goal.trajectory.joint_names = joints
        pt = JointTrajectoryPoint()
        pt.positions = [float(v) for v in positions]
        pt.velocities = [0.0] * len(joints)
        pt.time_from_start = Duration(sec=int(seconds), nanosec=int((seconds % 1.0) * 1e9))
        goal.trajectory.points = [pt]
        client = self.arms[arm]
        client.wait_for_server()
        gh = client.send_goal_async(goal)
        while not gh.done():
            time.sleep(0.02)
        handle = gh.result()
        if not handle.accepted:
            raise RuntimeError(f'{arm}: goal rejected')
        res = handle.get_result_async()
        while not res.done():
            time.sleep(0.02)
        code = res.result().result.error_code
        if code != 0:
            raise RuntimeError(f'{arm}: trajectory failed with error_code {code}')

    def grab(self, carrier, attach=True, settle=0.4):
        op = 'attach' if attach else 'detach'
        self.grasp[f'{carrier}/{op}'].publish(Empty())
        time.sleep(settle)
        got = self.grasp_state.get(carrier, '?')
        self.get_logger().info(f'   {carrier} {op}: plugin reports "{got}"')

    def belt(self, x_from, x_to):
        v = float(self.get_parameter('belt_speed').value)
        self.move('belt', [x_to], abs(x_to - x_from) / v)

    def release_all(self):
        """gz-sim 8.11's DetachableJoint attaches on start, so every carrier
        holds the wafer until told otherwise. Detach all three, repeatedly,
        until each plugin reports 'detached' (or it was never attached)."""
        self.say('RELEASE_ALL')
        for _ in range(4):
            for c in GRASP_LINKS:
                self.grasp[f'{c}/detach'].publish(Empty())
            time.sleep(0.4)
            if all(self.grasp_state.get(c) == 'detached' for c in GRASP_LINKS):
                break
        self.get_logger().info(f'   carrier states: {self.grasp_state}')

    # ------------------------------------------------------------ the cycle
    def cycle(self):
        m, p = self.m1, self.p6
        dwell = float(self.get_parameter('dwell_b').value)
        self.say('M1_APPROACH_YELLOW');   self.move('m1pro', m['approach'], 3.0)
        self.say('M1_INSERT_UNDER_WAFER');self.move('m1pro', m['insert'], 2.0)
        self.say('FORK_ATTACH');          self.grab('fork', True)
        self.say('M1_LIFT');              self.move('m1pro', m['lift'], 1.0)
        self.say('M1_TO_BELT');           self.move('m1pro', m['to_belt'], 3.0)
        self.say('M1_LOWER_TO_NEST');     self.move('m1pro', m['belt_approach'], 1.0)
        self.say('M1_INSERT_INTO_NEST');  self.move('m1pro', m['belt_insert'], 2.0)
        self.say('FORK_DETACH');          self.grab('fork', False)
        self.say('M1_DROP_BLADE');        self.move('m1pro', m['belt_lower'], 0.8)
        self.say('M1_RETREAT');           self.move('m1pro', m['belt_retreat'], 1.5)
        self.say('NEST_ATTACH');          self.grab('nest', True)
        self.say('M1_HOME');              self.move('m1pro', m['home'], 3.0)
        self.say('BELT_A_TO_B');          self.belt(BELT_A, BELT_B)
        if dwell > 0:
            self.say('BELT_DWELL_B');     time.sleep(dwell)
        self.say('BELT_B_TO_C');          self.belt(BELT_B, BELT_C)
        self.say('NEST_DETACH');          self.grab('nest', False)
        self.say('P6_ABOVE_C');           self.move('pro600', p['above_c'], 3.0)
        self.say('P6_DESCEND');           self.move('pro600', p['pick'], 2.0)
        self.say('CUP_ATTACH');           self.grab('cup', True)
        self.say('P6_LIFT');              self.move('pro600', p['lift'], 1.5)
        self.say('P6_TO_BLUE');           self.move('pro600', p['above_blue'], 3.0)
        self.say('P6_PLACE');             self.move('pro600', p['place'], 2.0)
        self.say('CUP_DETACH');           self.grab('cup', False)
        self.say('P6_UP');                self.move('pro600', p['up'], 1.5)
        self.say('P6_HOME');              self.move('pro600', p['home'], 3.0)
        self.say('BELT_RETURN_A');        self.belt(BELT_C, BELT_A)
        self.say('CYCLE_DONE')


def main():
    dry = '--dry-run' in sys.argv          # plan only: IK every waypoint, print, exit
    rclpy.init(args=[a for a in sys.argv if a != '--dry-run'])
    node = Sequencer()
    if dry:
        for arm, plan in (('m1pro', node.m1), ('pro600', node.p6)):
            for name, q in plan.items():
                print(f'{arm:7s} {name:14s} ' + ' '.join(f'{v:+.3f}' for v in q))
        rclpy.shutdown()
        return
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    spin = threading.Thread(target=ex.spin, daemon=True)
    spin.start()
    try:
        node.release_all()
        for i in range(int(node.get_parameter('cycles').value)):
            node.get_logger().info(f'=== cycle {i + 1} ===')
            t0 = time.time()
            node.cycle()
            node.get_logger().info(f'=== cycle {i + 1} done in {time.time() - t0:.1f} s wall ===')
    except KeyboardInterrupt:
        pass
    finally:
        ex.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
