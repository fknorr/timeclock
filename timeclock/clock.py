import sys
from argparse import ArgumentParser

from timeclock import stamp
from timeclock.stamp import Transition, Stamp


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('transition', metavar='transition', type=Transition.from_str,
                        help='|'.join(map(str, Transition)))
    parser.add_argument('details', metavar='details', type=str, nargs='?', default='')

    args = parser.parse_args()

    this = Stamp.now(args.transition, args.details)
    last = stamp.most_recent('/tmp/stamps')

    if this.may_follow(last):
        this.write('/tmp/stamps')
        return 0
    else:
        if last is not None:
            print('"{}" transition cannot follow "{}" transition'.format(this.transition, last.transition),
                  file=sys.stderr)
        else:
            print('First stamp must be an "in" transition', file=sys.stderr)
        return 1

