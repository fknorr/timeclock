#!/usr/bin/env python3
import os
import re

from setuptools import setup, find_packages


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    with open('timeclock/__init__.py', 'r') as file:
        version = re.search(r"^__version__\s*=\s*'(.*)'", file.read(), re.M).group(1)

    with open('README', 'rb') as f:
        long_descr = f.read().decode('utf-8')

    setup(
        name='timeclock',
        version=version,
        packages=find_packages(),
        install_requires=[
            'icalendar',
            'toml',
            'arrow',
            'appdirs',
            'tabulate',
        ],
        entry_points={
            'console_scripts': [
                'clock = timeclock.clock:main',
                'timesheet = timeclock.timesheet:main',
                'schedule = timeclock.schedule:main',
            ],
        },
        long_description=long_descr,
        url='https://github.com/fknorr/timeclock',
        license='MIT',
        author='Fabian Knorr',
        author_email='git@fabian-knorr.info',
        description='Keep track of working hours with simple shell commands',
    )


if __name__ == "__main__":
    main()
