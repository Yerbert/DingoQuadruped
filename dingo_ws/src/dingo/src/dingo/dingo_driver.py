from enum import Enum
from math import degrees, radians

import numpy as np
import rclpy
from geometry_msgs.msg import Point
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool, Float64MultiArray

from dingo_control.Config import Configuration
from dingo_control.Controller import Controller
from dingo_control.Kinematics import four_legs_inverse_kinematics
from dingo_control.State import BehaviorState, State
from dingo_input_interfacing.InputInterface import InputInterface
from dingo_msgs.msg import Angle, JointSpace, TaskSpace

from dingo.board_config import configure_blinka


class Mode(Enum):
    """What the 50 Hz control loop is currently doing.

    ROS 1 expressed this with nested blocking while-loops; with rclpy the loop body must return
    on every tick, so the position inside those loops is kept in this variable instead.
    """
    ESTOPPED = 0   # e-stop pressed: nothing is commanded until it is released
    MANUAL = 1     # joystick/keyboard drives the robot, external commands are rejected
    EXTERNAL = 2   # robot holds REST, /joint_space_cmd and /task_space_cmd are accepted


class DingoDriver(Node):
    MESSAGE_RATE = 50  # Hz

    def __init__(self):
        super().__init__('dingo_driver')

        # Replace the positional roslaunch arguments "is_sim is_physical use_imu" of ROS 1.
        self.declare_parameter('is_sim', False)
        self.declare_parameter('is_physical', True)
        self.declare_parameter('use_imu', True)
        # Which sensor_msgs/Joy layout the gamepad uses, see dingo_input_interfacing.HardwareConfig.
        self.declare_parameter('joy_layout', 'legacy')
        # Gazebo command topic (single Float64MultiArray, 12 values, leg-major order FR FL RR RL).
        self.declare_parameter('sim_command_topic', '/joint_group_position_controller/commands')

        self.is_sim = self.get_parameter('is_sim').value
        self.is_physical = self.get_parameter('is_physical').value
        self.use_imu = self.get_parameter('use_imu').value

        self.mode = None
        self.external_commands_enabled = 0

        self.task_space_pub = self.create_publisher(TaskSpace, 'task_space_goals', 10)
        self.joint_space_pub = self.create_publisher(JointSpace, 'joint_space_goals', 10)

        if self.is_sim:
            self.sim_publisher = self.create_publisher(
                Float64MultiArray, self.get_parameter('sim_command_topic').value, 10)

        self.config = Configuration()

        if self.is_physical:
            from dingo_control.Config import Leg_linkage
            from dingo_servo_interfacing.HardwareInterface import HardwareInterface
            self.linkage = Leg_linkage(self.config)
            self.hardware_interface = HardwareInterface(self.linkage)
        if self.use_imu:
            from dingo_peripheral_interfacing.IMU import IMU
            self.imu = IMU()

        self.controller = Controller(
            self.config,
            four_legs_inverse_kinematics,
            logger=self.get_logger(),
        )
        self.state = State()

        self.get_logger().info("Creating input listener...")
        self.input_interface = InputInterface(
            self.config, layout=self.get_parameter('joy_layout').value)
        self.joy_sub = self.create_subscription(Joy, 'joy', self.input_interface.input_callback, 10)
        self.get_logger().info(
            "Input listener successfully initialised... Robot will now receive commands via Joy messages")

        self.joint_command_sub = self.create_subscription(
            JointSpace, '/joint_space_cmd', self.run_joint_space_command, 10)
        self.task_command_sub = self.create_subscription(
            TaskSpace, '/task_space_cmd', self.run_task_space_command, 10)
        self.estop_status_sub = self.create_subscription(
            Bool, '/emergency_stop_status', self.update_emergency_stop_status, 10)

        self.get_logger().info("Summary of current gait parameters:")
        self.get_logger().info(f"overlap time: {self.config.overlap_time:.2f}")
        self.get_logger().info(f"swing time: {self.config.swing_time:.2f}")
        self.get_logger().info(f"z clearance: {self.config.z_clearance:.2f}")
        self.get_logger().info(f"back leg x shift: {self.config.rear_leg_x_shift:.2f}")
        self.get_logger().info(f"front leg x shift: {self.config.front_leg_x_shift:.2f}")

        self.timer = self.create_timer(1.0 / self.MESSAGE_RATE, self.control_step)

    # ------------------------------------------------------------------ control loop

    def control_step(self):
        """One 50 Hz tick of what used to be DingoDriver.run() in ROS 1."""
        if self.state.currently_estopped == 1:
            if self.mode != Mode.ESTOPPED:
                self.get_logger().warning(
                    "E-stop pressed. Controlling code now disabled until E-stop is released")
                self.state.trotting_active = 0
                self.external_commands_enabled = 0
                self.mode = Mode.ESTOPPED
            return

        if self.mode is None or self.mode == Mode.ESTOPPED:
            if self.mode == Mode.ESTOPPED:
                self.get_logger().info("E-stop released")
            self._enter_manual()
        elif self.mode == Mode.MANUAL:
            self._manual_step()
        else:
            self._external_step()

    def _enter_manual(self):
        self.external_commands_enabled = 0
        self.get_logger().info("Manual robot control active. Currently not accepting external commands")
        self._send_rest_pose()
        self.mode = Mode.MANUAL

    def _enter_external(self):
        self.get_logger().info("Manual Control deactivated. Now accepting external commands")
        self._send_rest_pose()
        self.mode = Mode.EXTERNAL

    def _send_rest_pose(self):
        # Always start a new control mode with the robot standing still: send the default pose once.
        command = self.input_interface.get_command(self.state, self.MESSAGE_RATE)
        self.state.behavior_state = BehaviorState.REST
        self.controller.run(self.state, command)
        self._publish_goals()
        self._actuate(self.state.joint_angles)

    def _manual_step(self):
        command = self.input_interface.get_command(self.state, self.MESSAGE_RATE)
        if command.joystick_control_event == 1:
            self.external_commands_enabled = 1
            self._enter_external()
            return

        self.state.euler_orientation = (
            self.imu.read_orientation() if self.use_imu else np.array([0, 0, 0])
        )
        self.controller.run(self.state, command)

        if self.state.behavior_state in (BehaviorState.TROT, BehaviorState.REST):
            self._publish_goals()
            self._actuate(self.state.joint_angles)
        elif self.is_sim:
            self._publish_to_sim(self.state.joint_angles)

    def _external_step(self):
        command = self.input_interface.get_command(self.state, self.MESSAGE_RATE)
        if command.joystick_control_event == 1:
            self._enter_manual()

    # ------------------------------------------------------------------ outputs

    def _actuate(self, joint_angles):
        if self.is_sim:
            self._publish_to_sim(joint_angles)
        if self.is_physical:
            self.hardware_interface.set_actuator_postions(joint_angles)

    def _publish_to_sim(self, joint_angles):
        rows, cols = joint_angles.shape
        msg = Float64MultiArray()
        msg.data = [float(joint_angles[row, col]) for col in range(cols) for row in range(rows)]
        self.sim_publisher.publish(msg)

    def _publish_goals(self):
        """Publish the current foot positions and joint angles (moved here from Controller)."""
        stamp = self.get_clock().now().to_msg()
        rotated_foot_locations = self.state.rotated_foot_locations
        leg_origins = self.config.LEG_ORIGINS
        angle_matrix = self.state.joint_angles

        task_space_message = TaskSpace()
        task_space_message.header.stamp = stamp
        task_space_message.fr_foot = self._foot_point(rotated_foot_locations, leg_origins, 0)
        task_space_message.fl_foot = self._foot_point(rotated_foot_locations, leg_origins, 1)
        task_space_message.rr_foot = self._foot_point(rotated_foot_locations, leg_origins, 2)
        task_space_message.rl_foot = self._foot_point(rotated_foot_locations, leg_origins, 3)
        self.task_space_pub.publish(task_space_message)

        joint_space_message = JointSpace()
        joint_space_message.header.stamp = stamp
        joint_space_message.fr_foot = self._leg_angles(angle_matrix, 0)
        joint_space_message.fl_foot = self._leg_angles(angle_matrix, 1)
        joint_space_message.rr_foot = self._leg_angles(angle_matrix, 2)
        joint_space_message.rl_foot = self._leg_angles(angle_matrix, 3)
        self.joint_space_pub.publish(joint_space_message)

    @staticmethod
    def _foot_point(foot_locations, leg_origins, leg):
        x, y, z = foot_locations[:, leg] - leg_origins[:, leg]
        return Point(x=float(x), y=float(y), z=float(z))

    @staticmethod
    def _leg_angles(angle_matrix, leg):
        return Angle(
            theta1=degrees(angle_matrix[0, leg]),
            theta2=degrees(angle_matrix[1, leg]),
            theta3=degrees(angle_matrix[2, leg]),
        )

    # ------------------------------------------------------------------ subscriptions

    def update_emergency_stop_status(self, msg):
        self.state.currently_estopped = 1 if msg.data else 0

    def _external_commands_allowed(self):
        if self.external_commands_enabled == 1 and self.state.currently_estopped == 0:
            return True
        if self.external_commands_enabled == 0:
            self.get_logger().error(
                "ERROR: Robot not accepting commands. Please deactivate manual control before sending control commands",
                throttle_duration_sec=2.0)
        else:
            self.get_logger().error(
                "ERROR: Robot currently estopped. Please release before trying to send commands",
                throttle_duration_sec=2.0)
        return False

    def run_task_space_command(self, msg):
        """/task_space_cmd: foot positions (x, y, z per leg, order FR FL RR RL) -> inverse kinematics."""
        if not self._external_commands_allowed():
            return
        foot_locations = np.zeros((3, 4))
        for leg, foot in enumerate((msg.fr_foot, msg.fl_foot, msg.rr_foot, msg.rl_foot)):
            foot_locations[:, leg] = [foot.x, foot.y, foot.z]
        joint_angles = self.controller.inverse_kinematics(foot_locations, self.config)
        self._actuate(joint_angles)

    def run_joint_space_command(self, msg):
        """/joint_space_cmd: joint angles in degrees (same unit as joint_space_goals), order FR FL RR RL."""
        if not self._external_commands_allowed():
            return
        joint_angles = np.zeros((3, 4))
        for leg, angles in enumerate((msg.fr_foot, msg.fl_foot, msg.rr_foot, msg.rl_foot)):
            joint_angles[:, leg] = [radians(angles.theta1), radians(angles.theta2), radians(angles.theta3)]
        self._actuate(joint_angles)


def main(args=None):
    configure_blinka()  # before any module imports `board` (PCA9685 servo board, BNO055 IMU)
    rclpy.init(args=args)
    node = DingoDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
