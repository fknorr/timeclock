from argparse import ArgumentParser
from datetime import timedelta
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
        yield day_intervals


def time_table(days: list, now: Arrow):
    for day_intervals in days:
        begin, end = day_intervals[0][0], day_intervals[-1][-1]
        work_time = sum(((e if e is not None else now) - b for b, e in day_intervals), timedelta())
        pause = ((end if end is not None else now) - begin) - work_time
        begin = begin.to('local')
        end = end.to('local').time() if end is not None else 'still working'
        yield (begin.date(), begin.time(), pause, end, work_time)


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))

    args = parser.parse_args()

    cfg = config.load(args.config)
    now = arrow.now()

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    days = list(collect(map(Stamp.load, sorted(iter_stamps(stamp_dir)))))

    print(tabulate(time_table(days, now), headers=('date', 'begin', 'pause', 'end', 'time worked')))

    work_time = timedelta()

    if days:
        current_week = days[-1][0][0].floor('week')
        for day_intervals in reversed(days):
            if day_intervals[0][0].floor('week') != current_week:
                break

            work_time += sum(((e if e is not None else now) - b for b, e in day_intervals), timedelta())

    schedule = Schedule()

    hours_required = timedelta(hours=schedule.hours_per_week)
    print('\nWorked {} of {} required ({:.0f}%)'.format(work_time, hours_required, 100 * work_time / hours_required))

    if work_time < hours_required:
        print('{} to go.'.format(hours_required - work_time))
    elif work_time > hours_required:
        print('Made {} overtime.'.format(work_time - hours_required))
    else:
        print('Just on time!')

    return 0


if __name__ == '__main__':
    main()
