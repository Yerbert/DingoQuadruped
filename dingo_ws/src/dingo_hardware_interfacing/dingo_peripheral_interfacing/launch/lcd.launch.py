from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='dingo_peripheral_interfacing', executable='dingo_lcd_interfacing.py',
             name='dingo_LCD_node', output='screen'),
    ])
