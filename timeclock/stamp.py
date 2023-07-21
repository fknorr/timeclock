import re
from enum import Enum, unique, auto
from os import path, listdir, remove

import arrow
from arrow import Arrow


@unique
class Transition(Enum):
    IN = auto()
    OUT = auto()
    PAUSE = auto()
    RESUME = auto()
    TAG = auto()

    def __str__(self):
        return self.name.lower()

    @classmethod
    def from_str(cls, s: str):
        return cls[s.upper()]

    def may_follow(self, other: 'Transition' or None):
        if self == Transition.IN:
            return other in [Transition.OUT, None]
        elif self in [Transition.OUT, Transition.PAUSE]:
            return other in [Transition.IN, Transition.RESUME, Transition.TAG]
        elif self == Transition.RESUME:
            return other in [Transition.PAUSE]
        elif self == Transition.TAG:
            return other not in [Transition.OUT, None]

    def is_opening(self):
        return self in [Transition.IN, Transition.RESUME, Transition.TAG]


class Stamp:
    FILE_NAME_RE = re.compile(r'^(\d+)\.stamp$')
    STAMP_FILE_RE = re.compile(r'^\s*([A-Za-z]+)\s*:\s*(.*?)\s*$')

    def __init__(self, transition: Transition, time: Arrow, details: str=''):
        self.transition = transition
        self.time = time
        self.details = details.strip()

    @classmethod
    def now(cls, transition: Transition, details: str=''):
        return cls(transition, arrow.utcnow(), details)

    def may_follow(self, other: 'Stamp' or None):
        if other is None:
            return self.transition.may_follow(None)
        else:
            return self.transition.may_follow(other.transition) and self.time > other.time

    @classmethod
    def load(cls, file_name: str):
        name_part = cls.FILE_NAME_RE.match(path.basename(file_name))
        if not name_part:
            raise ValueError('Invalid stamp file name')
        time = Arrow.fromtimestamp(int(name_part.group(1)))

        with open(file_name, 'r') as file:
            info = cls.STAMP_FILE_RE.match(file.read())
        if not info:
            raise ValueError('Invalid data in stamp file')

        return cls(Transition.from_str(info.group(1)), time, info.group(2))

    @classmethod
    def is_valid_file_name(cls, file_name: str):
        return cls.FILE_NAME_RE.match(path.basename(file_name)) is not None

    def write(self, directory: str):
        file_name = path.join(directory, '{}.stamp'.format(self.time.int_timestamp))
        with open(file_name, 'w') as file:
            file.write('{}:{}\n'.format(str(self.transition), self.details))

    def __repr__(self):
        return 'Stamp({}, {}, {})'.format(repr(self.transition), repr(self.time), repr(self.details))


def iter_stamps(directory: str):
    for entry in listdir(directory):
        full_name = path.join(directory, entry)
        if path.isfile(full_name) and Stamp.is_valid_file_name(full_name):
            yield full_name


def most_recent(directory: str):
    stamp_files = list(iter_stamps(directory))
    if stamp_files:
        return Stamp.load(max(stamp_files))
    return None


def remove_at(directory: str, time: Arrow):
    remove(path.join(directory, '{}.stamp'.format(time.int_timestamp)))
