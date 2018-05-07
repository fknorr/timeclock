import sys
from os import path, makedirs
from argparse import ArgumentParser

import arrow
import appdirs

from . import stamp
from .stamp import Transition, Stamp
from . import config


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('transition', type=Transition.from_str,
                        help='Type of transition ' + '|'.join(map(str, Transition)))
    parser.add_argument('details', type=str, nargs='?', default='')
    parser.add_argument('-f', '--force', help='Allow out-of-order transitions')
    parser.add_argument('-t', '--at', type=arrow.get, default=arrow.utcnow(), help='Time of transition (default now)')
    parser.add_argument('-c', '--config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True), 'config.toml'))

    args = parser.parse_args()

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

