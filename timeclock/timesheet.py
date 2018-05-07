from argparse import ArgumentParser
from datetime import timedelta
from os import path

import appdirs
import arrow
from tabulate import tabulate

from . import config
from .stamp import iter_stamps, Stamp, Transition


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


def time_table(stamp_dir: str):
    for day_intervals in collect(map(Stamp.load, sorted(iter_stamps(stamp_dir)))):
        begin, end = day_intervals[0][0], day_intervals[-1][-1]
        now = arrow.now()
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

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    print(tabulate(time_table(stamp_dir), headers=('date', 'begin', 'pause', 'end', 'time worked')))

    return 0


if __name__ == '__main__':
    main()
