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
from cell_layout import M1PRO_JOINTS, PRO600_JOINTS, GRASP_LINKS
from cell_plan import STEPS, build_waypoints


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
    def plan(self):
        self.m1, self.p6 = build_waypoints(self.chain, log=self.get_logger().error)
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
        """Walk cell_plan.STEPS: one table for the sequencer, the fake devices
        and the shadow comparison."""
        dwell = float(self.get_parameter('dwell_b').value)
        for name, kind, payload, dur in STEPS:
            self.say(name)
            if kind == 'm1pro':
                self.move('m1pro', self.m1[payload], dur)
            elif kind == 'pro600':
                self.move('pro600', self.p6[payload], dur)
            elif kind == 'belt':
                self.belt(*payload)
            elif kind == 'dwell':
                if dwell > 0:
                    time.sleep(dwell)
            elif kind == 'grasp':
                self.grab(payload[0], payload[1], settle=dur)



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
