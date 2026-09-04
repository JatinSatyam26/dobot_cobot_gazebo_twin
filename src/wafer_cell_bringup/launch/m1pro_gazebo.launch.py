#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Phase 1 bringup: spawn the Dobot M1 Pro placeholder alone in Gazebo Harmonic
and bring up ros2_control so its joints can be commanded.

    ros2 launch wafer_cell_bringup m1pro_gazebo.launch.py

This is the pipeline-validation launch (spawn -> controllers -> joint motion).
It deliberately loads only one robot; the two-robot cell comes later.
"""

from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# Top surface of the workbench in wafer_cell.sdf. Keep in sync with that file.
BENCH_TOP = 0.75

# APPROX placement: M1 Pro at the left-hand end of the bench, mirroring the
# lab photos. The Pro 600 will go at +0.55 on the same bench.
M1PRO_XY = (-0.55, 0.0)


def generate_launch_description():
    desc_pkg = FindPackageShare('dobot_m1pro_description')
    bringup_pkg = FindPackageShare('wafer_cell_bringup')

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    controllers_file = PathJoinSubstitution(
        [desc_pkg, 'config', 'm1pro_controllers.yaml']
    )

    declare_world = DeclareLaunchArgument(
        'world',
        default_value=PathJoinSubstitution(
            [bringup_pkg, 'worlds', 'wafer_cell.sdf']
        ),
        description='Absolute path to the SDF world to load.',
    )
    declare_gui = DeclareLaunchArgument(
        'gui',
        default_value='true',
        description='Run the Gazebo GUI. Set false for headless CI runs.',
    )
    declare_rviz = DeclareLaunchArgument(
        'rviz', default_value='false', description='Also start RViz2.'
    )

    # -- robot_description ---------------------------------------------------
    # ParameterValue(..., value_type=str) is mandatory: without it launch tries
    # to YAML-parse the URDF and dies on the first colon.
    robot_description = ParameterValue(Command([
        'xacro ',
        PathJoinSubstitution([desc_pkg, 'urdf', 'dobot_m1pro.urdf.xacro']),
        ' prefix:=m1pro_',
        ' controllers_file:=', controllers_file,
    ]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    # Gazebo resolves package:// mesh URIs by searching GZ_SIM_RESOURCE_PATH for
    # a directory matching the package name, so the path must point at the
    # SHARE ROOT (install/*/share), not at the package dir itself. Without this
    # the robot spawns with no visual geometry at all.
    gz_resource_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        PathJoinSubstitution([desc_pkg, '..']),
    )

    # -- Gazebo --------------------------------------------------------------
    # -r starts the world unpaused; -s is server-only (headless).
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution(
                [FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py']
            )
        ]),
        launch_arguments={
            'gz_args': [
                PythonExpression(
                    ["'-r -v 3 ' if '", gui, "' == 'true' else '-r -s -v 3 '"]
                ),
                world,
            ],
            'on_exit_shutdown': 'true',
        }.items(),
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-topic', 'robot_description',
            '-name', 'dobot_m1pro',
            '-x', str(M1PRO_XY[0]),
            '-y', str(M1PRO_XY[1]),
            '-z', str(BENCH_TOP),
            '-Y', '0.0',
        ],
    )

    # /clock bridge so every ROS node shares Gazebo's simulated time.
    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
    )

    # -- controllers ---------------------------------------------------------
    # gz_ros2_control runs its controller_manager INSIDE the gz sim process, so
    # the CM service exists long before the sim is responsive. With the default
    # 10 s timeout the spawner's load_controller call times out mid-flight, the
    # spawner retries, and the second attempt hits "Controller already loaded"
    # followed by "Failed to configure controller". Generous timeouts plus a
    # settling delay after spawn make startup deterministic.
    CM_ARGS = [
        '--controller-manager', '/m1pro_controller_manager',
        '--controller-manager-timeout', '60',
        '--service-call-timeout', '60',
        '--switch-timeout', '60',
    ]

    jsb_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=['joint_state_broadcaster'] + CM_ARGS,
    )

    arm_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=['m1pro_arm_controller'] + CM_ARGS,
    )

    # Let the sim settle before touching the controller_manager.
    after_spawn = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_robot,
            on_exit=[TimerAction(period=5.0, actions=[jsb_spawner])],
        )
    )
    after_jsb = RegisterEventHandler(
        OnProcessExit(target_action=jsb_spawner, on_exit=[arm_spawner])
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
        arguments=['-d', PathJoinSubstitution(
            [desc_pkg, 'rviz', 'm1pro.rviz'])],
        parameters=[{'use_sim_time': True}],
    )

    return LaunchDescription([
        gz_resource_path,
        declare_world,
        declare_gui,
        declare_rviz,
        gz_sim,
        robot_state_publisher,
        clock_bridge,
        spawn_robot,
        after_spawn,
        after_jsb,
        rviz,
    ])
