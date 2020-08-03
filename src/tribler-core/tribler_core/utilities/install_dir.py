"""
install_dir.

Author(s): Elric Milon
"""
import sys

from tribler_common.utilities import is_frozen

import tribler_core
from tribler_core.utilities.path_util import Path, str_path


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(tribler_core.__file__).parent
    return Path(str_path(base_path))


def get_lib_path():
    if is_frozen():
        return get_base_path() / 'tribler_source' / 'tribler_core'
    return get_base_path()
