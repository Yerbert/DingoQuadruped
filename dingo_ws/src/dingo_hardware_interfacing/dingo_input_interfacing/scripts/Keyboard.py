#!/usr/bin/env python3

import rospy
import sys
import threading
from sensor_msgs.msg import Joy
from evdev import InputDevice, categorize, ecodes

# === НАСТРОЙКА: УКАЖИТЕ ПУТЬ К УСТРОЙСТВУ КЛАВИАТУРЫ ===
KEYBOARD_DEVICE = "/dev/input/event0"
# Если не знаете точный путь — используйте /dev/input/eventX (например, event3)
# ИЛИ замените на автоопределение (см. примечание внизу)

class KeyboardEvdev:
    def __init__(self, device_path):
        self.device = InputDevice(device_path)
        self.device.grab()  # Захватываем устройство, чтобы другие не ловили события

        self.speed_multiplier = 1
        self.joy_pub = rospy.Publisher("joy", Joy, queue_size=10)

        self.current_joy = Joy()
        self.current_joy.axes = [0.0] * 8
        self.current_joy.buttons = [0] * 11

        self.running = True
        self.thread = threading.Thread(target=self._event_loop)
        self.thread.start()

    def _event_loop(self):
        for event in self.device.read_loop():
            if not self.running:
                break
            if event.type == ecodes.EV_KEY:
                self._handle_key(event)

    def _handle_key(self, event):
        key_event = categorize(event)
        key_code = key_event.keycode
        is_press = key_event.keystate == key_event.key_down

        # Сброс всех значений перед обновлением (для корректного отпускания)
        # Но мы будем обновлять только то, что изменилось
        if isinstance(key_code, list):
            key_code = key_code[0]  # Иногда возвращается список

        # Обработка клавиш
        if key_code == 'KEY_LEFTSHIFT' or key_code == 'KEY_RIGHTSHIFT':
            if is_press:
                self.speed_multiplier = 2
            else:
                self.speed_multiplier = 1

        elif key_code == 'KEY_W':
            self.current_joy.axes[1] = 0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_S':
            self.current_joy.axes[1] = -0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_A':
            self.current_joy.axes[0] = 0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_D':
            self.current_joy.axes[0] = -0.5 * self.speed_multiplier if is_press else 0.0

        elif key_code == 'KEY_UP':
            self.current_joy.axes[4] = 0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_DOWN':
            self.current_joy.axes[4] = -0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_LEFT':
            self.current_joy.axes[3] = 0.5 * self.speed_multiplier if is_press else 0.0
        elif key_code == 'KEY_RIGHT':
            self.current_joy.axes[3] = -0.5 * self.speed_multiplier if is_press else 0.0

        elif key_code == 'KEY_1':
            self.current_joy.buttons[5] = 1 if is_press else 0
        elif key_code == 'KEY_2':
            self.current_joy.buttons[0] = 1 if is_press else 0
        elif key_code == 'KEY_BACKSPACE':
            self.current_joy.buttons[4] = 1 if is_press else 0

        elif key_code == 'KEY_7':
            self.current_joy.axes[6] = -1 if is_press else 0
        elif key_code == 'KEY_8':
            self.current_joy.axes[6] = 1 if is_press else 0
        elif key_code == 'KEY_9':
            self.current_joy.axes[7] = -1 if is_press else 0
        elif key_code == 'KEY_0':
            self.current_joy.axes[7] = 1 if is_press else 0

        # Публикуем обновлённое сообщение
        self.current_joy.header.stamp = rospy.Time.now()
        self.joy_pub.publish(self.current_joy)

    def stop(self):
        self.running = False
        self.device.ungrab()
        self.thread.join()

# === ОСНОВНОЙ ЗАПУСК ===
def main():
    rospy.init_node("keyboard_input_listener", anonymous=True)
    rate = rospy.Rate(30)

    # Автоматическое определение клавиатуры (опционально)
    # Если хотите — раскомментируйте этот блок и закомментируйте KEYBOARD_DEVICE
    """
    from evdev import list_devices, InputDevice
    devices = [InputDevice(fn) for fn in list_devices()]
    kb_device = None
    for dev in devices:
        if 'keyboard' in dev.name.lower() or 'kbd' in dev.phys:
            kb_device = dev.path
            break
    if not kb_device:
        rospy.logfatal("No keyboard found in /dev/input/")
        sys.exit(1)
    """

    try:
        kb = KeyboardEvdev(KEYBOARD_DEVICE)
        rospy.loginfo(f"Keyboard listener started on {KEYBOARD_DEVICE}")
    except Exception as e:
        rospy.logfatal(f"Failed to open keyboard device {KEYBOARD_DEVICE}: {e}")
        sys.exit(1)

    try:
        while not rospy.is_shutdown():
            rate.sleep()
    except KeyboardInterrupt:
        pass
    finally:
        kb.stop()

if __name__ == '__main__':
    main()
