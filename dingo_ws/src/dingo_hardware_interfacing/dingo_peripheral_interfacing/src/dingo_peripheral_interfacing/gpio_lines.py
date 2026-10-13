"""Small GPIO layer on top of libgpiod, replacing RPi.GPIO (which only works on a Raspberry Pi).

A pin is given either as a Rockchip name, exactly as printed in the pinout of the ELTAY BB CM4 / Orange Pi CM4
("GPIO4_A5"), or as a plain line offset on the default chip. A name is resolved to the gpiochip whose label is
"gpio<bank>" and the line offset group * 8 + n (A=0, B=1, C=2, D=3), so no gpiochip numbering has to be known:
GPIO4_A5 -> chip labelled gpio4, line 5; GPIO3_D4 -> chip labelled gpio3, line 28.
`gpiodetect` and `gpioinfo` list the chips and lines of the board.

Targets the libgpiod v1 python bindings (apt package python3-libgpiod on Ubuntu 22.04).
"""
import re

try:
    import gpiod
except ImportError:  # reported when the first GpioLines is created, so the module still imports
    gpiod = None

_ROCKCHIP_PIN = re.compile(r"^GPIO([0-4])_([A-D])([0-7])$", re.IGNORECASE)


class GpioError(RuntimeError):
    pass


def resolve_pin(pin, default_chip="gpiochip0"):
    """Return (chip, line offset). chip is a name for gpiod.Chip, or "label:<label>" to open by label."""
    if isinstance(pin, int) and not isinstance(pin, bool):
        return default_chip, pin
    text = str(pin).strip()
    if text.isdigit():
        return default_chip, int(text)
    match = _ROCKCHIP_PIN.match(text)
    if match:
        bank, group, number = match.groups()
        return f"label:gpio{bank}", (ord(group.upper()) - ord("A")) * 8 + int(number)
    raise GpioError(f"cannot understand GPIO pin '{pin}': use a name like GPIO4_A5 or a line offset")


class GpioLines:
    LOW = 0
    HIGH = 1

    def __init__(self, chip_name="gpiochip0", consumer="dingo"):
        if gpiod is None:
            raise GpioError("python3-libgpiod is not installed (sudo apt install python3-libgpiod)")
        if hasattr(gpiod, "request_lines"):
            raise GpioError("libgpiod v2 python bindings found, but dingo_peripheral_interfacing is written "
                            "for the v1 API of python3-libgpiod (Ubuntu 22.04)")
        self._default_chip = chip_name
        self._consumer = consumer
        self._chips = {}
        self._lines = {}
        self._keys = {}

    def _chip(self, name):
        if name not in self._chips:
            if name.startswith("label:"):
                self._chips[name] = gpiod.Chip(name[len("label:"):], gpiod.Chip.OPEN_BY_LABEL)
            else:
                self._chips[name] = gpiod.Chip(name)
        return self._chips[name]

    def _key(self, pin):
        if pin not in self._keys:
            self._keys[pin] = resolve_pin(pin, self._default_chip)
        return self._keys[pin]

    def _request(self, pin, direction, **kwargs):
        key = self._key(pin)
        if key in self._lines:
            raise GpioError(f"pin {pin} ({key[0]} line {key[1]}) is already requested")
        line = self._chip(key[0]).get_line(key[1])
        line.request(consumer=self._consumer, type=direction, **kwargs)
        self._lines[key] = line

    def input(self, pin):
        self._request(pin, gpiod.LINE_REQ_DIR_IN)

    def output(self, pin, initial=0):
        self._request(pin, gpiod.LINE_REQ_DIR_OUT, default_val=1 if initial else 0)

    def read(self, pin):
        return self._lines[self._key(pin)].get_value()

    def write(self, pin, value):
        self._lines[self._key(pin)].set_value(1 if value else 0)

    def release(self):
        for line in self._lines.values():
            line.release()
        self._lines.clear()
        for chip in self._chips.values():
            chip.close()
        self._chips.clear()
