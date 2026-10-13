"""
Per-robot configuration file that is particular to each individual robot, not just the type of robot.
"""

PS4_COLOR = {"red": 0, "blue": 0, "green": 255}
PS4_DEACTIVATED_COLOR = {"red": 0, "blue": 0, "green": 50}
# sensor_msgs/Joy layouts understood by InputInterface (select with the "joy_layout" parameter of dingo_driver).
#   legacy          - layout the code was written for: PS4 pad through the ROS 1 joy_node. Keyboard.py emulates it.
#   game_controller - ros-humble-joy game_controller_node (SDL2 standard mapping, d-pad reported as buttons).
# The d-pad is reported as "left/up positive" like the legacy axes 6 and 7.
# Axis signs of game_controller are assumed to match legacy; check with `ros2 topic echo /joy` on the real pad.
JOY_LAYOUTS = {
    "legacy": {
        "buttons": {"trot": 5, "hop": 0, "joystick": 4},        # R1, cross, L1
        "axes": {"lx": 0, "ly": 1, "rx": 3, "ry": 4},
        "dpad_axes": {"x": 6, "y": 7},
    },
    "game_controller": {
        "buttons": {"trot": 10, "hop": 0, "joystick": 9},       # RIGHTSHOULDER, A (cross), LEFTSHOULDER
        "axes": {"lx": 0, "ly": 1, "rx": 2, "ry": 3},
        "dpad_buttons": {"up": 11, "down": 12, "left": 13, "right": 14},
    },
}
