import operator
from argparse import ArgumentParser
from enum import unique, Enum, auto
from os import path
from sys import stdin

import appdirs
from icalendar import Calendar, Event


@unique
class Action(Enum):
    IMPORT_HOLIDAYS = auto()

    def __str__(self):
        return self.name.lower().replace('_', '-')

    @classmethod
    def from_str(cls, s: str):
        return cls[s.replace('-', '_').upper()]


def import_ical(file):
    cal = Calendar.from_ical(file.read())
    holidays = []
    for component in cal.subcomponents:
        if isinstance(component, Event):
            holidays.append((component['DTSTART'].dt, component['DTEND'].dt, component['SUMMARY']))
    for start, end, summary in sorted(holidays, key=operator.itemgetter(0)):
        print(start, end, summary)


def with_file(file_name: str, func):
    if file_name == '-':
        return func(stdin)
    else:
        with open(file_name) as file:
            return func(file)


def main():
    parser = ArgumentParser(description='Manage timeclock working day and holiday schedule')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))
    parser.add_argument('action', metavar='action', type=Action.from_str, help='|'.join(map(str, Action)))
    parser.add_argument('-f', '--file', metavar='file', type=str, default='-',
                        help='calendar file name (defaults to stdin)')

    args = parser.parse_args()

    if args.action == Action.IMPORT_HOLIDAYS:
        with_file(args.file, import_ical)


if __name__ == '__main__':
    main()