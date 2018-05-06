import operator
from argparse import ArgumentParser
from enum import unique, Enum, auto
from os import path
from sys import stdin, stderr

import appdirs
import arrow
from arrow import Arrow
from icalendar import Calendar, Event
import csv


@unique
class Action(Enum):
    IMPORT_HOLIDAYS = auto()

    def __str__(self):
        return self.name.lower().replace('_', '-')

    @classmethod
    def from_str(cls, s: str):
        return cls[s.replace('-', '_').upper()]


def import_holidays(file):
    cal = Calendar.from_ical(file.read())
    holidays = []

    for component in cal.subcomponents:
        if not isinstance(component, Event):
            continue

        try:
            start, end = [Arrow.fromdate(component[k].dt).floor('day') for k in ['dtstart', 'dtend']]

            recurring = False
            if 'rrule' in component:
                freq = component['rrule']['freq'][0]
                if freq == 'YEARLY':
                    recurring = True
                else:
                    print('unsupported recurrence ' + freq, file=stderr)

            days = []
            date = start
            while True:
                days.append(date)
                date = date.shift(days=1)
                if date >= end:
                    break

            holidays += [(d.date(), recurring, component.get('summary', default=None)) for d in days]
        except KeyError or IndexError:
            print('Skipping incomplete vCalendar event', file=stderr)

    with open('/tmp/holidays.csv', 'w', newline='') as table:
        writer = csv.writer(table, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for entry in sorted(holidays, key=operator.itemgetter(0)):
            writer.writerow(entry)


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
        with_file(args.file, import_holidays)


if __name__ == '__main__':
    main()