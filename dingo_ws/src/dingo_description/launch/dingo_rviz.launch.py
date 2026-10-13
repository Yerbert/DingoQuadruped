import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory('dingo_description')
    robot = LaunchConfiguration('robot')
    robot_description = ParameterValue(Command([FindExecutable(name='xacro'), ' ', robot]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('robot', default_value=os.path.join(share, 'urdf', 'dingo.urdf')),
        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui',
             name='joint_state_publisher_gui'),
        Node(package='robot_state_publisher', executable='robot_state_publisher', name='robot_state_publisher',
             parameters=[{'robot_description': robot_description, 'publish_frequency': 1000.0}]),
        Node(package='rviz2', executable='rviz2', name='rviz2', output='screen',
             arguments=['-d', os.path.join(share, 'rviz', 'dingo.rviz')]),
    ])
