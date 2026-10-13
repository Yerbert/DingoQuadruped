from glob import glob

from setuptools import setup

package_name = 'dingo'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    package_dir={'': 'src'},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='alex',
    maintainer_email='alex@todo.todo',
    description='Main Dingo driver node and top-level launch files',
    license='MIT',
    entry_points={
        'console_scripts': [
            'dingo_driver = dingo.dingo_driver:main',
        ],
    },
)
