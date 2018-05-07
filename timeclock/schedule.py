import csv
import datetime
import operator
from argparse import ArgumentParser
from enum import unique, Enum, auto, IntEnum
from os import path
from sys import stdin, stderr

import appdirs
import arrow
from arrow import Arrow
from icalendar import Calendar, Event


@unique
class Action(Enum):
    IMPORT_HOLIDAYS = auto()

    def __str__(self):
        return self.name.lower().replace('_', '-')

    @classmethod
    def from_str(cls, s: str):
        return cls[s.replace('-', '_').upper()]


def days_in_range(start: Arrow, end: Arrow):
    date = start
    while date < end:
        yield date
        date = date.shift(days=1)


def import_holidays(file):
    cal = Calendar.from_ical(file.read())
    holidays = []

    for component in cal.subcomponents:
        if not isinstance(component, Event):
            continue

        try:
            start, end = (Arrow.fromdate(component[k].dt).floor('day') for k in ['dtstart', 'dtend'])
            summary = component.get('summary', default=None)

            recurring = False
            if 'rrule' in component:
                freq = component['rrule']['freq'][0]
                if freq == 'YEARLY':
                    recurring = True
                else:
                    print('unsupported recurrence ' + freq, file=stderr)

            holidays += [(d.date(), recurring, summary) for d in days_in_range(start, end)]
        except KeyError or IndexError:
            print('Skipping incomplete vCalendar event', file=stderr)

    with open('/tmp/holidays.csv', 'w', newline='') as table:
        writer = csv.writer(table, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for entry in sorted(holidays, key=operator.itemgetter(0)):
            writer.writerow(entry)


@unique
class Weekday(IntEnum):
    MON = 0
    TUE = 1
    WED = 2
    THU = 3
    FRI = 4
    SAT = 5
    SUN = 6


class Schedule:
    def __init__(self):
        self.working_days = list(range(0, 5))
        self.hours_per_week = 40
        self.holidays = []

        try:
            with open('/tmp/holidays.csv', 'r') as table:
                reader = csv.reader(table, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for date, recurring, summary in reader:
                    self.holidays.append((arrow.get(date), recurring == 'True', summary))
        except FileNotFoundError:
            pass

    def is_work_day(self, day: Arrow):
        day = day.floor('day')
        if day.weekday() not in self.working_days:
            return False
        for date, recurring, _ in self.holidays:
            if (not recurring and day == date) or (recurring and day == date.replace(year=day.year)):
                return False
        return True

    def working_hours_in_week(self, day: Arrow):
        working_days = sum(1 for d in Arrow.range('day', day.floor('week'), day.ceil('week')) if self.is_work_day(d))
        return self.hours_per_week / len(self.working_days) * working_days


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
    parser.add_argument('action', metavar='action', type=Action.from_str, nargs='?', help='|'.join(map(str, Action)))
    parser.add_argument('-f', '--file', metavar='file', type=str, default='-',
                        help='calendar file name (defaults to stdin)')

    args = parser.parse_args()

    if args.action == Action.IMPORT_HOLIDAYS:
        with_file(args.file, import_holidays)
    else:
        for entry in Schedule().holidays:
            print(*entry)


if __name__ == '__main__':
    main()