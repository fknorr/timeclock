import sys
from os import path, makedirs
import argparse

import arrow
import appdirs

from timeclock import stamp
from timeclock.stamp import Transition, Stamp
from timeclock import config


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(description='Keep track of working hours')
        self.add_argument('transition', type=self._parse_transition,
                            help='Type of transition ' + '|'.join(map(str, Transition)))
        self.add_argument('details', type=str, nargs='?', default=None)
        self.add_argument('-f', '--force', default=False, action='store_true',
                          help='Allow out-of-order transitions')
        self.add_argument('-t', '--at', type=self._parse_date, default=arrow.now(),
                            help='Time of transition (default now)')
        self.add_argument('-c', '--config', type=str,
                            default=path.join(appdirs.user_config_dir('timeclock', roaming=True),
                                              'config.toml'))
        self.add_argument('-e', '--replace', default=False, action='store_true',
                          help='Modify last stamp')
        self.add_argument('-r', '--remove', default=False, action='store_true',
                          help='Remove latest stamp')

    def _parse_transition(self, transition: str):
        try:
            return Transition.from_str(transition)
        except KeyError:
            self.error('Unknown transition {}. Allowed values are {}'.format(
                transition, ' '.join('"{}"'.format(t) for t in Transition)))

    def _parse_date(self, date: str):
        import dateparser
        dt = dateparser.parse(date, languages=['en'], settings={'RETURN_AS_TIMEZONE_AWARE': True})
        if dt is None:
            self.error('Invalid date format "{}". Try something like "11:40" or "2 hours ago"'
                       .format(date))
        return arrow.Arrow.fromdatetime(dt)


def main():
    args = ArgumentParser().parse_args()
    cfg = config.load(args.config)

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    makedirs(stamp_dir, exist_ok=True)

    last = stamp.most_recent(stamp_dir)

    if args.replace:
        if last is None:
            print('No stamp to modify', file=sys.stderr)
            return 1
        details = args.details if args.details is not None else last.details
        Stamp(args.transition, last.time, details).write(stamp_dir)
    elif args.remove:
        if last is None:
            print('No stamp to remove', file=sys.stderr)
            return 1
        stamp.remove_at(stamp_dir, last.time)
    else:
        details = args.details if args.details is not None else ''
        this = Stamp(args.transition, args.at, details)
        if args.force or this.may_follow(last):
            this.write(stamp_dir)
        else:
            if last is not None:
                print('"{}" transition cannot follow "{}" transition'.format(
                    this.transition, last.transition), file=sys.stderr)
            else:
                print('First stamp must be an "in" transition', file=sys.stderr)
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
