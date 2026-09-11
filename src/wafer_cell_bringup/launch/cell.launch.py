#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
Full cell bringup — both arms, the belt carriage and the wafer.

    ros2 launch wafer_cell_bringup cell.launch.py

ONE robot_description, ONE controller_manager, three controllers. See
scripts/generate_cell_urdf.py for why: gz_ros2_control blocks in Configure()
waiting for robot_description on Gazebo's main thread, so multiple plugin
instances deadlock the sim and do not honour per-instance namespaces.

    /controller_manager   joint_state_broadcaster
                          m1pro_arm_controller     (4 joints)
                          pro600_arm_controller    (6 joints)
                          belt_controller          (1 prismatic)

urdf/cell.urdf is GENERATED. After editing a robot xacro or a cell pose:
    ros2 run wafer_cell_bringup generate_cell_urdf.py && colcon build
"""

from launch import LaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.actions import (
    AppendEnvironmentVariable, DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, SetLaunchConfiguration, Shutdown,
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

# Wafer spawns on the yellow tower's TOP shelf (owner's instruction). The
# numbers live in scripts/cell_layout.py (installed to lib/<pkg>), the same
# file the generator and check_extents use.
import os, sys
from pathlib import Path
from ament_index_python.packages import get_package_prefix
sys.path.insert(0, os.path.join(get_package_prefix('wafer_cell_bringup'),
                                'lib', 'wafer_cell_bringup'))
from cell_layout import WAFER_SPAWN, GRASP_LINKS

# Render on the RTX 4060 when its kernel module is loaded. Default GL on this
# laptop is the Intel iGPU (PRIME on-demand); the offload variables only work
# once /proc/driver/nvidia exists - with the module missing they break GL
# context creation (see CLAUDE.md traps).
if os.path.exists('/proc/driver/nvidia/version'):
    os.environ.setdefault('__NV_PRIME_RENDER_OFFLOAD', '1')
    os.environ.setdefault('__GLX_VENDOR_LIBRARY_NAME', 'nvidia')
WAFER_POSE = tuple(f'{v:.5f}' for v in WAFER_SPAWN)

CM = ['--controller-manager', '/controller_manager',
      '--controller-manager-timeout', '60',
      '--service-call-timeout', '60',
      '--switch-timeout', '60']


def spawner(name, condition=None):
    return Node(package='controller_manager', executable='spawner',
                output='screen', arguments=[name] + CM, condition=condition)


def world_with_step(context):
    """step:=0.002 writes a temporary copy of the world with that physics step.
    The committed world keeps the 1 ms step the owner approved the cycle at.
    2 ms halves the physics cost (RTF 0.98 headless, 2026-09-04) but is NOT
    equivalent: the final place ended 2.1 / 1.3 mm off centre. Demos only."""
    import re, tempfile
    from launch.substitutions import LaunchConfiguration as LC
    step = LC('step').perform(context); world = LC('world').perform(context)
    if abs(float(step) - 0.001) < 1e-9:
        return [SetLaunchConfiguration('world_file', world)]
    text = Path(world).read_text()
    text, n = re.subn(r'<max_step_size>[^<]+</max_step_size>', f'<max_step_size>{float(step):g}</max_step_size>', text, count=1)
    assert n == 1, 'max_step_size not found in the world'
    tmp = Path(tempfile.gettempdir()) / f'wafer_cell_step{float(step):g}.sdf'
    tmp.write_text(text)
    return [SetLaunchConfiguration('world_file', str(tmp))]


def generate_launch_description():
    bringup = FindPackageShare('wafer_cell_bringup')
    m1_pkg = FindPackageShare('dobot_m1pro_description')
    p6_pkg = FindPackageShare('mycobot_pro600_description')

    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world_file')   # set by world_with_step()

    # cat, not xacro: cell.urdf is generated and already expanded.
    # ParameterValue(..., str) is mandatory or launch YAML-parses the URDF.
    robot_description = ParameterValue(
        Command(['cat ', PathJoinSubstitution([bringup, 'urdf', 'cell.urdf'])]),
        value_type=str)

    spawn_cell = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-topic', 'robot_description', '-name', 'wafer_cell',
                   '-x', '0', '-y', '0', '-z', '0'])

    telemetry = LaunchConfiguration('telemetry')
    # in telemetry mode go_home only releases the wafer's start-up welds; the arms hold
    # their spawn pose (the URDF initial values = HOME) until the joint stream arrives
    go_home = Node(package='wafer_cell_bringup', executable='go_home.py', output='screen',
                   arguments=[PythonExpression(["'--release-only' if '", telemetry, "' == 'true' else '--full'"])])

    spawn_wafer = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-file', PathJoinSubstitution([bringup, 'models', 'wafer.sdf']),
                   '-name', 'wafer',
                   '-x', WAFER_POSE[0], '-y', WAFER_POSE[1], '-z', WAFER_POSE[2]])

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('gui_nvidia', default_value='true',
                              description='render the GUI window on the NVIDIA card too (false: GUI on the '
                                          'Intel iGPU, server on NVIDIA; measured RTF 0.95 vs 0.86)'),
        DeclareLaunchArgument('cameras', default_value='true',
                              description='bridge the six camera sensors (they render only while bridged; '
                                          'false for a lighter GUI demo)'),
        DeclareLaunchArgument('demo', default_value='false',
                              description='run cell_sequencer.py automatically once the arms are home'),
        DeclareLaunchArgument('demo_cycles', default_value='1'),
        DeclareLaunchArgument('telemetry', default_value='false',
                              description='true: the arms follow /<robot>_position_controller/commands (joint telemetry) '
                                          'instead of running the cycle; everything else is a static prop'),
        DeclareLaunchArgument('verbose', default_value='3',
                              description='gz sim -v level; 4 shows plugin debug (DetachableJoint etc.)'),
        DeclareLaunchArgument('world', default_value=PathJoinSubstitution(
            [bringup, 'worlds', 'wafer_cell.sdf'])),
        DeclareLaunchArgument('step', default_value='0.001',
                              description='physics step in s; 0.002 runs a GUI demo at real time but is not '
                                          'equivalent (final place 2 mm off); verification stays at 0.001'),
        OpaqueFunction(function=world_with_step),

        # package:// mesh URIs resolve by scanning GZ_SIM_RESOURCE_PATH for a
        # directory named after the package — so these are the SHARE ROOTS.
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([bringup, '..'])),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([m1_pkg, '..'])),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([p6_pkg, '..'])),

        # The SERVER always runs headless (sensors render on the NVIDIA card via
        # the PRIME variables set above). The GUI is a separate process so it can
        # take a different GPU, and closing its window shuts the launch down
        # (a single 'gz sim -r' used to leave the server and bridges alive).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([PathJoinSubstitution(
                [FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'])]),
            launch_arguments={
                'gz_args': ['-r -s -v ', LaunchConfiguration('verbose'), ' ', world],
                'on_exit_shutdown': 'true'}.items()),
        ExecuteProcess(
            cmd=['gz', 'sim', '-g'], output='screen', on_exit=[Shutdown()],
            condition=IfCondition(PythonExpression(
                ["'", gui, "' == 'true' and '", LaunchConfiguration('gui_nvidia'), "' == 'true'"]))),
        ExecuteProcess(
            cmd=['bash', '-c', 'unset __NV_PRIME_RENDER_OFFLOAD __GLX_VENDOR_LIBRARY_NAME; exec gz sim -g'],
            output='screen', on_exit=[Shutdown()],
            condition=IfCondition(PythonExpression(
                ["'", gui, "' == 'true' and '", LaunchConfiguration('gui_nvidia'), "' != 'true'"]))),

        Node(package='robot_state_publisher', executable='robot_state_publisher',
             output='screen',
             parameters=[{'robot_description': robot_description,
                          'use_sim_time': True}]),

        Node(package='ros_gz_bridge', executable='parameter_bridge', output='screen',
             arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock']),

        TimerAction(period=3.0, actions=[spawn_cell]),
        TimerAction(period=6.0, actions=[spawn_wafer]),

        RegisterEventHandler(OnProcessExit(
            target_action=spawn_cell,
            on_exit=[TimerAction(period=1.5,
                                 actions=[spawner('joint_state_broadcaster')])])),
        RegisterEventHandler(OnProcessExit(
            target_action=spawn_cell,
            on_exit=[TimerAction(period=2.5, actions=[
                # telemetry:=true swaps the arms' trajectory controllers for forward
                # position controllers that follow a joint stream (tools/replay_telemetry.py,
                # later the live bridges); the belt keeps its controller and stays put.
                spawner('m1pro_arm_controller', UnlessCondition(telemetry)),
                spawner('pro600_arm_controller', UnlessCondition(telemetry)),
                spawner('m1pro_position_controller', IfCondition(telemetry)),
                spawner('pro600_position_controller', IfCondition(telemetry)),
                spawner('belt_controller')])])),

        # Drive to home once the controllers exist. Without this the arms sag
        # during the spawn->controller window and joint_trajectory_controller
        # latches the sagged pose on activation and holds it forever.
        RegisterEventHandler(OnProcessExit(
            target_action=spawn_cell,
            on_exit=[TimerAction(period=7.0, actions=[go_home])])),

        # demo:=true - one command shows the whole cycle: the sequencer starts
        # 8 s after go_home has commanded the rest poses.
        RegisterEventHandler(OnProcessExit(
            target_action=go_home,
            on_exit=[TimerAction(period=8.0, actions=[
                Node(package='wafer_cell_bringup', executable='cell_sequencer.py',
                     output='screen', condition=IfCondition(LaunchConfiguration('demo')),
                     parameters=[{'cycles': ParameterValue(LaunchConfiguration('demo_cycles'),
                                                           value_type=int)}])])])),

        # inspection camera -> ROS, so the build can be checked headlessly
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             name='cam_bridge', output='screen', condition=IfCondition(LaunchConfiguration('cameras')),
             arguments=['/cell_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/plan_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/detail_blue_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/detail_belt_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/detail_yellow_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/detail_beltc_cam@sensor_msgs/msg/Image[gz.msgs.Image']),

        # grasp: ROS std_msgs/Empty -> gz attach/detach of the wafer
        # (DetachableJoint plugins emitted by generate_cell_urdf.py), and the
        # plugin's "attached"/"detached" state back to ROS as std_msgs/String.
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             name='grasp_bridge', output='screen',
             arguments=[f'/wafer/{c}/{op}@std_msgs/msg/Empty]gz.msgs.Empty'
                        for c in GRASP_LINKS for op in ('attach', 'detach')]
                       + [f'/wafer/{c}/state@std_msgs/msg/String[gz.msgs.StringMsg'
                          for c in GRASP_LINKS]),
    ])
