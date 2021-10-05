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

from tribler_core.utilities import path_util

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
            return path_util.Path(shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_PROFILE))

        def get_appstate_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_APPDATA = &H1A
            # C:\Documents and Settings\username\Application Data
            return path_util.Path(shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_APPDATA))

        def get_picture_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_MYPICTURES = &H27
            # C:\Documents and Settings\username\My Documents\My Pictures
            return path_util.Path(shell.SHGetSpecialFolderPath(0, 0x27))

        def get_desktop_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_DESKTOPDIRECTORY = &H10
            # C:\Documents and Settings\username\Desktop
            return path_util.Path(shell.SHGetSpecialFolderPath(0, 0x10))

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
                appdir = homedir / "AppData" / "Roaming"
            else:
                appdir = homedir / "Application Data"
            return appdir

        def get_picture_dir():
            return get_home_dir()

        def get_desktop_dir():
            home = get_home_dir()
            return home / "Desktop"


elif is_android():

    def get_home_dir():
        return Path(str(os.environ['EXTERNAL_STORAGE'])).resolve()

    def get_appstate_dir():
        return Path(os.environ['ANDROID_PRIVATE'] / '../.Tribler').resolve()

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
        desktop = home / "Desktop"
        return desktop if desktop.exists() else home


invalidwinfilenamechars = ''
for i in range(32):
    invalidwinfilenamechars += chr(i)
invalidwinfilenamechars += '"*/:<>?\\|'
invalidlinuxfilenamechars = '/'


def fix_filebasename(name, unit=False, maxlen=255):
    """Check if str is a valid Windows file name (or unit name if unit is true)
    * If the filename isn't valid: returns a corrected name
    * If the filename is valid: returns the filename
    """
    if isinstance(name, Path):
        name = str(name)
    if unit and (len(name) != 2 or name[1] != ':'):
        return 'c:'
    if not name or name == '.' or name == '..':
        return '_'

    if unit:
        name = name[0]
    fixed = False
    if len(name) > maxlen:
        name = name[:maxlen]
        fixed = True

    fixedname = ''
    spaces = 0
    for c in name:
        if sys.platform.startswith('win'):
            invalidchars = invalidwinfilenamechars
        else:
            invalidchars = invalidlinuxfilenamechars

        if c in invalidchars:
            fixedname += '_'
            fixed = True
        else:
            fixedname += c
            if c == ' ':
                spaces += 1

    file_dir, basename = os.path.split(fixedname)
    while file_dir != '':
        fixedname = basename
        file_dir, basename = os.path.split(fixedname)
        fixed = True

    if fixedname == '':
        fixedname = '_'
        fixed = True

    if fixed:
        return last_minute_filename_clean(fixedname)
    elif spaces == len(name):
        # contains only spaces
        return '_'
    else:
        return last_minute_filename_clean(name)


def last_minute_filename_clean(name):
    s = name.strip()  # Arno: remove initial or ending space
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


def dir_copy(src_dir, dest_dir, merge_if_exists=True):
    try:
        if not os.path.exists(dest_dir):
            shutil.copytree(src_dir, dest_dir)
        elif merge_if_exists:
            merge_dir(src_dir, dest_dir)
    except OSError as e:
        # If source is not a directory, copy with shutil.copy
        if e.errno == errno.ENOTDIR:
            shutil.copy(src_dir, dest_dir)
        else:
            logging.error("Could not copy %s to %s", src_dir, dest_dir)


def merge_dir(src_dir, dest_dir):
    for src_sub_dir, _, files in os.walk(src_dir):
        dest_sub_dir = src_sub_dir.replace(str(src_dir), str(dest_dir), 1)
        if not os.path.exists(dest_sub_dir):
            os.makedirs(dest_sub_dir)
        for _file in files:
            src_file = os.path.join(src_sub_dir, _file)
            dst_file = os.path.join(dest_sub_dir, _file)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.copy(src_file, dest_sub_dir)


def get_root_state_directory(home_dir_postfix='.Tribler'):
    """Get the default application state directory."""
    if 'TSTATEDIR' in os.environ:
        path = os.environ['TSTATEDIR']
        return Path(path) if os.path.isabs(path) else Path(os.getcwd(), path)
    return Path(get_appstate_dir(), home_dir_postfix)
