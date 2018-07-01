import re
from argparse import ArgumentParser
from datetime import timedelta
from math import floor
from os import path

import appdirs
import arrow
from arrow import Arrow
from tabulate import tabulate

from timeclock import config
from timeclock.stamp import iter_stamps, Stamp, Transition
from timeclock.schedule import Schedule


def fmt_hours(hours: float):
    h = floor(hours)
    m = floor(60 * (hours - h))
    return '{:02d}:{:02d} h'.format(int(h), int(m))


def fmt_timedelta(delta: timedelta):
    return fmt_hours(delta.total_seconds() / 3600)


class WorkDay:
    def __init__(self):
        self.begin = None
        self.end = None
        self.pause_time = timedelta()
        self.tags = []
        self.invalid_transitions = False

    @property
    def work_time(self):
        if self.begin and self.end:
            return (self.end - self.begin) - self.pause_time
        else:
            return timedelta()

    def consistent(self):
        return self.begin is not None and not self.invalid_transitions

    def complete(self):
        return self.consistent() and self.end is not None

    def columns(self):
        cols = []

        def col_if(condition: bool, fmt):
            cols.append(fmt() if condition else '')

        col_if(self.begin, lambda: self.begin.format('ddd MMM DD'))
        col_if(self.begin, lambda: self.begin.format('HH:mm'))
        col_if(self.end, lambda: self.end.format('HH:mm'))
        cols.append(fmt_timedelta(self.pause_time))
        col_if(self.begin and self.end, lambda: fmt_timedelta(self.work_time))

        return cols


def collect(stamps):
    day = None
    paused = None
    last_stamp = None
    for stamp in stamps:
        if day is None or stamp.transition == Transition.IN:
            if day is not None:
                day.invalid_transitions = True
                yield day
            day = WorkDay()

        if stamp.transition != Transition.IN and not stamp.may_follow(last_stamp):
            day.invalid_transitions = True

        if stamp.transition == Transition.IN:
            day.begin = stamp.time
        elif stamp.transition == Transition.OUT:
            day.end = stamp.time
        elif stamp.transition == Transition.PAUSE:
            paused = stamp.time
        elif stamp.transition == Transition.RESUME:
            if paused is not None:
                day.pause_time += stamp.time - paused
                paused = None

        if day is not None and stamp.details:
            day.tags.append(stamp.details)

        if stamp.transition == Transition.OUT:
            yield day
            day = None
        if stamp.transition != Transition.PAUSE:
            paused = None
        last_stamp = stamp


def time_table(work_days: list):
    last_week = None
    week_work_time = timedelta()

    for day in work_days:
        this_week = day.begin.floor('week')
        if last_week is not None and last_week < this_week:
            yield ['---'] * 5
            yield ['week total', '', '', '', fmt_timedelta(week_work_time)]
            yield ['---'] * 5
            week_work_time = timedelta()
        last_week = this_week
        week_work_time += day.work_time

        yield day.columns()

    yield ['---'] * 5
    yield ['week total', '', '', '', fmt_timedelta(week_work_time)]


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True),
                                          'config.toml'))

    args = parser.parse_args()

    cfg = config.load(args.config)
    now = arrow.utcnow()

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    stamps = [Stamp.load(s) for s in sorted(iter_stamps(stamp_dir))]

    work_days = list(collect(stamps))
    table = tabulate(time_table(work_days, now), disable_numparse=True, stralign='center',
                     tablefmt='orgtbl', headers=('date', 'begin', 'end', 'pause', 'worked'))
    rows = table.splitlines()
    line = '-' * (len(rows[0]) - 2)
    rows = [rows[1] if ' --- ' in r else r for r in rows]
    table = '\n'.join(['.' + line + '.'] + rows + ["'" + line + "'"])

    if stamps[-1].transition == Transition.PAUSE:
        table += ' (paused)'
    print(table)

    work_time = timedelta()
    inconsistent = False

    if work_days:
        current_week = now.floor('week')
        for day in reversed(work_days):
            if day.begin is not None and day.begin.floor('week') != current_week:
                break
            if not day.consistent():
                inconsistent = True

            work_time += day.work_time

    schedule = Schedule()

    hours_worked = work_time.total_seconds() / 3600
    hours_required = float(schedule.hours_per_week)
    print('\nWorked {} of {} required ({:.0f}%).'.format(
        fmt_hours(hours_worked), fmt_hours(hours_required), 100 * hours_worked / hours_required),
        end=' ')

    if hours_worked < hours_required:
        print('{} to go this week.'.format(fmt_hours(hours_required - hours_worked)))
    elif hours_worked > hours_required:
        print('Made {} overtime this week.'.format(fmt_hours(work_time - hours_required)))
    else:
        print('Just on time!')

    if inconsistent:
        print('The timesheet for this week is inconsistent. Maybe the file system is out of sync?')

    return 0


if __name__ == '__main__':
    main()
