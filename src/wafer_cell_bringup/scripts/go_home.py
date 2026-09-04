#!/usr/bin/env python3
"""
Drive every joint to its home pose once the controllers are live.

WHY THIS IS NEEDED
------------------
gz_ros2_control only creates the controller_manager when the model spawns, so
there is an unavoidable window where the arms exist in the world with NO
controller holding them. Dobot's own SolidWorks masses are light (base 1.65 kg,
links 0.34-0.38 kg, because the export omits motors and castings), so the arms
sag quickly under gravity.

Then the trap: joint_trajectory_controller HOLDS THE CURRENT POSITION when it
activates. So the arm droops, the controller latches wherever it landed, and
holds that forever. Every measurement stays correct — link lengths, joint
limits, mesh scale, base placement — while the pose on screen is nonsense, and
it differs run to run because the sag is not deterministic.

Shortening the window reduces the droop; this command removes it.
"""
import time
import rclpy
from builtin_interfaces.msg import Duration
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cell_layout import HOME as _H, M1PRO_JOINTS, PRO600_JOINTS, BELT_A, GRASP_LINKS
from std_msgs.msg import Empty

# One source of truth: scripts/cell_layout.py (same values the generator
# writes into cell.urdf as initial_value, so "home" and "spawn" agree).
HOME = {
    '/m1pro_arm_controller/joint_trajectory':  (M1PRO_JOINTS,  [_H[j] for j in M1PRO_JOINTS]),
    '/pro600_arm_controller/joint_trajectory': (PRO600_JOINTS, [_H[j] for j in PRO600_JOINTS]),
    '/belt_controller/joint_trajectory':       (['belt_travel'], [BELT_A]),   # Point A
}


class GoHome(Node):
    def __init__(self):
        super().__init__('go_home')
        self.pubs = {t: self.create_publisher(JointTrajectory, t, 10)
                     for t in HOME}
        # gz-sim 8.11's DetachableJoint ATTACHES ON START (attachRequested
        # defaults true): the moment the wafer spawns, fork, cup and belt nest
        # all weld it where it lies and every later attach is "Already
        # attached". Release all three so the cell starts with a free wafer.
        self.release = [self.create_publisher(Empty, f'/wafer/{c}/detach', 10)
                        for c in GRASP_LINKS]
        self.sent = False
        self.tries = 0
        self.create_timer(1.0, self.tick)

    def tick(self):
        self.tries += 1
        waiting = [t for t, p in self.pubs.items()
                   if p.get_subscription_count() == 0]
        if waiting and self.tries < 40:
            self.get_logger().info(f'waiting for controllers: {waiting}')
            return
        for topic, (joints, pos) in HOME.items():
            traj = JointTrajectory()
            traj.joint_names = joints
            pt = JointTrajectoryPoint()
            pt.positions = [float(v) for v in pos]
            pt.velocities = [0.0] * len(joints)
            pt.time_from_start = Duration(sec=3)
            traj.points.append(pt)
            self.pubs[topic].publish(traj)
        for _ in range(3):
            for pub in self.release:
                pub.publish(Empty())
            time.sleep(0.3)
        self.get_logger().info('home pose commanded to all three controllers; wafer released from all carriers')
        raise SystemExit(0)


def main():
    rclpy.init()
    n = GoHome()
    try:
        rclpy.spin(n)
    except SystemExit:
        pass


if __name__ == '__main__':
    main()
