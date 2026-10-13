"""Hardware profile of the target computer: ELTAY RM66 (Rockchip RK3566) on the ELTAY BB CM4 baseboard.

Adafruit Blinka (used for the I2C devices: PCA9685 servo board and BNO055 IMU) does not know this board by
itself, so it is told which board to emulate. ORANGE_PI_3B is the Blinka board whose 40-pin map is identical to
the ELTAY BB CM4 header (all 28 GPIO pins were compared with the pinout of the baseboard), and its default I2C
bus is I2C2 on header pins 3 and 5. The variables must be set before `import board` is executed anywhere.
"""
import os

BLINKA_BOARD = "ORANGE_PI_3B"
BLINKA_CHIP = "RK3566"


def configure_blinka():
    """Set BLINKA_FORCEBOARD / BLINKA_FORCECHIP unless the user already chose other values."""
    os.environ.setdefault("BLINKA_FORCEBOARD", BLINKA_BOARD)
    os.environ.setdefault("BLINKA_FORCECHIP", BLINKA_CHIP)
