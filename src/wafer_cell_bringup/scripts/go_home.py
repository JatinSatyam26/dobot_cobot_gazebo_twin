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
import rclpy
from builtin_interfaces.msg import Duration
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

HOME = {
    '/m1pro_arm_controller/joint_trajectory': (
        ['m1pro_z_lift', 'm1pro_shoulder', 'm1pro_elbow', 'm1pro_wrist'],
        [0.120, -0.4000, 2.1400, -0.6358]),
    '/pro600_arm_controller/joint_trajectory': (
        [f'pro600_joint{i}' for i in range(1, 7)],
        [0.2161, -0.4382, 2.1570, -0.1480, -1.5708, 0.0209]),
    '/belt_controller/joint_trajectory': (
        ['belt_travel'], [-0.25]),          # Point A
}


class GoHome(Node):
    def __init__(self):
        super().__init__('go_home')
        self.pubs = {t: self.create_publisher(JointTrajectory, t, 10)
                     for t in HOME}
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
        self.get_logger().info('home pose commanded to all three controllers')
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
