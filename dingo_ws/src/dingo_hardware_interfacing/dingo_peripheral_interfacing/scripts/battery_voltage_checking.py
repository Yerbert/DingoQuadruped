#!/usr/bin/env python3
import subprocess
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, Float64

from dingo_peripheral_interfacing.gpio_lines import GpioLines


class BatteryMonitor(Node):
    MESSAGE_RATE = 50  # Hz

    def __init__(self):
        super().__init__("battery_monitor")

        # GPIO pins by Rockchip name (see dingo_peripheral_interfacing.gpio_lines). The defaults sit on the same
        # 40-pin header positions the Dingo PCB used on the Raspberry Pi (BCM 5, 6, 13, 19 = header pins 29, 31,
        # 33, 35), which on the ELTAY BB CM4 are GPIO4_A5, GPIO3_D4, GPIO3_D7 and GPIO3_D0.
        self.declare_parameter("gpio_chip", "gpiochip0")  # only used for pins given as plain line offsets
        self.declare_parameter("estop_pin", "GPIO4_A5")
        self.declare_parameter("battery_pins", ["GPIO3_D4", "GPIO3_D7", "GPIO3_D0"])  # most significant bit first

        self.estop_pin = self.get_parameter("estop_pin").value
        self.battery_pins = list(self.get_parameter("battery_pins").value)

        self.gpio = GpioLines(self.get_parameter("gpio_chip").value, consumer="dingo-battery-monitor")
        self.gpio.input(self.estop_pin)
        for pin in self.battery_pins:
            self.gpio.input(pin)

        self.battery_percentage_publisher = self.create_publisher(Float64, "/battery_percentage", 10)
        self.estop_publisher = self.create_publisher(Bool, "/emergency_stop_status", 10)

        self.current_estop_bit = 0
        self.number_of_low_battery_detections = 0
        # The e-stop state is also repeated once per second: a node that starts while the e-stop is already
        # pressed learns it within a second (in ROS 1 it never did, the state was only sent on changes).
        self.ticks_since_estop_publish = 0

        # Grab the initial value and publish it immediately
        if self.gpio.read(self.estop_pin) == 1:
            self.current_estop_bit = 1
        self._publish_estop()

        self.timer = self.create_timer(1.0 / self.MESSAGE_RATE, self.step)

    def step(self):
        estop_bit = self.gpio.read(self.estop_pin)
        battery_bits = [self.gpio.read(pin) for pin in self.battery_pins]

        if estop_bit == 1 and self.current_estop_bit == 0:
            self.current_estop_bit = 1
            self._publish_estop()

        if estop_bit == 0 and self.current_estop_bit == 1:
            self.current_estop_bit = 0
            self._publish_estop()

        self.ticks_since_estop_publish += 1
        if self.ticks_since_estop_publish >= self.MESSAGE_RATE:
            self._publish_estop()

        # Convert the bits to a decimal number: 0 -> 0.0, 1 -> 0.125 ... 6 -> 0.75, 7 -> 1.0
        num = int("".join(str(bit) for bit in battery_bits), 2)
        value = 1.0 if num == 7 else num * 0.125

        self.battery_percentage_publisher.publish(Float64(data=value))

        if value == 0.0:
            self.number_of_low_battery_detections += 1
            if self.number_of_low_battery_detections > 30:
                # self._shutdown()
                self.get_logger().warning("Would shut down if activated", throttle_duration_sec=5.0)
        elif self.number_of_low_battery_detections > 0:
            self.number_of_low_battery_detections -= 1

    def _publish_estop(self):
        self.ticks_since_estop_publish = 0
        self.estop_publisher.publish(Bool(data=bool(self.current_estop_bit)))

    def _shutdown(self):
        self.gpio.release()
        self.get_logger().warning("BATTERY VOLTAGE TOO LOW. COMMENCING SHUTDOWN PROCESS")
        time.sleep(5)
        subprocess.run(["sudo", "shutdown", "-h", "now"])

    def destroy_node(self):
        self.gpio.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryMonitor()
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
