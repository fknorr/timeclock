from argparse import ArgumentParser
from datetime import timedelta
from enum import Enum, unique
from math import floor
from os import path

import appdirs
import arrow
from arrow import Arrow

from timeclock import config
from timeclock.stamp import iter_stamps, Stamp, Transition
from timeclock.schedule import Schedule


ascii_table = {
    'corner-top-left': '.',
    'corner-top-right': '.',
    'corner-bottom-left': "'",
    'corner-bottom-right': "'",
    'join-mid': '+',
    'join-top': '-',
    'join-bottom': '-',
    'join-left': '|',
    'join-right': '|',
    'inner-horizontal': '-',
    'inner-vertical': '|',
    'outer-horizontal': '-',
    'outer-vertical': '|',
    'working-state': '>>',
    'paused-state': '::',
}


box_table = {
    'corner-top-left': '\u250c',
    'corner-top-right': '\u2510',
    'corner-bottom-left': '\u2514',
    'corner-bottom-right': '\u2518',
    'join-mid': '\u253c',
    'join-top': '\u252c',
    'join-bottom': '\u2534',
    'join-left': '\u251c',
    'join-right': '\u2524',
    'inner-horizontal': '\u2500',
    'inner-vertical': '\u2502',
    'outer-horizontal': '\u2500',
    'outer-vertical': '\u2502',
    'working-state': '\u25b6',
    'paused-state': '\u23f8',
}


def fmt_hours(hours: float):
    h = floor(hours)
    m = floor(60 * (hours - h))
    return '{:02d}:{:02d} h'.format(int(h), int(m))


def fmt_timedelta(delta: timedelta):
    return fmt_hours(delta.total_seconds() / 3600)


@unique
class State(Enum):
    ABSENT = 0
    WORKING = 1
    PAUSING = 2


class WorkDay:
    def __init__(self):
        self.begin = None
        self.end = None
        self.pause_time = timedelta()
        self.tags = []
        self.invalid_transitions = False
        self.state = None

    def work_time(self, now: Arrow):
        if not self.begin:
            return timedelta()
        end = self.end if self.end is not None else now
        return (end - self.begin) - self.pause_time

    def consistent(self):
        return self.begin is not None and not self.invalid_transitions

    def complete(self):
        return self.consistent() and self.end is not None and self.state == State.ABSENT

    def columns(self, now: Arrow, table: dict):
        cols = []
        placeholder = '-?-'

        if self.begin:
            begin_time = self.begin.to('local')
            cols += [begin_time.format('ddd MMM DD'), begin_time.format('HH:mm')]
        else:
            cols += [placeholder, placeholder]

        if self.end:
            cols.append(self.end.to('local').format('HH:mm'))
        elif self.state == State.PAUSING:
            cols.append(table['paused-state'])
        elif self.state == State.WORKING:
            cols.append(table['working-state'])
        else:
            cols.append(placeholder)

        cols.append(fmt_timedelta(self.pause_time))

        if self.consistent():
            cols.append(fmt_timedelta(self.work_time(now)))
        else:
            cols.append(placeholder)

        return cols


def collect(stamps, now: Arrow):
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
            day.state = State.WORKING
        elif stamp.transition == Transition.OUT:
            day.end = stamp.time
            day.state = State.ABSENT
        elif stamp.transition == Transition.PAUSE:
            paused = stamp.time
            day.state = State.PAUSING
        elif stamp.transition == Transition.RESUME:
            if paused is not None:
                day.pause_time += stamp.time - paused
                paused = None
            day.state = State.WORKING

        if day is not None and stamp.details:
            day.tags.append(stamp.details)

        if stamp.transition == Transition.OUT:
            yield day
            day = None
        if stamp.transition != Transition.PAUSE:
            paused = None
        last_stamp = stamp

    if day is not None:
        assert day.end is None
        if paused is not None:
            day.pause_time += now - paused
        yield day


def pad_center(text, width):
    pad = width - len(text)
    pad_left = pad // 2
    return ' ' * pad_left + text + ' ' * (pad - pad_left)


def time_table(work_days: list, now: Arrow, table: dict):
    head = ['date', 'begin', 'end', 'pause', 'worked']
    cells = [d.columns(now, table) for d in work_days]
    column_widths = [max(map(len, c)) for c in zip(*([head] + cells))]

    def make_rule(left: str, dash: str, inner: str, right: str):
        return dash.join([left, (dash + inner + dash).join(w * dash for w in column_widths), right])

    rule = make_rule(table['join-left'], table['inner-horizontal'], table['join-mid'],
                     table['join-right'])

    def print_row(cells: [str]):
        inner = table['inner-vertical']
        outer = table['outer-vertical']
        print(outer, (' ' + inner + ' ').join(pad_center(*a) for a in zip(cells, column_widths)),
                    outer)

    print(make_rule(table['corner-top-left'], table['outer-horizontal'], table['join-top'],
                    table['corner-top-right']))
    print_row(head)
    print(rule)

    last_week = None
    week_work_time = timedelta()

    for day, row in zip(work_days, cells):
        this_week = day.begin.floor('week')
        if last_week is not None and last_week < this_week:
            print(rule)
            print_row(['week total', '', '', '', fmt_timedelta(week_work_time)])
            print(rule)
            week_work_time = timedelta()
        last_week = this_week
        week_work_time += day.work_time(now)
        print_row(row)

    print(rule)
    print_row(['week total', '', '', '', fmt_timedelta(week_work_time)])
    print(make_rule(table['corner-bottom-left'], table['outer-horizontal'], table['join-bottom'],
                    table['corner-bottom-right']))


def main():
    parser = ArgumentParser(description='Keep track of working hours')
    parser.add_argument('-c', '--config', metavar='config', type=str,
                        default=path.join(appdirs.user_config_dir('timeclock', roaming=True),
                                          'config.toml'))
    parser.add_argument('-n', '--weeks', type=int, default=1)

    args = parser.parse_args()

    cfg = config.load(args.config)
    now = arrow.utcnow()

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    stamps = []
    week = 0
    current_week = now.floor('week')
    for file in sorted(iter_stamps(stamp_dir), reverse=True):
        st = Stamp.load(file)
        if st.time.floor('week') != current_week:
            week += 1
            if week >= args.weeks:
                break
            current_week = st.time.floor('week')
        stamps.append(st)

    work_days = list(collect(reversed(stamps), now))

    if cfg['timesheet']['style'] == 'ascii':
        table = ascii_table
    else:
        table = box_table
    time_table(work_days, now, table)

    work_time = timedelta()
    if work_days:
        current_week = now.floor('week')
        for day in reversed(work_days):
            if day.begin is not None and day.begin.floor('week') != current_week:
                break

            work_time += day.work_time(now)

    schedule = Schedule()

    hours_worked = work_time.total_seconds() / 3600
    hours_required = float(schedule.hours_per_week)
    print('\nWorked {} of {} required ({:.0f}%).'.format(
        fmt_hours(hours_worked), fmt_hours(hours_required), 100 * hours_worked / hours_required),
        end=' ')

    if hours_worked < hours_required:
        print('{} to go this week.'.format(fmt_hours(hours_required - hours_worked)))
    elif hours_worked > hours_required:
        print('Made {} overtime this week.'.format(fmt_hours(hours_worked - hours_required)))
    else:
        print('Just on time!')

    if any(not d.consistent() for d in work_days):
        print('The timesheet is inconsistent. Maybe the file system is out of sync?')

    return 0


if __name__ == '__main__':
    main()
