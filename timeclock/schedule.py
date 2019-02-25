import csv
import operator
from argparse import ArgumentParser
from enum import unique, Enum, auto, IntEnum
import os
from sys import stdin, stderr

import appdirs
import arrow
import toml
from arrow import Arrow
from icalendar import Calendar, Event

from timeclock import config


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

    def import_holidays(self, file):
        cal = Calendar.from_ical(file.read())

        for component in cal.subcomponents:
            if not isinstance(component, Event):
                continue

            try:
                start, end = (Arrow.fromdate(component[k].dt).floor('day') for k in ['dtstart', 'dtend'])
                summary = None
                try:
                    summary = str(component['summary'])
                except KeyError:
                    pass

                recurring = False
                if 'rrule' in component:
                    freq = component['rrule']['freq'][0]
                    if freq == 'YEARLY':
                        recurring = True
                    else:
                        print('unsupported recurrence ' + freq, file=stderr)

                self.holidays += [(d.date(), recurring, summary) for d in days_in_range(start, end)]
            except KeyError or IndexError:
                print('Skipping incomplete vCalendar event', file=stderr)

    def write(self, f):
        toml.dump({
            'working-days': self.working_days,
            'hours-per-week': self.hours_per_week,
            'holidays': [
                {'date': d, 'recurring': r, 'summary': s} for d, r, s in self.holidays
            ],
        }, f)

    @classmethod
    def load(cls, f):
        instance = cls()
        d = toml.load(f)

        try:
            instance.working_days = d['working-days']
        except KeyError:
            pass

        try:
            instance.hours_per_week = d['hours-per-week']
        except KeyError:
            pass

        try:
            for h in d['holidays']:
                instance.holidays.append((h['date'], h['recurring'], h['summary']))
        except KeyError:
            pass

        return instance


def with_file(file_name: str, func):
    if file_name == '-':
        return func(stdin)
    else:
        with open(file_name) as file:
            return func(file)


def main():
    parser = ArgumentParser(description='Manage timeclock working day and holiday schedule')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=os.path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))
    parser.add_argument('action', metavar='action', type=Action.from_str, nargs='?', help='|'.join(map(str, Action)))
    parser.add_argument('-f', '--file', metavar='file', type=str, default='-',
                        help='calendar file name (defaults to stdin)')

    args = parser.parse_args()
    cfg = config.load(args.config)

    schedule = Schedule()

    schedule_file = cfg['schedule']['file']
    try:
        with open(schedule_file, 'r') as f:
            schedule.load(f)
    except FileNotFoundError:
        pass

    if args.action == Action.IMPORT_HOLIDAYS:
        with_file(args.file, schedule.import_holidays)
        os.makedirs(os.path.dirname(schedule_file), exist_ok=True)
        with open(schedule_file, 'w') as f:
            schedule.write(f)
    else:
        for entry in Schedule().holidays:
            print(*entry)


if __name__ == '__main__':
    main()
