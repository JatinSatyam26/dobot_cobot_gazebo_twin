#!/usr/bin/env python3
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

# Wafer spawns on the yellow tower's TOP shelf (owner's instruction). The
# numbers live in scripts/cell_layout.py (installed to lib/<pkg>), the same
# file the generator and check_extents use.
import os, sys
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


def spawner(name):
    return Node(package='controller_manager', executable='spawner',
                output='screen', arguments=[name] + CM)


def generate_launch_description():
    bringup = FindPackageShare('wafer_cell_bringup')
    m1_pkg = FindPackageShare('dobot_m1pro_description')
    p6_pkg = FindPackageShare('mycobot_pro600_description')

    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world')

    # cat, not xacro: cell.urdf is generated and already expanded.
    # ParameterValue(..., str) is mandatory or launch YAML-parses the URDF.
    robot_description = ParameterValue(
        Command(['cat ', PathJoinSubstitution([bringup, 'urdf', 'cell.urdf'])]),
        value_type=str)

    spawn_cell = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-topic', 'robot_description', '-name', 'wafer_cell',
                   '-x', '0', '-y', '0', '-z', '0'])

    spawn_wafer = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-file', PathJoinSubstitution([bringup, 'models', 'wafer.sdf']),
                   '-name', 'wafer',
                   '-x', WAFER_POSE[0], '-y', WAFER_POSE[1], '-z', WAFER_POSE[2]])

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('verbose', default_value='3',
                              description='gz sim -v level; 4 shows plugin debug (DetachableJoint etc.)'),
        DeclareLaunchArgument('world', default_value=PathJoinSubstitution(
            [bringup, 'worlds', 'wafer_cell.sdf'])),

        # package:// mesh URIs resolve by scanning GZ_SIM_RESOURCE_PATH for a
        # directory named after the package — so these are the SHARE ROOTS.
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([bringup, '..'])),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([m1_pkg, '..'])),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  PathJoinSubstitution([p6_pkg, '..'])),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([PathJoinSubstitution(
                [FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'])]),
            launch_arguments={
                'gz_args': [PythonExpression(
                    ["'-r -v ' if '", gui, "' == 'true' else '-r -s -v '"]),
                    LaunchConfiguration('verbose'), ' ', world],
                'on_exit_shutdown': 'true'}.items()),

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
                spawner('m1pro_arm_controller'),
                spawner('pro600_arm_controller'),
                spawner('belt_controller')])])),

        # Drive to home once the controllers exist. Without this the arms sag
        # during the spawn->controller window and joint_trajectory_controller
        # latches the sagged pose on activation and holds it forever.
        RegisterEventHandler(OnProcessExit(
            target_action=spawn_cell,
            on_exit=[TimerAction(period=7.0, actions=[
                Node(package='wafer_cell_bringup', executable='go_home.py',
                     output='screen')])])),

        # inspection camera -> ROS, so the build can be checked headlessly
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             name='cam_bridge', output='screen',
             arguments=['/cell_cam@sensor_msgs/msg/Image[gz.msgs.Image',
                        '/plan_cam@sensor_msgs/msg/Image[gz.msgs.Image']),

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
