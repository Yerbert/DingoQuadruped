import logging
import numpy as np
from dingo_control.State import BehaviorState, State
from dingo_control.Command import Command
from dingo_utilities.Utilities import deadband, clipped_first_order_filter
from dingo_input_interfacing.HardwareConfig import JOY_LAYOUTS

logger = logging.getLogger(__name__)


class InputInterface:
    """Turns sensor_msgs/Joy messages into robot Commands.

    It does not subscribe to anything itself: the owning node subscribes to "joy" and passes every message
    to input_callback (in ROS 1 this class created its own rospy.Subscriber).
    """

    def __init__(self, config, layout="legacy"):
        if layout not in JOY_LAYOUTS:
            raise ValueError(f"Unknown joy layout '{layout}', expected one of {sorted(JOY_LAYOUTS)}")
        self.layout = JOY_LAYOUTS[layout]
        self.layout_name = layout
        self._min_buttons, self._min_axes = self._required_sizes(self.layout)
        self._warned_short_message = False

        self.config = config
        self.previous_gait_toggle = 0
        self.previous_state = BehaviorState.REST
        self.previous_hop_toggle = 0
        self.previous_joystick_toggle = 0

        self.rounding_dp = 2

        self.hop_event = 0
        self.trot_event = 0
        self.joystick_control_event = 0

        self.current_command = Command()
        self.new_command = Command()
        self.developing_command = Command()

    @staticmethod
    def _required_sizes(layout):
        """Smallest number of buttons and axes a Joy message needs to hold for this layout."""
        button_indices = list(layout["buttons"].values()) + list(layout.get("dpad_buttons", {}).values())
        axis_indices = list(layout["axes"].values()) + list(layout.get("dpad_axes", {}).values())
        return max(button_indices) + 1, max(axis_indices) + 1

    def _dpad(self, msg):
        """D-pad as (x, y), left and up positive, whichever way the layout reports it."""
        if "dpad_axes" in self.layout:
            return msg.axes[self.layout["dpad_axes"]["x"]], msg.axes[self.layout["dpad_axes"]["y"]]
        pad = self.layout["dpad_buttons"]
        return (msg.buttons[pad["left"]] - msg.buttons[pad["right"]],
                msg.buttons[pad["up"]] - msg.buttons[pad["down"]])

    def input_callback(self, msg):
        # A pad with fewer inputs than the layout expects would raise IndexError inside the ROS callback.
        if len(msg.buttons) < self._min_buttons or len(msg.axes) < self._min_axes:
            if not self._warned_short_message:
                logger.warning(
                    "Joy message has %d buttons and %d axes but layout '%s' needs at least %d and %d: "
                    "ignoring it (check the joy_layout parameter)",
                    len(msg.buttons), len(msg.axes), self.layout_name, self._min_buttons, self._min_axes)
                self._warned_short_message = True
            return

        buttons = self.layout["buttons"]
        axes = self.layout["axes"]
        self.developing_command = Command()
        ####### Handle discrete commands ########
        # Check if requesting a state transition to trotting, or from trotting to resting
        gait_toggle = msg.buttons[buttons["trot"]] #R1
        if self.trot_event != 1:
            self.trot_event = (gait_toggle == 1 and self.previous_gait_toggle == 0)

        # Check if requesting a state transition to hopping, from trotting or resting
        hop_toggle = msg.buttons[buttons["hop"]] #x
        if self.hop_event != 1:
            self.hop_event = (hop_toggle == 1 and self.previous_hop_toggle == 0)            
        
        joystick_toggle = msg.buttons[buttons["joystick"]] #L1
        if self.joystick_control_event != 1:
            self.joystick_control_event = (joystick_toggle == 1 and self.previous_joystick_toggle == 0)

        # Update previous values for toggles and state
        self.previous_gait_toggle = gait_toggle
        self.previous_hop_toggle = hop_toggle
        self.previous_joystick_toggle = joystick_toggle

        ####### Handle continuous commands ########
        dpad_x, dpad_y = self._dpad(msg)
        x_vel = (-1*msg.axes[axes["ly"]] ) * self.config.max_x_velocity #ly
        y_vel = msg.axes[axes["lx"]] * self.config.max_y_velocity #lx
        self.developing_command.horizontal_velocity =  np.round(np.array([x_vel, y_vel]),self.rounding_dp)
        self.developing_command.yaw_rate = np.round(msg.axes[axes["rx"]],self.rounding_dp) * self.config.max_yaw_rate #rx

        self.developing_command.pitch = np.round(msg.axes[axes["ry"]],self.rounding_dp) * self.config.max_pitch #ry
        self.developing_command.height_movement = np.round(dpad_y,self.rounding_dp) #dpady
        self.developing_command.roll_movement = -np.round(dpad_x,self.rounding_dp) #dpadx

        self.new_command = self.developing_command
        
    def get_command(self, state, message_rate):

        self.current_command = self.new_command

        self.current_command.trot_event = self.trot_event
        self.current_command.hop_event  = self.hop_event
        self.current_command.joystick_control_event = self.joystick_control_event
        self.hop_event = 0
        self.trot_event = 0
        self.joystick_control_event = 0

        message_dt = 1.0 / message_rate

        deadbanded_pitch = deadband(
            self.current_command.pitch, self.config.pitch_deadband
        )
        pitch_rate = clipped_first_order_filter(
            state.pitch,
            deadbanded_pitch,
            self.config.max_pitch_rate,
            self.config.pitch_time_constant,
        )
        self.current_command.pitch  = np.clip(state.pitch + message_dt * pitch_rate, -0.35,0.35)
        self.current_command.height = np.clip(state.height - message_dt * self.config.z_speed * self.current_command.height_movement,-0.27,-0.08)
        self.current_command.roll   = np.clip(state.roll + message_dt * self.config.roll_speed * self.current_command.roll_movement, -0.3,0.3)

        return self.current_command
    
