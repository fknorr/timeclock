import toml
import appdirs
from os import path


DEFAULT_CONFIG = {
    'stamps': {
        'dir': path.join(appdirs.user_data_dir('timeclock', roaming=True), 'stamps'),
    }
}


class Config(dict):
    def __init__(self):
        super().__init__()
        self.__dict__.update(DEFAULT_CONFIG)

    @classmethod
    def load(cls, file_name: str):
        return toml.load(file_name, cls)

