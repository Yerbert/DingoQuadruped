# План переноса Dingo: ROS 1 Noetic (Ubuntu 20.04) → ROS 2 Humble (Ubuntu 22.04)

Это пошаговый план для самостоятельного переноса. Он составлен по реальному коду репозитория (`dingo_ws/src`, `Dockerfile`, `dingo_nano`).

## 0. Предположения (проверьте)

- Ubuntu 22.04 ⇒ целевая версия **ROS 2 Humble Hawksbill** (LTS до 2027, единственный дистрибутив с официальными deb-пакетами для 22.04).
- «rm66» я понимаю как Rockchip **RK3566** (arm64/aarch64) или похожую плату. Если плата другая, уточните: от неё зависят пункты про GPIO/I2C/UART (раздел 4, этап 5).
- Старый робот на Raspberry Pi + Noetic остаётся рабочим эталоном, пока новый не заработает. Работайте в отдельной ветке: `git checkout -b ros2-humble`.

## 1. Что есть сейчас (инвентаризация)

| Пакет | Что внутри | ROS 1-зависимости |
|---|---|---|
| `dingo` | `scripts/dingo_driver.py` (главный узел), `run_robot.py` (устаревший), `status_publisher.py`, 3 launch | rospy, Publisher/Subscriber, Rate, `rospy.myargv` |
| `dingo_control` | Gaits, Kinematics, Stance/Swing, Controller, Config, State; **msg**: Angle, JointSpace, TaskSpace | rospy в `Controller.py` и `Kinematics.py` (только логи и 2 паблишера), catkin + message_generation |
| `dingo_description` | URDF, меши, launch для rviz/state_publisher | `xacro --inorder`, `.rviz` для rviz1 |
| `dingo_gazebo` | `simulation.launch`, `controllers.yaml`, 2 world | gazebo_ros, controller_manager spawner, `effort_controllers/JointPositionController` |
| `dingo_input_interfacing` | `InputInterface.py` (подписка на `joy`), `Keyboard.py` (evdev → Joy) | rospy, sensor_msgs/Joy |
| `dingo_servo_interfacing` | PCA9685 через `adafruit_servokit` (I2C) | rospy только для `logwarn` |
| `dingo_peripheral_interfacing` | IMU BNO055 (I2C), LCD (SPI + RPi.GPIO), `battery_voltage_checking.py` (RPi.GPIO), msg ElectricalMeasurements | rospy, rospkg, RPi.GPIO |
| `dingo_nano/*.ino` | Arduino Nano, публикует `emergency_stop_status` и `electrical_measurements` через **rosserial** | `ros.h` (rosserial) |
| `Dockerfile`, `Docker-compose.yaml`, `.devcontainer.json` | образ `osrf/ros:noetic-desktop-full`, `catkin_make` | всё |

Хорошая новость: чистая математика (`Gaits`, `StanceController`, `SwingLegController`, `Kinematics`, `Config`, `State`, `Command`, `util`, `dingo_utilities`) от ROS почти не зависит. Её переносим «как есть», убрав `rospy` из `Kinematics.py` и `Controller.py`.

## 2. Целевой стек

| Было (Noetic) | Станет (Humble) |
|---|---|
| catkin, `catkin_make` | ament_cmake / ament_python, `colcon build` |
| rospy | rclpy |
| `.launch` (XML ROS 1) | Python launch (`.launch.py`) |
| rosserial + Arduino | **нет аналога для Nano**, см. этап 6 |
| `joy` (старый) | `ros-humble-joy` (на SDL2, **другая раскладка осей**) |
| gazebo_ros + `controller_manager/spawner` + effort PID | `gazebo_ros_pkgs` (Gazebo Classic 11) + `gazebo_ros2_control` + `ros2_control` |
| rviz | rviz2 |
| `osrf/ros:noetic-desktop-full` | `ros:humble` / `osrf/ros:humble-desktop-full` (multi-arch, есть arm64) |
| Python 3.8 | Python 3.10 |

## 3. Общая стратегия

