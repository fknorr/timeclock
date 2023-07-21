from datetime import timedelta
from enum import Enum, unique
from math import floor
from os import path

import appdirs
import arrow
from arrow import Arrow

from timeclock import config, tablefmt, utils
from timeclock.schedule import Schedule
from timeclock.stamp import iter_stamps, Stamp, Transition
from timeclock.tablefmt import Table, Column


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
        self.date = None
        self.begin = None
        self.end = None
        self.pause_time = timedelta()
        self.tags = []
        self.invalid_transitions = False
        self.state = None

    def work_time(self, now: Arrow):
        if not self.consistent():
            return timedelta()
        end = self.end if self.end is not None else now
        return (end - self.begin) - self.pause_time

    def consistent(self):
        return self.begin is not None and not self.invalid_transitions

    def complete(self):
        return self.consistent() and self.end is not None and self.state == State.ABSENT

    def columns(self, now: Arrow, table: dict):
        cols = [self.date.to('local').format('ddd MMM DD')]

        if self.begin:
            cols.append(self.begin.to('local').format('HH:mm'))
        else:
            cols.append(table['placeholder'])

        if self.end:
            cols.append(self.end.to('local').format('HH:mm'))
        elif not self.consistent():
            cols.append(table['placeholder'])
        elif self.state == State.PAUSING:
            cols.append(table['paused-state'])
        else:
            assert self.state == State.WORKING
            cols.append(table['working-state'])

        cols.append(fmt_timedelta(self.pause_time))

        if self.consistent():
            cols.append(fmt_timedelta(self.work_time(now)))
        else:
            cols.append(table['placeholder'])

        cols.append(', '.join(self.tags))

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

        if day.date is None:
            day.date = stamp.time.floor('day')

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


def time_table(work_days: list, now: Arrow, style: dict):
    table = Table([Column.CENTER, Column.CENTER, Column.CENTER, Column.CENTER, Column.CENTER,
                   Column.LEFT])
    table.row(['date', 'begin', 'end', 'pause', 'worked', 'tags'])
    table.rule()

    last_week = None
    week_work_time = timedelta()
    week_time_is_lower_bound = False

    def print_total():
        week_time_str = fmt_timedelta(week_work_time)
        if week_time_is_lower_bound:
            week_time_str = week_time_str[:-2] + '+h'

        table.rule()
        table.row(['week total', '', '', '', week_time_str, ''])

    cells = [d.columns(now, style) for d in work_days]
    for day, row in zip(work_days, cells):
        this_week = day.date.floor('week')
        if last_week is not None and last_week < this_week:
            print_total()
            table.rule()
            week_work_time = timedelta()
            week_time_is_lower_bound = False

        last_week = this_week
        week_work_time += day.work_time(now)
        if not day.consistent():
            week_time_is_lower_bound = True

        table.row(row)

    print_total()
    table.print(style)


def week_table(style: dict, stamps: [Stamp], now: Arrow, schedule: Schedule):
    work_days = list(collect(reversed(stamps), now))

    time_table(work_days, now, style)

    work_time = timedelta()
    if work_days:
        current_week = now.floor('week')
        for day in reversed(work_days):
            if day.date.floor('week') != current_week:
                break

            work_time += day.work_time(now)

    if schedule.hours_per_week is not None:
        hours_worked = work_time.total_seconds() / 3600
        hours_required = float(schedule.hours_per_week)
        print('\nWorked {} of {} required ({:.0f}%).'.format(
            fmt_hours(hours_worked), fmt_hours(hours_required),
            100 * hours_worked / hours_required), end=' ')

        if hours_worked < hours_required:
            print('{} to go this week.'.format(fmt_hours(hours_required - hours_worked)))
        elif hours_worked > hours_required:
            print('Made {} overtime this week.'.format(fmt_hours(hours_worked - hours_required)))
        else:
            print('Just on time!')

    if any(not d.consistent() for d in work_days):
        print('The time sheet is inconsistent. Maybe the file system is out of sync?')


def stamp_table(style: dict, stamps: [Stamp]):
    table = Table([Column.LEFT, Column.LEFT, Column.LEFT, Column.LEFT, Column.LEFT])
    table.row(['date', 'time', 'stamp', 'transition', 'tag'])
    table.rule()

    last_day = None
    first_stamp_today = True
    for stamp in reversed(stamps):
        local_time = stamp.time.to('local')
        day = local_time.floor('day')
        if last_day is not None and day != last_day:
            table.rule()
            first_stamp_today = True

        date = ''
        if first_stamp_today:
            date = local_time.format('ddd MMM DD')

        table.row([date, local_time.format('HH:mm'), stamp.time.int_timestamp, stamp.transition, stamp.details])

        last_day = day
        first_stamp_today = False

    table.print(style)


class ArgumentParser(utils.ArgumentParser):
    def __init__(self):
        super().__init__(description='Keep track of working hours')
        self.add_argument('-c', '--config', metavar='config', type=str,
                          default=path.join(appdirs.user_config_dir('timeclock', roaming=True),
                                            'config.toml'))
        self.add_argument('--stamps', default=False, action='store_true', help='Show individual stamps')

        scope = self.add_mutually_exclusive_group()
        scope.add_argument('-n', '--weeks', type=int)
        scope.add_argument('--since', type=self._parse_date)


def main():
    args = ArgumentParser().parse_args()

    cfg = config.load(args.config)
    now = arrow.utcnow()

    if args.since is not None:
        since = args.since
    elif args.weeks is not None:
        since = (now - timedelta(weeks=args.weeks - 1)).floor('week')
    else:
        since = now.floor('week')

    stamp_dir = path.expanduser(cfg['stamps']['dir'])
    stamps = []
    for file in sorted(iter_stamps(stamp_dir), reverse=True):
        st = Stamp.load(file)
        if st.time < since:
            break
        stamps.append(st)

    if cfg['timesheet']['style'] == 'ascii':
        table = tablefmt.ASCII_STYLE
    else:
        table = tablefmt.BOX_STYLE

    if args.stamps:
        stamp_table(table, stamps)
    else:
        schedule_file = cfg['schedule']['file']
        try:
            with open(schedule_file, 'r') as f:
                schedule = Schedule.load(f)
        except FileNotFoundError:
            schedule = Schedule()

        week_table(table, stamps, now, schedule)

    return 0


if __name__ == '__main__':
    main()
