"""
install_dir.

Author(s): Elric Milon
"""
import sys

import tribler
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import is_frozen


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller/cx_freeze"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(getattr(sys, '_MEIPASS'))
    except AttributeError:
        if getattr(sys, 'frozen', False):  # cx_freeze
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(tribler.__file__).parent

    fixed_filename = Path.fix_win_long_file(base_path)
    return Path(fixed_filename)


def get_core_path():
    if is_frozen():
        return get_base_path() / 'tribler_source/tribler/core'
    return get_base_path() / 'core'
