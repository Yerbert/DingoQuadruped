from setuptools import setup

package_name = 'dingo_control'

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
    description='Gait, kinematics and stance/swing control logic for the Dingo quadruped',
    license='MIT',
    entry_points={
        'console_scripts': [],
    },
)
