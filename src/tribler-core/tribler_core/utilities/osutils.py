"""
OS-independent utility functions.

The function get_home_dir returns CSIDL_APPDATA i.e. App data directory on win32.

Author(s): Arno Bakker
"""

import errno
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def is_android():
    """
    This functions checks whether Tribler is running on Android or not,
    using the system platform name and OS environment variable ANDROID_PRIVATE

    :return: boolean True if running on Android. False otherwise.
    """
    return sys.platform.startswith('linux') and 'ANDROID_PRIVATE' in os.environ


if sys.platform == "win32":
    try:
        from win32com.shell import shell, shellcon

        def get_home_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_PROFILE = &H28
            # C:\Documents and Settings\username
            return Path(shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_PROFILE))

        def get_appstate_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_APPDATA = &H1A
            # C:\Documents and Settings\username\Application Data
            return Path(shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_APPDATA))

        def get_picture_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_MYPICTURES = &H27
            # C:\Documents and Settings\username\My Documents\My Pictures
            return Path(shell.SHGetSpecialFolderPath(0, 0x27))

        def get_desktop_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_DESKTOPDIRECTORY = &H10
            # C:\Documents and Settings\username\Desktop
            return Path(shell.SHGetSpecialFolderPath(0, 0x10))

    except ImportError:
        def get_home_dir():
            # This will always succeed on python 3.x
            return Path("~").expanduser()

        def get_appstate_dir():
            homedir = get_home_dir()
            # 5 = XP, 6 = Vista
            # [E1101] Module 'sys' has no 'getwindowsversion' member
            # pylint: disable-msg=E1101
            winversion = sys.getwindowsversion()
            # pylint: enable-msg=E1101
            if winversion[0] == 6:
                appdir = homedir / "AppData/Roaming"
            else:
                appdir = homedir / "Application Data"
            return appdir

        def get_picture_dir():
            return get_home_dir()

        def get_desktop_dir():
            return get_home_dir() / "Desktop"

elif is_android():

    def get_home_dir():
        return Path(os.environ['EXTERNAL_STORAGE']).resolve()

    def get_appstate_dir():
        return Path(os.environ['ANDROID_PRIVATE'], '../.Tribler').resolve()

    def get_picture_dir():
        return get_home_dir() / 'DCIM'

    def get_desktop_dir():
        return get_home_dir()

else:
    # linux or darwin (mac)
    def get_home_dir():
        return Path("~").expanduser()

    def get_appstate_dir():
        return get_home_dir()

    def get_picture_dir():
        return get_desktop_dir()

    def get_desktop_dir():
        home = get_home_dir()
        desktop = get_home_dir() / "Desktop"
        return desktop if desktop.exists() else home


def _invalid_windows_file_chars():
    invalid_chars = [chr(i) for i in range(32)]
    invalid_chars.append('"*/:<>?\\|')
    return ''.join(invalid_chars)


invalid_win_file_name_chars = _invalid_windows_file_chars()
invalid_linux_file_name_chars = '/'


def fix_filebasename(name, unit=False, maxlen=255):
    """ Check if str is a valid Windows file name (or unit name if unit is true)
     * If the filename isn't valid: returns a corrected name
     * If the filename is valid: returns the filename
    """
    if isinstance(name, Path):
        name = str(name)
    if unit and (len(name) != 2 or name[1] != ':'):
        return 'c:'
    if not name or name in ('.', '..'):
        return '_'

    if unit:
        name = name[0]
    fixed = False
    if len(name) > maxlen:
        name = name[:maxlen]
        fixed = True

    invalid_chars = invalid_win_file_name_chars if sys.platform.startswith('win') else invalid_linux_file_name_chars
    fixed_name = []
    spaces = 0
    for c in name:
        if c in invalid_chars:
            fixed_name.append('_')
            fixed = True
        else:
            fixed_name.append(c)
            if c == ' ':
                spaces += 1
    fixed_name = ''.join(fixed_name)

    file_dir, basename = os.path.split(fixed_name)
    while file_dir != '':
        fixed_name = basename
        file_dir, basename = os.path.split(fixed_name)
        fixed = True

    if fixed_name == '':
        fixed_name = '_'
        fixed = True

    if fixed:
        return last_minute_filename_clean(fixed_name)
    if spaces == len(name):
        # contains only spaces
        return '_'
    return last_minute_filename_clean(name)


def last_minute_filename_clean(name):
    # Arno: remove initial or ending space
    s = name.strip()
    if sys.platform == 'win32' and s.endswith('..'):
        s = s[:-2]
    return s


def startfile(filepath):
    if sys.platform == 'darwin':
        subprocess.call(('open', filepath))
    elif sys.platform == 'linux2':
        subprocess.call(('xdg-open', filepath))
    elif hasattr(os, "startfile"):
        os.startfile(filepath)


def dir_copy(src_dir, dest_dir):
    try:
        shutil.copytree(src_dir, dest_dir)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src_dir, dest_dir)
        else:
            logging.error("Directory %s could not be imported", src_dir)
