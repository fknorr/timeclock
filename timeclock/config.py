import toml
import appdirs
import os
from os import path


DEFAULT_CONFIG = {
    'stamps': {
        'dir': path.join(appdirs.user_data_dir('timeclock', roaming=True), 'stamps'),
    }
}


def load(file_name: str):
    cfg = DEFAULT_CONFIG.copy()
    try:
        cfg.update(toml.load(file_name))
    except FileNotFoundError:
        os.makedirs(path.dirname(file_name), exist_ok=True)
        with open(file_name, 'w') as f:
            toml.dump(cfg, f)

    return cfg
