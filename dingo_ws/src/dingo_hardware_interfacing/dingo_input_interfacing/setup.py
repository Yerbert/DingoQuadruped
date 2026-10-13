from setuptools import setup

package_name = 'dingo_input_interfacing'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_dir={'': 'src'},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('lib/' + package_name, ['scripts/Keyboard.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='alex',
    maintainer_email='alex@todo.todo',
    description='Joystick and keyboard input handling for Dingo',
    license='MIT',
    entry_points={
        'console_scripts': [],
    },
)
