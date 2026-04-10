#!/usr/bin/env python3

import os
import random
import subprocess
import rospy
import rospkg
from sensor_msgs.msg import Joy

# Circle button index on a PS4/PS3 joystick via the ROS joy package
CIRCLE_BUTTON_INDEX = 1


class DingoVoiceNode:
    def __init__(self):
        rospy.init_node("dingo_voice_node", anonymous=False)

        # Resolve path to the sounds directory bundled with this package
        pkg_path = rospkg.RosPack().get_path("dingo_peripheral_interfacing")
        sounds_dir = os.path.join(pkg_path, "sounds")

        self.sound_files = [
            os.path.join(sounds_dir, f)
            for f in os.listdir(sounds_dir)
            if f.lower().endswith(".mp3")
        ]

        if not self.sound_files:
            rospy.logwarn("dingo_voice_node: no MP3 files found in %s", sounds_dir)

        self._prev_circle = 0
        self._player_proc = None

        rospy.Subscriber("joy", Joy, self._joy_callback)
        rospy.loginfo("dingo_voice_node: ready, %d sound(s) loaded", len(self.sound_files))

    def _joy_callback(self, msg):
        if len(msg.buttons) <= CIRCLE_BUTTON_INDEX:
            return

        circle_pressed = msg.buttons[CIRCLE_BUTTON_INDEX]

        # Trigger on rising edge (button just pressed)
        if circle_pressed == 1 and self._prev_circle == 0:
            self._play_random_sound()

        self._prev_circle = circle_pressed

    def _play_random_sound(self):
        if not self.sound_files:
            rospy.logwarn("dingo_voice_node: no sounds available to play")
            return

        # Stop any currently playing sound before starting a new one
        if self._player_proc is not None and self._player_proc.poll() is None:
            self._player_proc.terminate()

        sound = random.choice(self.sound_files)
        rospy.loginfo("dingo_voice_node: playing %s", os.path.basename(sound))

        # mpg123 plays MP3 directly through the ALSA/jack audio output
        self._player_proc = subprocess.Popen(
            ["mpg123", "-q", sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def spin(self):
        rospy.spin()

        # Clean up player process on shutdown
        if self._player_proc is not None and self._player_proc.poll() is None:
            self._player_proc.terminate()


def main():
    node = DingoVoiceNode()
    node.spin()


if __name__ == "__main__":
    main()
