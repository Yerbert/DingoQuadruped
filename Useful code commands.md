# Useful code commands


# Adding changed files to Github Repository

Add all changed files, then commit them with a message and push

```python
git add --all
git commit -m "Insert your commit message here"
git push
```

# Managing Wifi Networks and Connections

Connections on the pi can be managed by running:

```python
sudo nano /etc/netplan/50-cloud-init.yaml
```

# ROS launch for LCD at startup

robot_upstart does not exist for ROS 2, so the LCD launch file is started by a systemd service. Create `/etc/systemd/system/dingo_lcd.service` (replace `<user>`; this is an example, adjust it to your installation):

```ini
[Unit]
Description=Dingo LCD node
After=network.target

[Service]
User=<user>
ExecStart=/bin/bash -c "source /opt/ros/humble/setup.bash && source /home/<user>/DingoQuadruped/dingo_ws/install/setup.bash && ros2 launch dingo_peripheral_interfacing lcd.launch.py"
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```python
sudo systemctl daemon-reload && sudo systemctl enable --now dingo_lcd
```

The service user needs access to the SPI and GPIO devices (see "Setting necessary permissions for ROS" in the README).

## Run LCD node manually

If it doesn’t properly start on startup, LCD can be turned on using:

```python
ros2 run dingo_peripheral_interfacing dingo_lcd_interfacing.py
```

The LCD node is also started by dingo.launch.py when `is_physical` is true. Do not run it twice.

# Create a pull request on Github

Include the Notion task link in your PR description. 

# Launch Dingo control in simulation

```python
source install/setup.bash
ros2 launch dingo_gazebo simulation.launch.py
ros2 launch dingo dingo.launch.py is_physical:=false is_sim:=true
```

# View joint or task space objectives

Make sure dingo.launch.py has been started first then:

```python
source install/setup.bash
ros2 topic echo /task_space_goals
ros2 topic echo /joint_space_goals
```

# Calibrate Robot Servos

The **HardwareInterface.py** code uses a matrix of offset angles to ensure the robot’s motors are calibrated. Calibration can be tweaked in two ways

1. **CalibrateServos.py** contains extensive calibration instructions. It requires running the script multiple times and tweaking offset values individually. Note that this file is not used by any other files, so once the offset values have been set here, they can be copied across the the **HardwareInterface.py** code for use in the main files. 
    
    This calibration can be run using:
    
    ```python
    export BLINKA_FORCEBOARD=ORANGE_PI_3B BLINKA_FORCECHIP=RK3566
    cd ~/DingoQuadruped/dingo_ws/src/dingo_hardware_interfacing/dingo_servo_interfacing/src/dingo_servo_interfacing
    python3 CalibrateServos.py
    ```
    
    1. At the bottom of the [**HardwareInterface.py](http://HardwareInterface.py)** code, there is a section that allows testing by sending all legs to the same set of 3 joint angles (defining hip, upper and lower leg servo angles for the leg. This is not the suggested method but can be good if only a single motor needs to be tweaked. This file can be run using:
    
    ```python
    export BLINKA_FORCEBOARD=ORANGE_PI_3B BLINKA_FORCECHIP=RK3566
    python3 HardwareInterface.py
    ```

    (run it from the same folder)