1. **Сначала Docker на ноутбуке (x86)**, а не на плате. Образ Humble мультиархитектурный, поэтому тот же Dockerfile потом соберётся на arm64. Так отлаживаются логика, сообщения, launch и симуляция без железа.
2. Порядок: образ → пакеты-интерфейсы (msg) → чистая логика → узел-драйвер → ввод (joy) → описание/rviz → симуляция → железо на плате.
3. Железные части (I2C, SPI, GPIO, UART) переносим **последними**, на самой плате.
4. На каждом этапе есть критерий готовности (раздел 5).

## 4. Этапы

### Этап 1. Образ и сборка

- [ ] В `Dockerfile` заменить базу на `osrf/ros:humble-desktop-full` и убрать строку с `ros-latest.list` (в базовом образе репозиторий уже подключён).
- [ ] Заменить apt-пакеты:
  - `ros-noetic-ros-controllers` → `ros-humble-ros2-control ros-humble-ros2-controllers ros-humble-gazebo-ros2-control ros-humble-gazebo-ros-pkgs`
  - `ros-noetic-joy` → `ros-humble-joy`
  - `ros-noetic-rosserial*`, `ros-noetic-soem`, `python3-catkin-tools` → удалить (soem не нужен, rosserial нет)
  - добавить `ros-humble-xacro ros-humble-robot-state-publisher ros-humble-joint-state-publisher-gui ros-humble-rviz2 python3-colcon-common-extensions`
  - `python3-rosdep`, `python3-vcstool`, `python3-pip` оставить.
- [ ] pip: пакет `serial` не нужен и вреден (конфликтует с `pyserial`, оставьте только `pyserial`). `UDPComms`, `pigpio` из кода не используются (HardwareInterface про pigpio закомментирован). Убрать, пока не понадобится. `RPi.GPIO` на Rockchip не работает, см. этап 5.
- [ ] Вместо `catkin_make` собирать `colcon build --symlink-install`; в `.bashrc` source `/opt/ros/humble/setup.bash` и `install/setup.bash` (вместо `devel/`).
- [ ] `ros_entrypoint.sh` менять не нужно (использует `$ROS_DISTRO`).
- [ ] `.devcontainer.json`: расширение `ms-iot.vscode-ros` остаётся.
- [ ] `.gitignore`: добавить `build/ install/ log/`.

### Этап 2. Интерфейсы (msg) и структура пакетов

Это самое важное архитектурное решение. Сейчас пакет `dingo_control` одновременно содержит Python-модули и `msg/`, а `dingo_peripheral_interfacing` аналогично. В ROS 2 сгенерированный `dingo_control.msg` и ваш Python-пакет `dingo_control` будут конфликтовать по имени.

**Рекомендация:** создать отдельный пакет `dingo_msgs` (ament_cmake + rosidl) и перенести туда все `.msg`. Остальные пакеты делать `ament_python`.

Правки в самих `.msg` (иначе не соберётся):
- [ ] В `JointSpace.msg` и `TaskSpace.msg` убрать развёрнутые `uint32 seq / time stamp / string frame_id` и написать просто `std_msgs/Header header` (поля `seq` в ROS 2 нет).
- [ ] **Имена полей в ROS 2 только в нижнем регистре** (`snake_case`): `FL_foot` → `fl_foot`, `FR_foot` → `fr_foot`, `RL_foot` → `rl_foot`, `RR_foot` → `rr_foot`. Придётся поправить места использования в `Controller.py` и `dingo_driver.py`.
- [ ] `ElectricalMeasurements.msg` (`battery_voltage_level`, `servo_buck_voltage_level`): имена уже допустимы, формат тот же.
- [ ] `Angle.msg`: поля `theta1..3` допустимы.
- [ ] `package.xml` → format 3, `<buildtool_depend>ament_cmake</buildtool_depend>`, `rosidl_default_generators`, `rosidl_default_runtime`, `<member_of_group>rosidl_interface_packages</member_of_group>`, зависимости `std_msgs`, `geometry_msgs`.
- [ ] `CMakeLists.txt`: `rosidl_generate_interfaces(${PROJECT_NAME} "msg/Angle.msg" ... DEPENDENCIES std_msgs geometry_msgs)`.

