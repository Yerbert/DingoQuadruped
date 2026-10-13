from setuptools import setup

package_name = 'dingo_servo_interfacing'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_dir={'': 'src'},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='alex',
    maintainer_email='alex@todo.todo',
    description='PCA9685 servo driver interface and servo calibration for Dingo',
    license='MIT',
    entry_points={
        'console_scripts': [],
    },
)
