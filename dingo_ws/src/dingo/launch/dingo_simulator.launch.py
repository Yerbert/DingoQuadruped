import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    # Only starts the Gazebo simulation; run dingo.launch.py with is_sim:=true is_physical:=false to drive it.
    simulation = os.path.join(get_package_share_directory('dingo_gazebo'), 'launch', 'simulation.launch.py')
    return LaunchDescription([IncludeLaunchDescription(PythonLaunchDescriptionSource(simulation))])
