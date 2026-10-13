FROM osrf/ros:humble-desktop-full

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    python3-pip \
    ros-humble-xacro \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher-gui \
    ros-humble-joy \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-gazebo-ros2-control \
    ros-humble-rmw-cyclonedds-cpp \
    i2c-tools \
    python3-smbus \
    python3-libgpiod \
    python3-evdev \
    gdb \
    nano \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    transforms3d \
    pyserial \
    pynput \
    spidev \
    adafruit-circuitpython-servokit \
    adafruit-circuitpython-bno055 \
    matplotlib \
    numpy

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Adafruit Blinka does not know the ELTAY RM66 / ELTAY BB CM4. ORANGE_PI_3B has the same 40-pin map and I2C2 as default bus.
ENV BLINKA_FORCEBOARD=ORANGE_PI_3B
ENV BLINKA_FORCECHIP=RK3566

RUN echo "source /opt/ros/humble/setup.bash" >> /etc/bash.bashrc

COPY ros_entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

WORKDIR /dingo_ws
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
