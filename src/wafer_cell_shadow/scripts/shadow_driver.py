#!/usr/bin/env python3
"""
Shadow driver: makes the Gazebo cell follow what the bridges publish.

    ros2 run wafer_cell_shadow shadow_driver.py

Inputs (from the bridges, or from a replayed bag of them)
  /shadow/m1pro/joint_states, /shadow/pro600/joint_states   -> arm controllers
  /shadow/plc/belt_run                                       -> belt position, dead-reckoned
  /shadow/plc/state                                          -> wafer attach/detach events
Outputs
  <ctrl>/joint_trajectory  short (1/rate s) trajectories to the existing JTCs
  /wafer/<carrier>/attach|detach                             std_msgs/Empty
  /cell/state                                                the step name, republished

The belt has NO sensor in the real cell, so its position here is
belt_speed x (time the PLC has held belt_run high), reset at every stop. That
is the honest limit of this shadow, not a shortcut.
"""
import time
import rclpy
import rclpy.executors
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String, Bool, Empty
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from rclpy.qos import QoSProfile, DurabilityPolicy

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
from shadow_common import M1PRO_JOINTS, PRO600_JOINTS, BELT_A
from cell_layout import BELT_XYZ, NEST_SEAT_Z, WAFER_THICKNESS
from wafer_seat import seat_wafer

GRASP_EVENTS = {'FORK_ATTACH': ('fork', True), 'FORK_DETACH': ('fork', False),
                'NEST_HOLD': ('nest', True), 'NEST_DROP': ('nest', False),
                'NEST_ATTACH': ('nest', True), 'NEST_DETACH': ('nest', False),
                'CUP_ATTACH': ('cup', True), 'CUP_DETACH': ('cup', False),
                'NEST_SEAT': 'seat',   # stand-in: place the wafer on the seat (wafer_seat.py)
                'RELEASE_ALL': None}


class ShadowDriver(Node):
    def __init__(self):
        super().__init__('shadow_driver')
        self.declare_parameter('rate_hz', 10.0)
        self.declare_parameter('belt_speed', 0.07)
        self.declare_parameter('belt_direction', 1.0)     # +1: A->C on belt_run; -1 reversed
        # The sim arm trails the real (or fake) one by about one trajectory
        # horizon plus latency. A grasp event fired the moment the real robot
        # arrives would attach/release while the sim fork is still short of
        # the pose, so grasp events are applied after this delay.
        self.declare_parameter('event_delay', 0.35)
        self.rate = float(self.get_parameter('rate_hz').value)
        self.q = {'m1pro': None, 'pro600': None}
        self.belt_x, self.belt_run, self.belt_t, self.belt_rev = BELT_A, False, None, False
        self.create_subscription(JointState, '/shadow/m1pro/joint_states', lambda m: self.on_js('m1pro', m), 10)
        self.create_subscription(JointState, '/shadow/pro600/joint_states', lambda m: self.on_js('pro600', m), 10)
        self.create_subscription(Bool, '/shadow/plc/belt_run', self.on_belt, 10)
        self.create_subscription(Bool, '/shadow/plc/belt_reverse', lambda m: setattr(self, 'belt_rev', m.data), 10)
        self.create_subscription(String, '/shadow/plc/state', self.on_state, LATCHED)
        self.traj = {a: self.create_publisher(JointTrajectory, f'/{a}_arm_controller/joint_trajectory', 10)
                     for a in ('m1pro', 'pro600')}
        self.traj['belt'] = self.create_publisher(JointTrajectory, '/belt_controller/joint_trajectory', 10)
        self.grasp = {f'{c}/{op}': self.create_publisher(Empty, f'/wafer/{c}/{op}', 10)
                      for c in ('fork', 'cup', 'nest') for op in ('attach', 'detach')}
        self.state_pub = self.create_publisher(String, '/cell/state', LATCHED)
        self.create_timer(1.0 / self.rate, self.tick)
        self.get_logger().info('shadow driver up: waiting for /shadow/* topics')

    def on_js(self, arm, m):
        names = M1PRO_JOINTS if arm == 'm1pro' else PRO600_JOINTS
        pos = dict(zip(m.name, m.position))
        if all(j in pos for j in names):
            self.q[arm] = [pos[j] for j in names]

    def on_belt(self, m):
        now = time.time()
        if m.data and not self.belt_run:
            self.belt_t = now                              # rising edge: start integrating
        elif self.belt_run and self.belt_t is not None:
            sign = float(self.get_parameter('belt_direction').value) * (-1.0 if self.belt_rev else 1.0)
            self.belt_x += sign * float(self.get_parameter('belt_speed').value) * (now - self.belt_t)
            self.belt_t = now
        self.belt_run = m.data

    def on_state(self, m):
        self.state_pub.publish(m)
        ev = GRASP_EVENTS.get(m.data, 'none')
        if ev != 'none':
            delay = float(self.get_parameter('event_delay').value)
            timer = None

            def fire():
                if ev is None:
                    for c in ('fork', 'cup', 'nest'):
                        self.grasp[f'{c}/detach'].publish(Empty())
                elif ev == 'seat':
                    seat_wafer(BELT_A, BELT_XYZ[1], NEST_SEAT_Z + WAFER_THICKNESS / 2 + 0.0003)  # 0.3 mm above the seat: placed touching, it sank 0.3 mm into the contact
                else:
                    carrier, attach = ev
                    self.grasp[f"{carrier}/{'attach' if attach else 'detach'}"].publish(Empty())
                timer.cancel()
            timer = self.create_timer(max(delay, 0.01), fire)
        if m.data == 'CYCLE_DONE':
            self.belt_x = BELT_A                           # the return has ended; cancel dead-reckoning drift

    def send(self, arm, names, positions):
        t = JointTrajectory()
        t.joint_names = names
        pt = JointTrajectoryPoint()
        pt.positions = [float(v) for v in positions]
        pt.velocities = [0.0] * len(names)
        pt.time_from_start = Duration(nanosec=int(1e9 / self.rate))
        t.points = [pt]
        self.traj[arm].publish(t)

    def tick(self):
        if self.q['m1pro'] is not None:
            self.send('m1pro', M1PRO_JOINTS, self.q['m1pro'])
        if self.q['pro600'] is not None:
            self.send('pro600', PRO600_JOINTS, self.q['pro600'])
        if self.belt_run and self.belt_t is not None:
            self.on_belt(Bool(data=True))                  # keep integrating between messages
        self.belt_x = max(-0.30, min(0.30, self.belt_x))
        self.send('belt', ['belt_travel'], [self.belt_x])


def main():
    rclpy.init()
    n = ShadowDriver()
    try:
        rclpy.spin(n)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
