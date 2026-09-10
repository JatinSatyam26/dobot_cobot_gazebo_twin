#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Digital Shadow bring-up: three device bridges + the driver that makes the
(already running) Gazebo cell follow them.

    ros2 launch wafer_cell_shadow shadow.launch.py                 # fake devices
    ros2 launch wafer_cell_shadow shadow.launch.py source:=real    # real devices (config/shadow.yaml)
    ros2 launch wafer_cell_shadow shadow.launch.py record:=true    # also bag every /shadow/* topic
    ros2 launch wafer_cell_shadow shadow.launch.py bridges:=false  # driver only, e.g. under `ros2 bag play`
    ros2 launch wafer_cell_shadow shadow.launch.py level1:=true fake_plc:=true      # Level 1 against the fake PLC
    ros2 launch wafer_cell_shadow shadow.launch.py level1:=true plc_ip:=192.168.10.10 plc_port:=502   # bench

level1:=true runs plc_bridge.py (Modbus, read-only) + task_shadow.py and none
of the time-replay fakes; fake_plc.py is the Modbus server stand-in for the
Micro850, run under the shadow venv's pymodbus.

Start cell.launch.py first. The fake devices share one epoch (fake_t0, a few
seconds from now) so they stay in step.
"""
import os
import time
from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    cfg = PathJoinSubstitution([FindPackageShare('wafer_cell_shadow'), 'config', 'shadow.yaml'])
    source = LaunchConfiguration('source')
    t0 = str(time.time() + 6.0)
    common = [cfg, {'source': source, 'fake_t0': float(t0),
                    'fake_dwell_b': LaunchConfiguration('dwell_b'),
                    'fake_belt_speed': LaunchConfiguration('belt_speed'),
                    'fake_cycles': LaunchConfiguration('cycles')}]
    level1 = LaunchConfiguration('level1')
    venv_py = os.path.expanduser('~/venvs/wafer_shadow/bin/python')
    fake_plc = os.path.join(get_package_prefix('wafer_cell_shadow'), 'lib', 'wafer_cell_shadow', 'fake_plc.py')
    # plc_ip left empty resolves to the fake PLC on this machine when fake_plc:=true, else the bench PLC
    plc_ip = PythonExpression(["'127.0.0.1' if '", LaunchConfiguration('plc_ip'), "' == '' and '",
                               LaunchConfiguration('fake_plc'), "' == 'true' else ('192.168.10.10' if '",
                               LaunchConfiguration('plc_ip'), "' == '' else '", LaunchConfiguration('plc_ip'), "')"])
    plc_params = [cfg, {'source': 'real', 'ip': plc_ip, 'port': LaunchConfiguration('plc_port')}]
    return LaunchDescription([
        DeclareLaunchArgument('source', default_value='fake', description='fake | real'),
        DeclareLaunchArgument('level1', default_value='false',
                              description='Modbus PLC reader + task_shadow instead of the time-replay fakes'),
        DeclareLaunchArgument('fake_plc', default_value='false', description='also start fake_plc.py on plc_port'),
        DeclareLaunchArgument('plc_ip', default_value='', description='empty: 127.0.0.1 with fake_plc:=true, else 192.168.10.10'),
        DeclareLaunchArgument('plc_port', default_value='502'),
        DeclareLaunchArgument('fake_cycles_plc', default_value='0', description='fake_plc.py cycles, 0 = endless'),
        DeclareLaunchArgument('bridges', default_value='true'),
        DeclareLaunchArgument('record', default_value='false'),
        DeclareLaunchArgument('dwell_b', default_value='0.0'),
        DeclareLaunchArgument('belt_speed', default_value='0.07'),
        DeclareLaunchArgument('cycles', default_value='1', description='fake devices: cycles to replay, 0 = loop'),
        # Level 1 stack - after every DeclareLaunchArgument, since launch resolves in list order
        ExecuteProcess(cmd=[venv_py if os.path.exists(venv_py) else 'python3', fake_plc,
                            '--port', LaunchConfiguration('plc_port'),
                            '--cycles', LaunchConfiguration('fake_cycles_plc')],
                       output='screen', condition=IfCondition(LaunchConfiguration('fake_plc'))),
        Node(package='wafer_cell_shadow', executable='plc_bridge.py', output='screen',
             parameters=plc_params, condition=IfCondition(level1)),
        Node(package='wafer_cell_shadow', executable='task_shadow.py', output='screen',
             parameters=[cfg, {'belt_speed': LaunchConfiguration('belt_speed')}], condition=IfCondition(level1)),
        Node(package='wafer_cell_shadow', executable='m1pro_bridge.py', output='screen',
             parameters=common, condition=IfCondition(PythonExpression(
                 ["'", LaunchConfiguration('bridges'), "' == 'true' and '", level1, "' != 'true'"]))),
        Node(package='wafer_cell_shadow', executable='pro600_bridge.py', output='screen',
             parameters=common, condition=IfCondition(PythonExpression(
                 ["'", LaunchConfiguration('bridges'), "' == 'true' and '", level1, "' != 'true'"]))),
        Node(package='wafer_cell_shadow', executable='plc_bridge.py', output='screen',
             parameters=common, condition=IfCondition(PythonExpression(
                 ["'", LaunchConfiguration('bridges'), "' == 'true' and '", level1, "' != 'true'"]))),
        Node(package='wafer_cell_shadow', executable='shadow_driver.py', output='screen',
             parameters=[cfg, {'belt_speed': LaunchConfiguration('belt_speed')}], condition=UnlessCondition(level1)),
        ExecuteProcess(cmd=['ros2', 'bag', 'record', '-o', 'shadow_bag',
                            '/shadow/m1pro/joint_states', '/shadow/pro600/joint_states',
                            '/shadow/plc/state', '/shadow/plc/phase', '/shadow/plc/step', '/shadow/plc/belt_run',
                            '/shadow/plc/vacuum_on', '/shadow/plc/blow', '/shadow/plc/belt_reverse',
                            '/shadow/m1pro/raw', '/shadow/pro600/raw', '/shadow/plc/raw'],
                       output='screen', condition=IfCondition(LaunchConfiguration('record'))),
    ])
