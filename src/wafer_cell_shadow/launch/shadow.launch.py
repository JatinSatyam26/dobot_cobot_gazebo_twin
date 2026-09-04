#!/usr/bin/env python3
"""
Digital Shadow bring-up: three device bridges + the driver that makes the
(already running) Gazebo cell follow them.

    ros2 launch wafer_cell_shadow shadow.launch.py                 # fake devices
    ros2 launch wafer_cell_shadow shadow.launch.py source:=real    # real devices (config/shadow.yaml)
    ros2 launch wafer_cell_shadow shadow.launch.py record:=true    # also bag every /shadow/* topic
    ros2 launch wafer_cell_shadow shadow.launch.py bridges:=false  # driver only, e.g. under `ros2 bag play`

Start cell.launch.py first. The fake devices share one epoch (fake_t0, a few
seconds from now) so they stay in step.
"""
import time
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    cfg = PathJoinSubstitution([FindPackageShare('wafer_cell_shadow'), 'config', 'shadow.yaml'])
    source = LaunchConfiguration('source')
    t0 = str(time.time() + 6.0)
    common = [cfg, {'source': source, 'fake_t0': float(t0),
                    'fake_dwell_b': LaunchConfiguration('dwell_b'),
                    'fake_belt_speed': LaunchConfiguration('belt_speed')}]
    return LaunchDescription([
        DeclareLaunchArgument('source', default_value='fake', description='fake | real'),
        DeclareLaunchArgument('bridges', default_value='true'),
        DeclareLaunchArgument('record', default_value='false'),
        DeclareLaunchArgument('dwell_b', default_value='0.0'),
        DeclareLaunchArgument('belt_speed', default_value='0.07'),
        Node(package='wafer_cell_shadow', executable='m1pro_bridge.py', output='screen',
             parameters=common, condition=IfCondition(LaunchConfiguration('bridges'))),
        Node(package='wafer_cell_shadow', executable='pro600_bridge.py', output='screen',
             parameters=common, condition=IfCondition(LaunchConfiguration('bridges'))),
        Node(package='wafer_cell_shadow', executable='plc_bridge.py', output='screen',
             parameters=common, condition=IfCondition(LaunchConfiguration('bridges'))),
        Node(package='wafer_cell_shadow', executable='shadow_driver.py', output='screen',
             parameters=[cfg, {'belt_speed': LaunchConfiguration('belt_speed')}]),
        ExecuteProcess(cmd=['ros2', 'bag', 'record', '-o', 'shadow_bag',
                            '/shadow/m1pro/joint_states', '/shadow/pro600/joint_states',
                            '/shadow/plc/state', '/shadow/plc/belt_run', '/shadow/plc/vacuum_on', '/shadow/plc/belt_reverse',
                            '/shadow/m1pro/raw', '/shadow/pro600/raw', '/shadow/plc/raw'],
                       output='screen', condition=IfCondition(LaunchConfiguration('record'))),
    ])
