from setuptools import setup, find_packages

setup(
    name='timeclock',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'icalendar',
        'toml',
        'arrow'
    ],
    url='https://github.com/fknorr/timeclock',
    license='MIT',
    author='Fabian Knorr',
    author_email='git@fabian-knorr.info',
    description='Keep track of working hours with simple shell commands'
)
