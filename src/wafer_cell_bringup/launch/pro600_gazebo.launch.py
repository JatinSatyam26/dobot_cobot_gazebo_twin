#!/usr/bin/env python3
"""Spawn the myCobot Pro 600 alone in Gazebo Harmonic and bring up its
controllers. Mirrors m1pro_gazebo.launch.py; used to validate the Pro 600
import before both arms share a world."""

from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable, DeclareLaunchArgument,
    IncludeLaunchDescription, RegisterEventHandler, TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command, LaunchConfiguration, PathJoinSubstitution, PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

BENCH_TOP = 0.75
PRO600_XY = (0.55, 0.0)

# Same spawner hardening as the M1 Pro: gz_ros2_control's controller_manager
# lives inside the sim process and is slow to answer while the world loads.
CM_TIMEOUTS = ['--controller-manager-timeout', '60',
               '--service-call-timeout', '60',
               '--switch-timeout', '60']


def generate_launch_description():
    desc = FindPackageShare('mycobot_pro600_description')
    bringup = FindPackageShare('wafer_cell_bringup')
    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world')

    controllers = PathJoinSubstitution([desc, 'config', 'pro600_controllers.yaml'])

    robot_description = ParameterValue(Command([
        'xacro ',
        PathJoinSubstitution([desc, 'urdf', 'mycobot_pro600.urdf.xacro']),
        ' prefix:=pro600_',
        ' controllers_file:=', controllers,
    ]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('world', default_value=PathJoinSubstitution(
            [bringup, 'worlds', 'wafer_cell.sdf'])),

        # package:// mesh URIs resolve by searching for a dir matching the
        # package name, so this must point at install/*/share.
        AppendEnvironmentVariable(
            'GZ_SIM_RESOURCE_PATH', PathJoinSubstitution([desc, '..'])),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([PathJoinSubstitution(
                [FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'])]),
            launch_arguments={
                'gz_args': [PythonExpression(
                    ["'-r -v 3 ' if '", gui, "' == 'true' else '-r -s -v 3 '"]),
                    world],
                'on_exit_shutdown': 'true',
            }.items()),

        Node(package='robot_state_publisher', executable='robot_state_publisher',
             output='screen',
             parameters=[{'robot_description': robot_description,
                          'use_sim_time': True}]),

        Node(package='ros_gz_bridge', executable='parameter_bridge', output='screen',
             arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock']),

        (spawn := Node(package='ros_gz_sim', executable='create', output='screen',
                       arguments=['-topic', 'robot_description',
                                  '-name', 'mycobot_pro600',
                                  '-x', str(PRO600_XY[0]), '-y', str(PRO600_XY[1]),
                                  '-z', str(BENCH_TOP)])),

        RegisterEventHandler(OnProcessExit(
            target_action=spawn,
            on_exit=[TimerAction(period=5.0, actions=[
                (jsb := Node(package='controller_manager', executable='spawner',
                             output='screen',
                             arguments=['joint_state_broadcaster',
                                        '--controller-manager',
                                        '/pro600_controller_manager'] + CM_TIMEOUTS))])])),

        RegisterEventHandler(OnProcessExit(
            target_action=jsb,
            on_exit=[Node(package='controller_manager', executable='spawner',
                          output='screen',
                          arguments=['pro600_arm_controller',
                                     '--controller-manager',
                                     '/pro600_controller_manager'] + CM_TIMEOUTS)])),
    ])