Для каждого остального пакета (`dingo`, `dingo_control`, `dingo_utilities`, `dingo_*_interfacing`):
- [ ] Удалить `CMakeLists.txt` (если пакет чисто Python), оставить `package.xml` (format 3, `ament_python`) + `setup.py` + `setup.cfg` + `resource/<имя_пакета>` (пустой файл-маркер).
- [ ] `setup.py` переписать на `setuptools` с `data_files` (launch, config) и `entry_points={'console_scripts': [...]}`. Скрипты из `scripts/` либо превратить в entry points, либо положить в `lib/<pkg>`.
- [ ] Структура модулей `src/<pkg>/...` меняется на `<pkg>/<pkg>/...` (ament_python ждёт пакет рядом с `setup.py`).
- [ ] Импорт `from dingo_control.msg import ...` → `from dingo_msgs.msg import ...`.

### Этап 3. Чистая логика и узел-драйвер

`Kinematics.py`, `Controller.py`:
- [ ] Убрать `import rospy`. В `Kinematics.py` заменить `rospy.logwarn` на `logging.getLogger(__name__).warning` (математика не должна зависеть от ROS).
- [ ] В `Controller.py` паблишеры (`task_space_goals`, `joint_space_goals`, строки 30-31) вынести в узел-драйвер. `Controller` оставить чистым: пусть возвращает данные, а публикует драйвер. Иначе `Controller` придётся передавать `node` в конструктор.
- [ ] `rospy.Time.now()` → `node.get_clock().now().to_msg()`.

`dingo_driver.py` (главный узел), основная переделка:
- [ ] `class DingoDriver(Node)`, `super().__init__('dingo_driver')`. Аргументы `is_sim/is_physical/use_imu` получать как **ROS-параметры** (`declare_parameter`), а не через `sys.argv`.
- [ ] `rospy.Subscriber(topic, T, cb)` → `create_subscription(T, topic, cb, 10)` (порядок аргументов другой!). `rospy.Publisher(topic, T, queue_size=n)` → `create_publisher(T, topic, n)`.
- [ ] **Главное:** сейчас `run()` это блокирующий `while`-цикл с `rate.sleep()`, а колбэки `joy` и `emergency_stop_status` приходят в параллельных потоках rospy. В rclpy колбэки обрабатываются только внутри `spin`. Нельзя крутить `while` и ждать колбэков в том же потоке. Два варианта:
  - (рекомендую) переписать цикл как `self.create_timer(1/50, self.control_step)` и хранить режим (manual / external / estop) как поле состояния. Блокирующие вложенные `while` превращаются в ветки `if` внутри `control_step`;
  - или оставить цикл в отдельном потоке и использовать `MultiThreadedExecutor` (быстрее переносится, но нужны блокировки на общих полях `state`).
- [ ] `rospy.is_shutdown()` → `rclpy.ok()`; `rospy.loginfo/logwarn/logerr` → `self.get_logger().info/warning/error`.
- [ ] `InputInterface` создаёт подписку `joy` внутри себя через `rospy.Subscriber`. Передавайте в него `node` (или вынесите подписку в драйвер и вызывайте `input_interface.input_callback(msg)`).
- [ ] `signal_handler`/`sys.exit` убрать: `rclpy` сам обрабатывает SIGINT.

Симуляционные топики `/dingo_controller/FR_theta1/command` (12 штук, `Float64`) заменить на один топик `forward_command_controller` с `std_msgs/Float64MultiArray` (см. этап 7), порядок элементов должен совпадать с `controllers.yaml`.

`status_publisher.py`: тривиален (один `String`-паблишер), перенести на `Node.create_publisher`.
`run_robot.py`: устаревший скрипт (импортирует несуществующий `dingo_input_interfacing.InputController`), его **лучше не переносить**, а удалить.

### Этап 4. Ввод (joy / клавиатура)

- [ ] `InputInterface.input_callback` индексирует `msg.buttons[0,4,5]` и `msg.axes[0,1,3,4,6,7]`. **В Humble `joy` собран на SDL2 и раскладка осей/кнопок геймпада изменилась** (например, крестовина у ряда геймпадов приходит не осями 6/7, а кнопками, у PS4 другая нумерация триггеров). Проверьте `ros2 topic echo /joy` с вашим геймпадом и перепишите индексы (лучше вынести в `HardwareConfig.py`/параметры).
- [ ] Параметры `joy_node` изменились: `autorepeat_rate` остаётся, вместо `dev` — `device_id` (число).
- [ ] `Keyboard.py`: `rospy.init_node`/`Rate`/`Publisher("joy", Joy)` на rclpy; логика evdev остаётся. `KEYBOARD_DEVICE = "/dev/input/event0"` проверьте на новой плате.

