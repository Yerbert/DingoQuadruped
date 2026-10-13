import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def gazebo_model_path(description_share):
    """GAZEBO_MODEL_PATH that lets Gazebo find its own models and the meshes of the URDF.

    The URDF names its meshes package://dingo_description/meshes/..., which Gazebo reads as
    model://dingo_description/meshes/... and looks up as <path>/dingo_description/meshes/... in every entry of the
    model path, so the "share" directory of the install space has to be one of them. Gazebo only falls back to its
    own models while the variable is empty, so those are listed explicitly.
    """
    paths = [p for p in os.environ.get('GAZEBO_MODEL_PATH', '').split(os.pathsep) if p]
    for default in ('/usr/share/gazebo-11/models', os.path.expanduser('~/.gazebo/models')):
        if os.path.isdir(default) and default not in paths:
            paths.append(default)
    share_root = os.path.dirname(description_share)
    if share_root not in paths:
        paths.append(share_root)
    return os.pathsep.join(paths)


def generate_launch_description():
    gazebo_share = get_package_share_directory('dingo_gazebo')
    description_share = get_package_share_directory('dingo_description')
    gazebo_ros_share = get_package_share_directory('gazebo_ros')

    robot = LaunchConfiguration('robot')
    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    verbose = LaunchConfiguration('verbose')
    robot_description = ParameterValue(Command([FindExecutable(name='xacro'), ' ', robot]), value_type=str)

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(gazebo_ros_share, 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world, 'gui': gui, 'verbose': verbose}.items())

    robot_state_publisher = Node(
        package='robot_state_publisher', executable='robot_state_publisher', name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description, 'publish_frequency': 10.0, 'use_sim_time': True}])

    spawn_robot = Node(
        package='gazebo_ros', executable='spawn_entity.py', name='spawn_urdf', output='screen',
        arguments=['-topic', 'robot_description', '-entity', 'dingo_gazebo', '-z', '3'])

    joint_state_broadcaster = Node(
        package='controller_manager', executable='spawner', output='screen',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'])

    position_controller = Node(
        package='controller_manager', executable='spawner', output='screen',
        arguments=['joint_group_position_controller', '--controller-manager', '/controller_manager'])

    return LaunchDescription([
        SetEnvironmentVariable('GAZEBO_MODEL_PATH', gazebo_model_path(description_share)),
        DeclareLaunchArgument('robot', default_value=os.path.join(description_share, 'urdf', 'dingo.urdf')),
        DeclareLaunchArgument('world', default_value=os.path.join(gazebo_share, 'launch', 'world', 'normal.world')),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('verbose', default_value='false'),
        gazebo,
        robot_state_publisher,
        spawn_robot,
        # the controllers can only be loaded once the robot (and with it controller_manager) exists
        RegisterEventHandler(OnProcessExit(target_action=spawn_robot, on_exit=[joint_state_broadcaster])),
        RegisterEventHandler(OnProcessExit(target_action=joint_state_broadcaster, on_exit=[position_controller])),
    ])
