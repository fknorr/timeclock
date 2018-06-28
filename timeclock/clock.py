import sys
from os import path, makedirs
import argparse
import dateparser

import arrow
import appdirs

from . import stamp
from .stamp import Transition, Stamp
from . import config


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(description='Keep track of working hours')
        self.add_argument('transition', type=Transition.from_str,
                            help='Type of transition ' + '|'.join(map(str, Transition)))
        self.add_argument('details', type=str, nargs='?', default='')
        self.add_argument('-f', '--force', default=False, action='store_true', help='Allow out-of-order transitions')
        self.add_argument('-t', '--at', type=self._parse_date, default=arrow.now(),
                            help='Time of transition (default now)')
        self.add_argument('-c', '--config', type=str,
                            default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))

    def _parse_date(self, date: str):
        dt = dateparser.parse(date)
        if dt is None:
            self.error('Invalid date format "{}". Try something like "11:40" or "2 hours ago"'.format(date))
        return arrow.Arrow.fromdatetime(dt)


def main():
    args = ArgumentParser().parse_args()
    cfg = config.load(args.config)

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    makedirs(stamp_dir, exist_ok=True)

    this = Stamp(args.transition, args.at, args.details)
    last = stamp.most_recent(stamp_dir)

    if this.may_follow(last):
        this.write(stamp_dir)
        return 0
    else:
        if last is not None:
            print('"{}" transition cannot follow "{}" transition'.format(this.transition, last.transition),
                  file=sys.stderr)
        else:
            print('First stamp must be an "in" transition', file=sys.stderr)
        return 1


if __name__ == '__main__':
    main()