### Этап 5. Железо на новой плате (RK3566, arm64)

Raspberry Pi специфика, которая **не заработает как есть**:

| Что в коде | Проблема на Rockchip | Что делать |
|---|---|---|
| `RPi.GPIO` (`battery_voltage_checking.py`, `lcdconfig.py`) | библиотека только для Raspberry Pi | заменить на `gpiod` (libgpiod, `python3-libgpiod`) либо на библиотеку вендора платы; номера пинов BCM → номера линий `gpiochipN/line` вашей платы, заново сверить по распиновке |
| `adafruit_servokit` / `board.I2C()` (Blinka) в `HardwareInterface.py`, `IMU.py` | Blinka знает только поддерживаемые платы | проверить, определяется ли ваша плата в Blinka; если нет — задать через `BLINKA_FORCEBOARD`/`BLINKA_FORCECHIP` или переписать доступ к PCA9685 и BNO055 на `smbus2` (регистры простые) |
| I2C шина `1` в README | на Rockchip номер шины другой | `i2cdetect -l`, `i2cdetect -y N`; включить нужную шину через device tree overlay/`armbian-config` |
| SPI дисплей `spidev.SpiDev(0,0)` | нужный SPI может быть выключен | включить SPI overlay, проверить `/dev/spidev*` |
| UART `/dev/ttyS0` для Arduino | у платы другое имя (`ttyS3`, `ttyFIQ0`…) | включить нужный UART в overlay, отключить `serial-getty` на нём, прописать порт параметром |
| `libraspberrypi-bin`, `wireless-tools` в README | пакеты для Raspberry | убрать из инструкции |
| udev-правила `KERNEL=="ttyS0"`, `i2c` в README | имена устройств другие | переписать под новые устройства |

- [ ] Образ ОС для платы: проверьте, что есть Ubuntu 22.04 (или Armbian на базе jammy) именно с поддержкой вашей платы и ядром с включёнными I2C/SPI/UART. Это блокирующий пункт: ROS 2 Humble deb-пакеты есть для `arm64` на 22.04.
- [ ] Права доступа: пользователь в группах `i2c`, `spi`, `gpio`, `dialout`; в Docker-режиме `privileged: true` и `devices: /dev:/dev` уже есть.
- [ ] Заменить `rospy.logwarn("Warning - I2C IO error")` в `HardwareInterface.py` на логгер модуля. Это единственное использование rospy в этом пакете.
- [ ] `IMU.py`: убрать `import rospy` (в самом файле он не используется).
- [ ] Калибровка серв (`physical_calibration_offsets`, диапазон 370–2400) от ОС не зависит, переносится без изменений. Но проверьте частоту PCA9685 (по умолчанию 50 Гц) и питание серв.

### Этап 6. Arduino Nano (rosserial)

`rosserial` в ROS 2 **не существует**, а **micro-ROS не поддерживает Nano V3 (ATmega328P)**: мало памяти. Варианты:

1. **(рекомендую)** Переписать скетч `dingo_arduino.ino`: убрать `ros.h`, `NodeHandle`, `Publisher`; отправлять данные простым текстовым или бинарным кадром по Serial (напряжения АКБ, buck, бит E-stop). На плате написать маленький узел-мост на `pyserial`, который читает порт и публикует `emergency_stop_status` (`std_msgs/Bool`) и `electrical_measurements` (`dingo_msgs/ElectricalMeasurements`). Названия топиков оставить прежними, остальные узлы не изменятся.
2. Заменить Nano на плату, которую поддерживает micro-ROS (например, ESP32/STM32/Teensy). Это изменение железа, делать только если действительно нужно.

`battery_voltage_checking.py` (читает те же сигналы через GPIO) и `dingo_lcd_interfacing.py` подписаны на топики этого моста, так что их достаточно перенести на rclpy и заменить GPIO.

