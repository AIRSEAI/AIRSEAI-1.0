from glob import glob
from setuptools import setup
import os

package_name = 'airseai_navigation'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/airseai_navigation']),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='airseai',
    maintainer_email='airseai@cuhk.edu.cn',
    description='Python package for airseai navigation API using custom navigation service',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'navigation_service_node = airseai_navigation.navigation_service_node:main',
        ],
    },
)
