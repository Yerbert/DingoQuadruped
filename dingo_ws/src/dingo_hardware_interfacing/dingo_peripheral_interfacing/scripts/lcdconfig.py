#!/usr/bin/env python3
# /*****************************************************************************
# * | File        :	  epdconfig.py
# * | Author      :   Waveshare team
# * | Function    :   Hardware underlying interface
# * | Info        :
# *----------------
# * | This version:   V1.0
# * | Date        :   2019-06-21
# * | Info        :   
# ******************************************************************************
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import os
import sys
import time
import spidev
import logging
import numpy as np

from dingo_peripheral_interfacing.gpio_lines import GpioLines

# Waveshare hardware layer. Despite the class name it no longer needs a Raspberry Pi: GPIO goes through
# libgpiod (line offsets of gpio_chip) and SPI through spidev (spi_bus/spi_device).
class RaspberryPi:
    def __init__(self,spi=None,spi_freq=40000000,rst = "GPIO4_A0",dc = "GPIO4_A4",bl = "GPIO3_C7",bl_freq=1000,i2c=None,i2c_freq=100000,
                 gpio_chip="gpiochip0",spi_bus=3,spi_device=0):
        self.np=np
        self.RST_PIN= rst
        self.DC_PIN = dc
        self.BL_PIN = bl
        self.SPEED  =spi_freq
        self.BL_freq=bl_freq
        self.GPIO = GpioLines(gpio_chip, consumer="dingo-lcd")
        self.GPIO.output(self.RST_PIN, 0)
        self.GPIO.output(self.DC_PIN, 0)
        self.GPIO.output(self.BL_PIN, 1)
        #Initialize SPI (opened here, not at import time, so the bus can be chosen per board)
        if spi is None:
            spi = spidev.SpiDev()
            spi.open(spi_bus, spi_device)
        self.SPI = spi
        if self.SPI!=None :
            self.SPI.max_speed_hz = spi_freq
            self.SPI.mode = 0b00

    def digital_write(self, pin, value):
        self.GPIO.write(pin, value)

    def digital_read(self, pin):
        return self.GPIO.read(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        if self.SPI!=None :
            self.SPI.writebytes(data)

    # libgpiod has no PWM: the backlight is simply on (duty > 0) or off, brightness cannot be dimmed.
    def bl_DutyCycle(self, duty):
        self.GPIO.write(self.BL_PIN, 1 if duty > 0 else 0)
        
    def bl_Frequency(self,freq):
        pass
           
    def module_init(self):
        self.GPIO.write(self.BL_PIN, 1)
        if self.SPI!=None :
            self.SPI.max_speed_hz = self.SPEED        
            self.SPI.mode = 0b00     
        return 0

    def module_exit(self):
        logging.debug("spi end")
        if self.SPI!=None :
            self.SPI.close()
        
        logging.debug("gpio cleanup...")
        self.GPIO.write(self.RST_PIN, 1)
        self.GPIO.write(self.DC_PIN, 0)        
        time.sleep(0.001)
        self.GPIO.write(self.BL_PIN, 1)
        self.GPIO.release()


'''
if os.path.exists('/sys/bus/platform/drivers/gpiomem-bcm2835'):
    implementation = RaspberryPi()

for func in [x for x in dir(implementation) if not x.startswith('_')]:
    setattr(sys.modules[__name__], func, getattr(implementation, func))
'''

### END OF FILE ###