### Этап 7. Описание, rviz и симуляция

`dingo_description`:
- [ ] Из launch убрать флаг `--inorder` у xacro (в ROS 2 он не нужен и не поддерживается как раньше). Использовать `xacro` через `Command(['xacro ', path])` в `.launch.py`.
- [ ] `robot_description` передавать параметром узла `robot_state_publisher` (`parameters=[{'robot_description': ...}]`).
- [ ] Перенастроить `joint_states`: `remap from="joint_states" to="joint_space_joint_states"` оформляется через `remappings=[...]`.
- [ ] Конфиг `dingo_rviz.rviz` создан для rviz1; откройте в rviz2, поправьте Fixed Frame и displays, пересохраните как `dingo.rviz`.
- [ ] `package://dingo_description/meshes/...` в URDF продолжают работать; меши и `.dae` менять не нужно. Установить `meshes`, `urdf`, `launch` через `data_files` / `install(DIRECTORY ...)`.
- [ ] Удалить лишнее: `urdf/dingo copy.urdf`, `export.log`, `meshes/main.py` (не нужны в пакете).

`dingo_gazebo` (самая трудоёмкая часть):
- [ ] URDF уже содержит блоки `<transmission>`/`<gazebo>` (22 совпадения). Нужно заменить плагин `libgazebo_ros_control.so` на `libgazebo_ros2_control.so` и добавить блок `<ros2_control>` с `gazebo_ros2_control/GazeboSystem` и интерфейсами по каждому из 12 суставов (`position` команда + `position/velocity` состояние).
- [ ] `controllers.yaml` переписать в формат ROS 2:
  ```yaml
  controller_manager:
    ros__parameters:
      update_rate: 100
      joint_state_broadcaster: {type: joint_state_broadcaster/JointStateBroadcaster}
      joint_group_position_controller: {type: position_controllers/JointGroupPositionController}
  joint_group_position_controller:
    ros__parameters:
      joints: [FR_theta1, FR_theta2, ...]   # те же 12 суставов
  ```
  Если нужен PID по усилию, как сейчас (`effort_controllers/JointPositionController` с `p: 9, i: 0.03, d: 0.3055`) — в ROS 2 такого контроллера нет; проще использовать позиционный интерфейс в Gazebo и забыть PID, либо `joint_trajectory_controller` с PID.
- [ ] `simulation.launch` → `simulation.launch.py`: `gazebo_ros/launch/gazebo.launch.py`, `spawn_entity.py -topic robot_description -entity dingo`, затем `ros2 control load_controller --set-state active joint_state_broadcaster` и позиционный контроллер (через `ExecuteProcess`/`RegisterEventHandler`).
- [ ] Миры `normal.world`, `office.world` (SDF) в Gazebo Classic 11 открываются как есть.
- [ ] В драйвере в режиме симуляции публиковать в `/joint_group_position_controller/commands` (`Float64MultiArray`, 12 значений в порядке `joints`).
- [ ] `use_sim_time:=true` передавать параметром всем узлам.

### Этап 8. Launch-файлы

Три launch `dingo.launch`, `dingo_gazebo_sim.launch`, `dingo_simulator.launch`, плюс launch в description и peripheral переписать в `.launch.py`:
- [ ] `<arg>` → `DeclareLaunchArgument` + `LaunchConfiguration`.
- [ ] `<group if="$(arg is_physical)">` → `GroupAction(condition=IfCondition(...))`.
- [ ] `<node pkg type name args>` → `Node(package=..., executable=..., name=..., parameters=[...])`.
- [ ] `<include file="$(find ...)">` → `IncludeLaunchDescription(PythonLaunchDescriptionSource(...))`, путь через `get_package_share_directory`.
- [ ] Убрать узел `rosserial_python/serial_node.py` (заменён мостом из этапа 6).
- [ ] Пакеты вида `dingo_peripheral_interfacing/launch/LCD_service.launch` ссылаются на несуществующий пакет `dingo_lcd_interfacing` (опечатка ещё в ROS 1), исправить при переносе.
- [ ] Дополнительно: `ROS_DOMAIN_ID`, а для слабой платы и Wi-Fi лучше `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` (`ros-humble-rmw-cyclonedds-cpp`). Быстрее и стабильнее FastDDS по Wi-Fi.

