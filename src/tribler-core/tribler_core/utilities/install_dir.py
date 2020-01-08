"""
install_dir.

Author(s): Elric Milon
"""
import sys

import tribler_core
from tribler_core.utilities.path_util import Path


def is_frozen():
    """
    Return whether we are running in a frozen environment
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        sys._MEIPASS
    except Exception:
        return False
    return True


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(tribler_core.__file__).parent
    return base_path


def get_lib_path():
    if is_frozen():
        return get_base_path() / 'tribler_source' / 'tribler_core'
    return get_base_path()
