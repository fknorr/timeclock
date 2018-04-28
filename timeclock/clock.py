import sys
from os import path, makedirs
from argparse import ArgumentParser

import arrow
import appdirs

from timeclock import stamp
from timeclock.stamp import Transition, Stamp
from timeclock.config import Config


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('transition', metavar='transition', type=Transition.from_str,
                        help='Type of transition ' + '|'.join(map(str, Transition)))
    parser.add_argument('details', metavar='details', type=str, nargs='?', default='')
    parser.add_argument('-f', '--force', help='Allow out-of-order transitions')
    parser.add_argument('-t', '--at', metavar='time', type=arrow.get, default=arrow.utcnow(),
                        help='Time of transition (default now)')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))

    args = parser.parse_args()

    try:
        config = Config.load(args.config)
    except FileNotFoundError:
        config = Config()

    stamp_dir = path.expanduser(config.stamps['dir'])
    makedirs(stamp_dir, exist_ok=True)

    this = Stamp.now(args.transition, args.details)
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

