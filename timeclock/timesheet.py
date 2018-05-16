import re
from argparse import ArgumentParser
from datetime import timedelta
from math import floor
from os import path

import appdirs
import arrow
from arrow import Arrow
from tabulate import tabulate

from . import config
from .stamp import iter_stamps, Stamp, Transition
from .schedule import Schedule


def collect(stamps):
    last_opening = None
    day_intervals = []
    last_transition = None
    for stamp in stamps:
        assert stamp.transition.may_follow(last_transition)

        if stamp.transition in [Transition.IN, Transition.RESUME]:
            last_opening = stamp.time
        else:
            day_intervals.append((last_opening, stamp.time))

        if stamp.transition == Transition.OUT:
            yield day_intervals
            day_intervals = []

        last_transition = stamp.transition

    if last_transition.is_opening():
        day_intervals.append((last_opening, None))

    if day_intervals:
        yield day_intervals


def fmt_hours(hours: float):
    h = floor(hours)
    m = floor(60 * (hours - h))
    return '{:02d}:{:02d} h'.format(int(h), int(m))


def fmt_timedelta(delta: timedelta):
    return fmt_hours(delta.total_seconds() / 3600)


def time_table(days: list, now: Arrow):
    last_week = None
    for day_intervals in days:
        begin, end = day_intervals[0][0], day_intervals[-1][-1]

        this_week = begin.floor('week')
        if last_week is not None and last_week < this_week:
            yield ['---'] * 5
        last_week = this_week

        work_time = sum(((e if e is not None else now) - b for b, e in day_intervals), timedelta())
        pause = ((end if end is not None else now) - begin) - work_time
        begin = begin.to('local')
        end_text = end.to('local').format('HH:mm') if end is not None else 'still working'
        yield [begin.format('ddd MMM DD'), begin.format('HH:mm'), end_text,
               fmt_timedelta(pause), fmt_timedelta(work_time)]


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

    days = list(collect(stamps))
    table = tabulate(time_table(days, now), disable_numparse=True, stralign='center',
                     tablefmt='orgtbl', headers=('date', 'begin', 'end', 'pause', 'worked'))
    rows = table.splitlines()
    line = '-' * (len(rows[0]) - 2)
    rows = [rows[1] if ' --- ' in r else r for r in rows]
    table = '\n'.join(['.' + line + '.'] + rows + ["'" + line + "'"])

    if stamps[-1].transition == Transition.PAUSE:
        table += ' (paused)'
    print(table)

    work_time = timedelta()

    if days:
        current_week = now.floor('week')
        for day_intervals in reversed(days):
            if day_intervals[0][0].floor('week') != current_week:
                break

            work_time += sum(((e if e is not None else now) - b for b, e in day_intervals),
                             timedelta())

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

    return 0


if __name__ == '__main__':
    main()
