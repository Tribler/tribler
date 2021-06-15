"""
install_dir.

Author(s): Elric Milon
"""
import sys

from tribler_common.utilities import is_frozen

import tribler_core
from tribler_core.utilities.path_util import Path


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(tribler_core.__file__).parent

    fixed_filename = Path.fix_win_long_file(base_path)
    return Path(fixed_filename)


def get_lib_path():
    if is_frozen():
        return get_base_path() / 'tribler_source' / 'tribler_core'
    return get_base_path()
