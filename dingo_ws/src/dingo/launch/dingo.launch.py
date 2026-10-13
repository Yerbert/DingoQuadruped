from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from dingo.board_config import BLINKA_BOARD, BLINKA_CHIP


def generate_launch_description():
    # Boolean arguments take true/false (ROS 1 used 1/0).
    is_sim = LaunchConfiguration('is_sim')
    is_physical = LaunchConfiguration('is_physical')
    use_joystick = LaunchConfiguration('use_joystick')
    use_keyboard = LaunchConfiguration('use_keyboard')
    use_imu = LaunchConfiguration('use_imu')
    serial_port = LaunchConfiguration('serial_port')
    joy_layout = LaunchConfiguration('joy_layout')
    joy_executable = LaunchConfiguration('joy_executable')

    physical_nodes = GroupAction(
        condition=IfCondition(is_physical),
        actions=[
            # Reads the frames of the Arduino Nano (replaces rosserial_python)
            Node(package='dingo_peripheral_interfacing', executable='arduino_bridge', name='dingo_arduino_bridge',
                 output='screen', parameters=[{'serial_port': serial_port}]),
            # LCD screen
            Node(package='dingo_peripheral_interfacing', executable='dingo_lcd_interfacing.py',
                 name='dingo_LCD_node', output='screen'),
        ])

    joystick = GroupAction(
        condition=IfCondition(use_joystick),
        actions=[
            # joy_node publishes the layout of the manufacturer, game_controller_node the SDL standard layout;
            # choose joy_layout accordingly (legacy / game_controller)
            Node(package='joy', executable=joy_executable, name='JOYSTICK',
                 parameters=[{'autorepeat_rate': 30.0}]),
        ])

    keyboard = GroupAction(
        condition=IfCondition(use_keyboard),
        actions=[
            Node(package='dingo_input_interfacing', executable='Keyboard.py', name='keyboard_input_listener',
                 output='screen'),
        ])

    driver = Node(
        package='dingo', executable='dingo_driver', name='dingo', output='screen',
        parameters=[{
            'is_sim': ParameterValue(is_sim, value_type=bool),
            'is_physical': ParameterValue(is_physical, value_type=bool),
            'use_imu': ParameterValue(use_imu, value_type=bool),
            'joy_layout': joy_layout,
        }])

    return LaunchDescription([
        DeclareLaunchArgument('is_sim', default_value='false'),
        DeclareLaunchArgument('is_physical', default_value='true'),
        DeclareLaunchArgument('use_joystick', default_value='true'),
        DeclareLaunchArgument('use_keyboard', default_value='false'),
        # The Nano is connected with its USB cable, which shows up as /dev/ttyUSB0 (CH340 or FTDI chip) or
        # /dev/ttyACM0. The pins 8/10 used on the Raspberry Pi are the debug console UART2 on the ELTAY BB CM4; a wired
        # connection would use UART7 (header pins 15/16), for example /dev/ttyS7.
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('use_imu', default_value='false'),
        DeclareLaunchArgument('joy_layout', default_value='legacy'),
        DeclareLaunchArgument('joy_executable', default_value='joy_node'),

        # Adafruit Blinka (PCA9685, BNO055) must be told which board it runs on; values already set in the
        # environment (for example by the Docker image) win.
        SetEnvironmentVariable('BLINKA_FORCEBOARD', EnvironmentVariable('BLINKA_FORCEBOARD', default_value=BLINKA_BOARD)),
        SetEnvironmentVariable('BLINKA_FORCECHIP', EnvironmentVariable('BLINKA_FORCECHIP', default_value=BLINKA_CHIP)),

        physical_nodes,
        joystick,
        keyboard,
        driver,
    ])
