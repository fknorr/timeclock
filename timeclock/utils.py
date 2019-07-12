import argparse

import arrow

from .stamp import Transition


class ArgumentParser(argparse.ArgumentParser):
    def _parse_transition(self, transition: str):
        try:
            return Transition.from_str(transition)
        except KeyError:
            self.error('Unknown transition {}. Allowed values are {}'.format(
                transition, ' '.join('"{}"'.format(t) for t in Transition)))

    def _parse_date(self, date: str):
        import dateparser
        dt = dateparser.parse(date, languages=['en'], settings={
            'RETURN_AS_TIMEZONE_AWARE': True,
            'PREFER_DAY_OF_MONTH': 'first',
        })
        if dt is None:
            self.error('Invalid date format "{}". Try something like "11:40" or "2 hours ago"'
                       .format(date))
        return arrow.Arrow.fromdatetime(dt)

