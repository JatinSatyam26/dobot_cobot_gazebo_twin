#!/usr/bin/env python3
"""
Phase 1 proof-of-life: drive every M1 Pro joint through a short trajectory.

    ros2 run wafer_cell_bringup m1pro_wiggle.py

If the arm moves in Gazebo, the whole pipeline is validated:
xacro -> robot_description -> spawn -> gz_ros2_control -> JointTrajectoryController.
"""

import rclpy
from builtin_interfaces.msg import Duration
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

# Chain order, NOT Dobot's J-numbering:
#   z_lift = Dobot J3 (vertical carriage, range 0.02 - 0.23 m)
#   shoulder = J1, elbow = J2, wrist = J4
JOINTS = ['m1pro_z_lift', 'm1pro_shoulder', 'm1pro_elbow', 'm1pro_wrist']

# (seconds_from_start, [z_lift, shoulder, elbow, wrist])
# z_lift is absolute carriage height on the column: 0.02 = bottom, 0.23 = top.
WAYPOINTS = [
    (3.0,  [0.02,  0.0,   0.0,   0.0]),
    (6.0,  [0.23,  0.0,   0.0,   0.0]),   # ride the carriage to the top
    (9.0,  [0.23,  0.8,  -0.9,   0.0]),   # fold the arm
    (12.0, [0.23,  0.8,  -0.9,   1.57]),  # rotate the tool
    (15.0, [0.02,  0.8,  -0.9,   1.57]),  # descend to pick height
    (19.0, [0.02, -0.8,   0.9,   0.0]),   # swing to the other side
    (23.0, [0.02,  0.0,   0.0,   0.0]),   # home
]


class Wiggle(Node):
    def __init__(self):
        super().__init__('m1pro_wiggle')
        self.pub = self.create_publisher(
            JointTrajectory, '/m1pro_arm_controller/joint_trajectory', 10
        )
        # Give the controller a moment to finish activating and to see us.
        self.timer = self.create_timer(1.0, self.send_once)

    def send_once(self):
        if self.pub.get_subscription_count() == 0:
            self.get_logger().info(
                'waiting for m1pro_arm_controller to subscribe...'
            )
            return
        self.timer.cancel()

        traj = JointTrajectory()
        traj.joint_names = JOINTS
        for secs, positions in WAYPOINTS:
            pt = JointTrajectoryPoint()
            pt.positions = [float(p) for p in positions]
            pt.velocities = [0.0] * len(JOINTS)
            pt.time_from_start = Duration(
                sec=int(secs), nanosec=int((secs % 1.0) * 1e9)
            )
            traj.points.append(pt)

        self.pub.publish(traj)
        self.get_logger().info(
            f'published {len(traj.points)}-point trajectory '
            f'({WAYPOINTS[-1][0]:.0f} s). Watch Gazebo.'
        )


def main():
    rclpy.init()
    node = Wiggle()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