## 5. Критерии готовности по этапам

| Этап | Проверка |
|---|---|
| 1 | `docker compose build` проходит; `ros2 --help` работает в контейнере |
| 2 | `colcon build` собирает `dingo_msgs`; `ros2 interface show dingo_msgs/msg/JointSpace` показывает поля в нижнем регистре |
| 3 | `ros2 run dingo dingo_driver` стартует; `ros2 topic list` показывает `joint_space_goals`/`task_space_goals`; при пустом `joy` робот в `REST` |
| 4 | `ros2 run joy joy_node` + `ros2 topic echo /joy`; нажатие L1/R1/X меняет состояние в логе драйвера |
| 5 | `i2cdetect` видит PCA9685 (0x40) и BNO055 (0x28/0x29); одна сервопривод поворачивается на команду; IMU выдаёт углы |
| 6 | `ros2 topic echo /emergency_stop_status` и `/electrical_measurements` показывают данные с Nano |
| 7 | `ros2 launch dingo_description ...` показывает модель в rviz2; `ros2 launch dingo_gazebo simulation.launch.py` — робот стоит, суставы управляются |
| 8 | один `ros2 launch dingo dingo.launch.py` поднимает всё; робот на подставке (лапы в воздухе) реагирует на геймпад |

**Безопасность:** первый запуск на реальном роботе только на подставке, лапами в воздухе; аварийный выключатель под рукой; сначала проверьте работу E-stop (топик `/emergency_stop_status`).

## 6. Известные ошибки в текущем коде (всплывут при переносе, лучше исправить сразу)

Не относятся к ROS 2, но в ROS 2 эти места упадут сразу:
- `dingo_driver.py`: `self.currently_estopped` не существует (должно быть `self.state.currently_estopped`) в `run_task_space_command` и `run_joint_space_command`.
- Там же: `for i in 3:` (нужно `range(3)`); `msg.FR_foot[j]` для `TaskSpace` это `Point` (индексировать нельзя, нужны `.x/.y/.z`), для `JointSpace` это `Angle` (поля `theta1..3`); `self.publish_joints_to_sim(self, joint_angles)` передаёт `self` дважды.
- Несовпадение имён топиков: `Controller` публикует `task_space_goals`/`joint_space_goals`, а драйвер подписан на `/task_space_cmd`/`/joint_space_cmd` (это может быть задумано как «цели» и «команды», но проверьте).
- `time.start = rospy.Time.now()` присваивает атрибут модулю `time`, а в ROS 2 `time` (Python) и `rclpy.time` легко перепутать; для замеров используйте `time.perf_counter()`.
- `package.xml` у `dingo` содержит `<depend>time</depend>`; такого rosdep-ключа нет, удалить.
- `README.md` и `Useful code commands.md` описывают Noetic/Pi: переписать после переноса (особенно разделы про I2C, serial, `catkin_make`).

## 7. Рекомендуемый порядок работы (по дням)

1. Ветка, Dockerfile Humble, пустая сборка (этап 1).
2. `dingo_msgs` и перенос пакетов на ament_python (этап 2).
3. Узел-драйвер на таймере + чистый Controller (этап 3) и joy (этап 4). Проверка «без железа»: подать `joy`, смотреть `joint_space_goals`.
4. Описание + rviz2 (этап 7, первая половина). Заодно визуально проверяется IK.
5. Gazebo + ros2_control (этап 7, вторая половина).
6. Накатить Ubuntu 22.04 на плату, настроить I2C/SPI/UART/GPIO (этап 5), проверить каждую периферию отдельным скриптом без ROS.
7. Мост для Nano (этап 6).
8. Объединить launch (этап 8), тесты на подставке, обновить README.

## 8. Полезные ссылки

- Миграция пакетов: https://docs.ros.org/en/humble/How-To-Guides/Migrating-from-ROS1.html
- Python-пакеты в ROS 2: https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Creating-Your-First-ROS2-Package.html
- Создание msg: https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- ros2_control + Gazebo Classic: https://control.ros.org/humble/index.html
- micro-ROS (поддерживаемые платы): https://micro.ros.org
