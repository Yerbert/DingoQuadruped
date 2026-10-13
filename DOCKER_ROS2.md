# План: ROS 2 Humble в Docker на Ubuntu 24.04 и сборка проекта Dingo

Хост: Ubuntu 24.04 (Wayland), Docker 29.9 уже установлен. Humble нативно на 24.04 не ставится (там Jazzy), поэтому Humble идёт в контейнере на базе Ubuntu 22.04. Один и тот же образ потом собирается на плате (arm64).

## Шаг 0. Подготовка хоста (один раз)

1. Проверить Docker и права без sudo:
   ```bash
   docker run --rm hello-world
   ```
   Если «permission denied»: `sudo usermod -aG docker $USER`, затем выйти из сессии и зайти снова.
2. Проверить compose v2: `docker compose version` (команда с пробелом, не `docker-compose`).
3. GUI (rviz2, Gazebo) из контейнера. Сессия у вас Wayland, но XWayland есть, поэтому используем X11:
   ```bash
   xhost +local:docker      # разрешить контейнеру подключаться к X-серверу; повторять после перезагрузки
   echo $DISPLAY            # обычно :0 или :1
   ```
   Для NVIDIA GPU понадобится `nvidia-container-toolkit`; для Intel/AMD достаточно проброса `/dev/dri`.

## Шаг 1. Dockerfile (заменить текущий)

Основа: `osrf/ros:humble-desktop-full` (22.04, содержит rviz2 и Gazebo Classic). Что поменять относительно нынешнего Dockerfile:

- `FROM osrf/ros:humble-desktop-full`; строку с `ros-latest.list` удалить.
- apt-пакеты вместо Noetic-набора:
  ```
  python3-colcon-common-extensions python3-rosdep python3-vcstool python3-pip
  ros-humble-xacro ros-humble-robot-state-publisher ros-humble-joint-state-publisher-gui
  ros-humble-joy ros-humble-ros2-control ros-humble-ros2-controllers
  ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros2-control
  ros-humble-rmw-cyclonedds-cpp
  i2c-tools python3-smbus python3-libgpiod gdb nano git build-essential
  ```
- pip: `transforms3d pyserial pynput spidev adafruit-circuitpython-servokit adafruit-circuitpython-bno055 matplotlib numpy`. Пакеты `serial`, `UDPComms`, `pigpio`, `regex` убрать (в коде не нужны). `RPi.GPIO` не ставить (на Rockchip не работает).
- Сборка: `colcon build --symlink-install` вместо `catkin_make`.
- В `/etc/bash.bashrc`: `source /opt/ros/humble/setup.bash` и `source /dingo_ws/install/setup.bash` (если есть).
- `ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`.
- `ENTRYPOINT`/`ros_entrypoint.sh` без изменений.

Важно: пока код не перенесён (этапы 2–3 плана), `colcon build` внутри `docker build` будет падать. Поэтому на время разработки **не собирайте проект на этапе `docker build`**. Образ содержит только окружение, а сборка идёт вручную внутри контейнера в смонтированном `dingo_ws`. Добавьте сборку в Dockerfile, когда пакеты уже собираются.

Также не копируйте `dingo_ws/src` в образ (`COPY`) на время разработки: рабочая папка монтируется томом, и копия лишь устареет.

## Шаг 2. Docker-compose.yaml

Изменения:

```yaml
services:
  dingoquadruped:
    image: dingo_ros2:humble
    build: {context: ., dockerfile: ./Dockerfile}
    network_mode: host            # нужно для DDS-обнаружения
    privileged: true              # доступ к /dev/i2c, spi, tty на плате
    environment:
      - DISPLAY=${DISPLAY}
      - QT_X11_NO_MITSHM=1
      - ROS_DOMAIN_ID=42
      - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    volumes:
      - ./dingo_ws:/dingo_ws
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    devices:
      - /dev/dri:/dev/dri         # GPU для rviz2/Gazebo (Intel/AMD)
    command: sleep infinity
```

