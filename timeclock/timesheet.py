from argparse import ArgumentParser
from os import path
from datetime import timedelta

from tabulate import tabulate

from timeclock.config import Config
import appdirs

from timeclock.stamp import iter_stamps, Stamp, Transition


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


def time_table(stamp_dir: str):
    for day_intervals in collect(map(Stamp.load, sorted(iter_stamps(stamp_dir)))):
        begin, end = day_intervals[0][0], day_intervals[-1][-1]
        work_time = sum((e - b for b, e in day_intervals), timedelta())
        pause = (end - begin) - work_time
        yield (begin.date(), begin.time(), pause, end.time(), work_time)


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))

    args = parser.parse_args()

    try:
        config = Config.load(args.config)
    except FileNotFoundError:
        config = Config()

    stamp_dir = path.expanduser(config['stamps']['dir'])
    print(tabulate(time_table(stamp_dir), headers=('date', 'begin', 'pause', 'end', 'time worked')))

    return 0

