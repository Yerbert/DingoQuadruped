#!/usr/bin/env python3
import os
import random
import pygame
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
        self._mixer_ready = self._init_mixer_once()
        

        rospy.Subscriber("joy", Joy, self._joy_callback)
        rospy.on_shutdown(self._shutdown_audio)
        rospy.loginfo("dingo_voice_node: ready, %d sound(s) loaded", len(self.sound_files))

    def _init_mixer_once(self):
        try:
            pygame.mixer.init()
            return True
        except Exception as e:
            rospy.logerr("dingo_voice_node: failed to init pygame mixer: %s", e)
            return False
        
    def _joy_callback(self, msg):
        if len(msg.buttons) <= CIRCLE_BUTTON_INDEX:
            return

        circle_pressed = msg.buttons[CIRCLE_BUTTON_INDEX]

        # Trigger on rising edge (button just pressed)
        if circle_pressed and self._prev_circle == 0:
            self._play_random_sound()

        self._prev_circle = circle_pressed

    def _play_random_sound(self):
        if not self._mixer_ready:
            rospy.logwarn("dingo_voice_node: pygame mixer not ready, skipping sound.")
            return

        if not self.sound_files:
            rospy.logwarn("dingo_voice_node: no sounds available to play")
            return

        sound = random.choice(self.sound_files)
        rospy.loginfo("dingo_voice_node: playing %s", os.path.basename(sound))

        try:
            # Stop any currently playing sound before starting a new one
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()

            pygame.mixer.music.load(sound)
            pygame.mixer.music.play()
        except Exception as e:
            rospy.logerr("dingo_voice_node: failed to play sound %s: %s", sound, e)
            
            
    def _shutdown_audio(self):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except Exception as e:
            rospy.logwarn("dingo_voice_node: audio shutdown warning: %s", e)
        

    def spin(self):
        rospy.spin()


def main():
    node = DingoVoiceNode()
    node.spin()


if __name__ == "__main__":
    main()