- Строку `devices: - /dev:/dev` на ноутбуке лучше убрать: она лишняя и небезопасная. Оставляйте её (и `privileged`) только в варианте для платы, где нужны I2C/SPI/UART. Удобно сделать второй файл `Docker-compose.board.yaml`.
- Для геймпада на ноутбуке добавьте `- /dev/input:/dev/input`.
- `version: '3.4'` в compose v2 не нужна, можно удалить.
- `.devcontainer.json` менять не надо (ссылается на сервис `dingoquadruped`).

## Шаг 3. Сборка и запуск

```bash
cd ~/DingoQuadruped
git checkout ros2
docker compose build            # первый раз 10–20 минут (скачивается ~3–4 ГБ)
docker compose up -d
docker compose exec dingoquadruped bash
```

Проверка окружения внутри контейнера:
```bash
printenv ROS_DISTRO             # humble
ros2 --help
ros2 run demo_nodes_cpp talker  # в другом терминале: ros2 run demo_nodes_py listener
```
Проверка GUI (на хосте перед этим сделан `xhost +local:docker`):
```bash
rviz2
gazebo --verbose                # или ros2 launch gazebo_ros gazebo.launch.py
```
Если окно не открывается: проверьте `echo $DISPLAY` внутри контейнера и повторите `xhost`. Если Gazebo падает с ошибкой GL, запустите с программным рендерингом: `LIBGL_ALWAYS_SOFTWARE=1`.

## Шаг 4. Сборка проекта Dingo внутри контейнера

Выполняется после переноса кода (см. этапы 2–3 в `MIGRATION_ROS2.md`):
```bash
cd /dingo_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```
Полезно:
- `colcon build --packages-select dingo_msgs` — собрать один пакет, сначала сообщения.
- `colcon build --cmake-clean-cache` или удалить `build/ install/ log/` при странных ошибках.
- Старые `build/`, `devel/` от catkin из `dingo_ws` удалить (они в `.gitignore`).
- Права: папки `build/ install/ log/` создаст root из контейнера. Либо запускать контейнер с `user: "${UID}:${GID}"`, либо иногда делать `sudo chown -R $USER:$USER dingo_ws` на хосте.

## Шаг 5. Тестирование без железа

1. Тест математики без ROS: `python3 -c "import dingo_control..."` или `pytest` для Kinematics/Gaits.
2. `ros2 launch dingo dingo.launch.py is_physical:=0` + `ros2 topic echo /joint_space_goals`.
3. Подача команд без геймпада: `ros2 topic pub /joy sensor_msgs/msg/Joy "{axes: [0,0,0,0,0,0,0,0], buttons: [0,0,0,0,0,0]}" -r 30`.
4. rviz2 и Gazebo — как в шаге 3.

## Шаг 6. Перенос на плату (arm64)

- Вариант А: на плате тоже Docker. Установить Docker Engine на её Ubuntu 22.04, клонировать ветку `ros2`, использовать `Docker-compose.board.yaml` (`privileged`, `/dev`). Образ `osrf/ros:humble-desktop-full` есть под arm64, но тяжёлый (≈4 ГБ); для робота лучше `ros:humble-ros-base` + нужные пакеты, GUI там не нужен.
- Вариант Б: на плате нативно `ros-humble-ros-base` (22.04), без Docker. Меньше накладных расходов и проще доступ к I2C/SPI/GPIO.
- Кросс-сборка с ноутбука: `docker buildx build --platform linux/arm64` (нужен `qemu-user-static`: `sudo apt install qemu-user-static binfmt-support`). Работает, но медленно.

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| `cannot connect to X server` | не выполнен `xhost +local:docker` или не передан `DISPLAY`/сокет X11 |
| Узлы с хоста и контейнера не видят друг друга | разный `ROS_DOMAIN_ID` или `RMW_IMPLEMENTATION`; у хоста 24.04 может быть Jazzy — общаться через ROS 2 между Jazzy и Humble обычно можно, но лучше всё запускать в контейнерах |
| Файлы в `dingo_ws` принадлежат root | см. шаг 4, запуск контейнера под своим UID |
| Долгий `rosdep install` | нормально при первом запуске; можно закрепить зависимости в Dockerfile |
| Нет доступа к I2C/SPI/UART на плате | не `privileged` или не проброшены `/dev/i2c-*`, `/dev/spidev*`, `/dev/ttyS*`; пользователь не в группах `i2c`, `dialout` |
