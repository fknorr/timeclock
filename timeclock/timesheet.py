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

    def columns(self, now: Arrow):
        cols = []

        def col_if(condition: bool, fmt):
            if condition:
                string = fmt()
            elif not self.consistent():
                string = '-?-'
            else:
                string = ''
            cols.append(string)

        col_if(self.begin, lambda: self.begin.to('local').format('ddd MMM DD'))
        col_if(self.begin, lambda: self.begin.to('local').format('HH:mm'))
        col_if(self.end, lambda: self.end.to('local').format('HH:mm'))
        cols.append(fmt_timedelta(self.pause_time))
        col_if(self.consistent(), lambda: fmt_timedelta(self.work_time(now)))

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


def time_table(work_days: list, now: Arrow):
    head = ['date', 'begin', 'end', 'pause', 'worked']
    cells = [d.columns(now) for d in work_days]
    column_widths = [max(map(len, c)) for c in zip(*([head] + cells))]

    def make_rule(outer_sep: str, inner_sep: str):
        return '-'.join([outer_sep, ('-' + inner_sep + '-').join(w * '-' for w in column_widths),
                         outer_sep])

    rule = make_rule('|', '+')

    def print_row(cells: [str], note: str or None=None):
        tail = [note] if note is not None else []
        print('|', ' | '.join(pad_center(*a) for a in zip(cells, column_widths)), '|', *tail)

    print(make_rule('.', '-'))
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

        note = None
        if day.consistent():
            if day.state == State.PAUSING:
                note = '(paused)'
            elif day.state == State.WORKING:
                note = '(still working)'
        print_row(row, note)

    print(rule)
    print_row(['week total', '', '', '', fmt_timedelta(week_work_time)])
    print(make_rule("'", '-'))


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
    time_table(work_days, now)

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
        print('Made {} overtime this week.'.format(fmt_hours(work_time - hours_required)))
    else:
        print('Just on time!')

    if any(not d.consistent() for d in work_days):
        print('The timesheet is inconsistent. Maybe the file system is out of sync?')

    return 0


if __name__ == '__main__':
    main()
