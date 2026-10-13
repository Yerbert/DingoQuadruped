from glob import glob

from setuptools import setup

package_name = 'dingo_peripheral_interfacing'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_dir={'': 'src'},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('lib/' + package_name, ['scripts/battery_voltage_checking.py', 'scripts/dingo_lcd_interfacing.py', 'scripts/LCD_1inch47.py', 'scripts/lcdconfig.py']),
        ('share/dingo_peripheral_interfacing/lib', ['lib/emptybatterystatus_white.png']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='alex',
    maintainer_email='alex@todo.todo',
    description='IMU, LCD display and battery monitoring for Dingo',
    license='MIT',
    entry_points={
        'console_scripts': [
            'arduino_bridge = dingo_peripheral_interfacing.arduino_bridge:main',
        ],
    },
)
