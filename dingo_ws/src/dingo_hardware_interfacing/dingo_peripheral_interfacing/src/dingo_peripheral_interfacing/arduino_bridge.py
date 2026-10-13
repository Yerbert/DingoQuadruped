"""Bridge between the Arduino Nano and ROS 2 (replaces rosserial_python).

The Nano (dingo_nano/dingo_arduino.ino) prints frames like  $DINGO,<estop>,<battery V>,<servo buck V>*<XOR>  to its
serial port. This node reads them and publishes
  /electrical_measurements  dingo_msgs/ElectricalMeasurements  every valid frame
  /emergency_stop_status    std_msgs/Bool                      every valid frame (the Nano sends one per second
                                                               and immediately when the e-stop state changes)
Lines starting with '#' are log messages of the Nano and are forwarded to the ROS log.
"""
import rclpy
import serial
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool

from dingo_msgs.msg import ElectricalMeasurements


def parse_frame(line):
    """Parse one frame. Returns (estopped: bool, battery_volts: float, servo_buck_volts: float).

    Raises ValueError for anything that is not a complete frame with a correct checksum.
    """
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        raise ValueError(f"not a frame: {line!r}")
    payload, _, checksum_text = line[1:].rpartition("*")
    checksum = 0
    for char in payload:
        checksum ^= ord(char)
    if len(checksum_text) != 2 or int(checksum_text, 16) != checksum:
        raise ValueError(f"bad checksum in {line!r}: expected {checksum:02X}")
    fields = payload.split(",")
    if len(fields) != 4 or fields[0] != "DINGO" or fields[1] not in ("0", "1"):
        raise ValueError(f"unexpected fields in {line!r}")
    return fields[1] == "1", float(fields[2]), float(fields[3])


class ArduinoBridge(Node):
    READ_RATE = 20  # Hz
    RECONNECT_PERIOD = 2.0  # seconds

    def __init__(self):
        super().__init__("arduino_bridge")
        # The Nano is connected with its USB cable: /dev/ttyUSB0 (CH340 or FTDI chip) or /dev/ttyACM0. Pi header pins
        # 8/10 (/dev/ttyS0 in ROS 1) are the debug console UART2 on the ELTAY BB CM4; a wired connection would use
        # UART7 (header pins 15 TX / 16 RX), whose device name depends on the OS image (for example /dev/ttyS7).
        # Opening a USB serial port resets the Nano, and its sketch waits 15 seconds before it starts sending.
        self.declare_parameter("serial_port", "/dev/ttyUSB0")
        self.declare_parameter("baud", 57600)

        self.serial_port = self.get_parameter("serial_port").value
        self.baud = self.get_parameter("baud").value

        self.electrical_publisher = self.create_publisher(ElectricalMeasurements, "/electrical_measurements", 10)
        self.estop_publisher = self.create_publisher(Bool, "/emergency_stop_status", 10)

        self.serial = None
        self.buffer = b""
        self.last_open_attempt = 0.0

        self.timer = self.create_timer(1.0 / self.READ_RATE, self.step)

    def _open(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.last_open_attempt < self.RECONNECT_PERIOD:
            return False
        self.last_open_attempt = now
        try:
            self.serial = serial.Serial(self.serial_port, self.baud, timeout=0)
        except (serial.SerialException, OSError) as error:
            self.get_logger().error(f"Cannot open {self.serial_port}: {error}", throttle_duration_sec=10.0)
            return False
        self.buffer = b""
        self.get_logger().info(f"Connected to the Arduino on {self.serial_port} at {self.baud} baud")
        return True

    def step(self):
        if self.serial is None and not self._open():
            return
        try:
            data = self.serial.read(self.serial.in_waiting or 1)
        except (serial.SerialException, OSError) as error:
            self.get_logger().error(f"Lost the serial connection: {error}")
            self.serial.close()
            self.serial = None
            return
        self.buffer += data
        while b"\n" in self.buffer:
            raw, _, self.buffer = self.buffer.partition(b"\n")
            self._handle_line(raw.decode("ascii", errors="replace"))
        if len(self.buffer) > 512:  # no newline for a long time: noise, start over
            self.buffer = b""

    def _handle_line(self, line):
        line = line.strip()
        if not line:
            return
        if line.startswith("#"):
            self.get_logger().warning(f"Arduino: {line[1:].strip()}")
            return
        try:
            estop, battery, buck = parse_frame(line)
        except ValueError as error:
            self.get_logger().warning(f"Ignoring a corrupted line from the Arduino ({error})",
                                      throttle_duration_sec=5.0)
            return

        self.electrical_publisher.publish(
            ElectricalMeasurements(battery_voltage_level=battery, servo_buck_voltage_level=buck))
        # Repeating the state with every frame lets nodes that start later (or miss a message) catch up.
        self.estop_publisher.publish(Bool(data=estop))

    def destroy_node(self):
        if self.serial is not None:
            self.serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ArduinoBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
