#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
import spidev as SPI
import LCD_1inch47
from PIL import Image, ImageDraw, ImageFont
import logging
import os
import socket
import time
from std_msgs.msg import Float64
from dingo_msgs.msg import ElectricalMeasurements


class DingoDisplayNode(Node):
    def __init__(self):
        super().__init__('dingo_display_node')
        # Display wiring. The defaults sit on the 40-pin header positions the Dingo PCB used on the Raspberry Pi:
        # RST BCM27 = pin 13 = GPIO4_A0, DC BCM25 = pin 22 = GPIO4_A4, BL BCM18 = pin 12 = GPIO3_C7. The SPI pins
        # (MOSI 19, MISO 21, CLK 23, CS0 24) are SPI3 on the ELTAY BB CM4, i.e. /dev/spidev3.0.
        self.declare_parameter('gpio_chip', 'gpiochip0')  # only used for pins given as plain line offsets
        self.declare_parameter('rst_pin', 'GPIO4_A0')
        self.declare_parameter('dc_pin', 'GPIO4_A4')
        self.declare_parameter('bl_pin', 'GPIO3_C7')
        self.declare_parameter('spi_bus', 3)
        self.declare_parameter('spi_device', 0)
        self.ssid = ''
        self.ipAddress = ''
        self.disp = LCD_1inch47.LCD_1inch47(
            rst=self.get_parameter('rst_pin').value,
            dc=self.get_parameter('dc_pin').value,
            bl=self.get_parameter('bl_pin').value,
            gpio_chip=self.get_parameter('gpio_chip').value,
            spi_bus=self.get_parameter('spi_bus').value,
            spi_device=self.get_parameter('spi_device').value,
        )
        # Initialize library.
        self.disp.Init()
        # Clear display.
        self.disp.clear()

        # installed by setup.py into share/dingo_peripheral_interfacing/lib
        self.battery_icon_path = os.path.join(
            get_package_share_directory('dingo_peripheral_interfacing'), 'lib', 'emptybatterystatus_white.png')

        self.battery_voltage_subscriber = self.create_subscription(
            ElectricalMeasurements, "/electrical_measurements", self.update_battery_percentage, 10)

        self.battery_percentage = 0.7  # Number between 0 and 1

        self.timer = self.create_timer(1.0 / 50, self.run)  # 50 Hz

    def update_battery_percentage(self, message):

        # max_voltage and min_voltage for 4s lipo battery
        max_voltage = 16.8
        min_voltage = 14.0

        # Ensure the received voltage is within expected bounds
        battery_voltage_level = max(min(message.battery_voltage_level, max_voltage), min_voltage)

        # Convert to percentage
        self.battery_percentage = (battery_voltage_level - min_voltage) / (max_voltage - min_voltage)

        # self.get_logger().info("Battery voltage level: {}".format(message.battery_voltage_level))
        # self.get_logger().info("Updated battery percentage: {:.2f}%".format(self.battery_percentage * 100))

    def run(self):
        try:
            # display with hardware SPI:
            #self.get_logger().info("Initializing display...")

            # Create blank image for drawing.
            image1 = Image.new("RGB", (self.disp.height, self.disp.width), "black")
            draw = ImageDraw.Draw(image1)

            #self.get_logger().info("Importing fonts...")
            Font1 = ImageFont.truetype("/usr/share/fonts/truetype/Font02.ttf", 25)
            Font1_small = ImageFont.truetype("/usr/share/fonts/truetype/Font02.ttf", 20)
            Font1_large = ImageFont.truetype("/usr/share/fonts/truetype/Font02.ttf", 60)
            Font2 = ImageFont.truetype("/usr/share/fonts/truetype/Font01.ttf", 35)
            Font3 = ImageFont.truetype("/usr/share/fonts/truetype/Font02.ttf", 120)

            # draw.text((60, -15), 'Dingo', fill="RED", font=Font3)
            draw.text((20, 110), 'SSID: '+ self.ssid, fill="WHITE", font=Font1)
            draw.text((20, 135), 'IP: ' + self.ipAddress, fill="WHITE", font=Font1)
            current_time = time.strftime("%I:%M:%S%p")
            draw.text((220, 0), current_time, fill="WHITE", font=Font1_small)

            ## Battery indication bar
            black= Image.new("RGB", (320, 172), "black")

            batt_status = Image.open(self.battery_icon_path)

            # batt_status = batt_status.rotate(180)
            batt_draw = ImageDraw.Draw(batt_status)

            if self.battery_percentage <=0.20:
                batt_fill = "RED"
            elif 0.20 < self.battery_percentage <=0.60:
                batt_fill = "#d49b00" #yellow
            else:
                batt_fill = "#09ab00" #green

            batt_draw.rounded_rectangle([(42,92),(42+(153*self.battery_percentage) ,170)],8,fill = batt_fill)
            batt_draw.text((68, 95),str(int(self.battery_percentage*100))+"%", fill = "WHITE",font = Font1_large)
            batt_scale_factor=0.8
            resized_batt_status = batt_status.resize((int(batt_status.size[0]*batt_scale_factor),int(batt_status.size[1]*batt_scale_factor)))
            image1.paste(resized_batt_status,(62, -40),resized_batt_status.convert('RGBA'))


            #self.get_logger().info("Drawing...")
            image1 = image1.rotate(0)
            image1 = image1.transpose(Image.ROTATE_270)
            self.disp.ShowImage(image1)

            ## SSID and IP are calcultated after displaying so that they can run on the second loop
            #self.get_logger().info("Connecting to Wi-Fi...")
            try:
                self.ssid = os.popen("iwgetid -r").read().strip()
            except Exception as e:
                self.get_logger().error(str(e))
                self.ssid = "N/A"

            #self.get_logger().info("SSID: " + str(self.ssid))
            #self.get_logger().info("Getting IP address...")
            try:
                #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                #s.connect(('google.com', 0))
                #self.ipAddress = s.getsockname()[0]
                #s.close()
                hostname=socket.gethostname()   
                self.ipAddress=socket.gethostbyname(hostname) 
            except Exception as e:
                self.get_logger().error(str(e))
                self.ipAddress = '-:-:-:-'
            #self.get_logger().info("IP: {self.ipAddress}")

        except Exception as e:
            self.get_logger().error(str(e))
            

    def shutdown_display(self):
        self.get_logger().info("Quitting...")
        self.disp.clear()
        self.disp.module_exit()


def main(args=None):
    rclpy.init(args=args)
    node = DingoDisplayNode()
    node.get_logger().info("Display node started, ouputting to display")
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.shutdown_display()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
