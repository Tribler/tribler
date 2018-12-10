"""
OS-independent utility functions.

The function get_home_dir returns CSIDL_APPDATA i.e. App data directory on win32.

Author(s): Arno Bakker
"""

from __future__ import absolute_import

import logging
import os
import subprocess
import sys

from six import text_type

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
            return shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_PROFILE)

        def get_appstate_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_APPDATA = &H1A
            # C:\Documents and Settings\username\Application Data
            return shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_APPDATA)

        def get_picture_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_MYPICTURES = &H27
            # C:\Documents and Settings\username\My Documents\My Pictures
            return shell.SHGetSpecialFolderPath(0, 0x27)

        def get_desktop_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_DESKTOPDIRECTORY = &H10
            # C:\Documents and Settings\username\Desktop
            return shell.SHGetSpecialFolderPath(0, 0x10)

    except ImportError:
        def get_home_dir():
            unicode_error = None  # forward declare for Python 3 scoping rules
            try:
                # when there are special unicode characters in the username,
                # the following will fail on python 2.4, 2.5, 2.x this will
                # always succeed on python 3.x
                return os.path.expanduser(u"~")
            except Exception as unicode_error:
                pass

            # non-Unicode home
            home = os.path.expanduser("~")
            head, tail = os.path.split(home)

            dirs = os.listdir(head)
            udirs = os.listdir(text_type(head))

            # the character set may be different, but the string length is
            # still the same
            islen = lambda dir: len(dir) == len(tail)
            dirs = filter(islen, dirs)
            udirs = filter(islen, udirs)
            if len(dirs) == 1 and len(udirs) == 1:
                return os.path.join(head, udirs[0])

            # remove all dirs that are equal in Unicode and non-Unicode. we
            # know that we don't need these dirs because the initial
            # expandusers would not have failed on them
            for dir in dirs[:]:
                if dir in udirs:
                    dirs.remove(dir)
                    udirs.remove(dir)
            if len(dirs) == 1 and len(udirs) == 1:
                return os.path.join(head, udirs[0])

            # assume that the user has write access in her own
            # directory. therefore we can filter out any non-writable
            # directories
            writable_udir = [udir for udir in udirs if os.access(udir, os.W_OK)]
            if len(writable_udir) == 1:
                return os.path.join(head, writable_udir[0])

            # fallback: assume that the order of entries in dirs is the same
            # as in udirs
            for dir, udir in zip(dirs, udirs):
                if dir == tail:
                    return os.path.join(head, udir)

            # failure
            raise unicode_error

        def get_appstate_dir():
            homedir = get_home_dir()
            # 5 = XP, 6 = Vista
            # [E1101] Module 'sys' has no 'getwindowsversion' member
            # pylint: disable-msg=E1101
            winversion = sys.getwindowsversion()
            # pylint: enable-msg=E1101
            if winversion[0] == 6:
                appdir = os.path.join(homedir, u"AppData", u"Roaming")
            else:
                appdir = os.path.join(homedir, u"Application Data")
            return appdir

        def get_picture_dir():
            return get_home_dir()

        def get_desktop_dir():
            home = get_home_dir()
            return os.path.join(home, u"Desktop")

elif is_android():

    def get_home_dir():
        return os.path.realpath(text_type(os.environ['EXTERNAL_STORAGE']))

    def get_appstate_dir():
        return os.path.realpath(os.path.join(text_type(os.environ['ANDROID_PRIVATE']), u'../.Tribler'))

    def get_picture_dir():
        return os.path.join(get_home_dir(), u'DCIM')

    def get_desktop_dir():
        return get_home_dir()

else:
    # linux or darwin (mac)
    def get_home_dir():
        return os.path.expanduser(u"~")

    def get_appstate_dir():
        return get_home_dir()

    def get_picture_dir():
        return get_desktop_dir()

    def get_desktop_dir():
        home = get_home_dir()
        desktop = os.path.join(home, "Desktop")
        if os.path.exists(desktop):
            return desktop
        else:
            return home


def get_free_space(path):
    if not os.path.exists(path):
        return -1

    if sys.platform == 'win32':
        from win32file import GetDiskFreeSpaceEx
        return GetDiskFreeSpaceEx(os.path.splitdrive(os.path.abspath(path))[0])[0]
    else:
        data = os.statvfs(path.encode("utf-8"))
        return data.f_bavail * data.f_frsize


invalidwinfilenamechars = ''
for i in range(32):
    invalidwinfilenamechars += chr(i)
invalidwinfilenamechars += '"*/:<>?\\|'
invalidlinuxfilenamechars = '/'


def fix_filebasename(name, unit=False, maxlen=255):
    """ Check if str is a valid Windows file name (or unit name if unit is true)
     * If the filename isn't valid: returns a corrected name
     * If the filename is valid: returns the filename
    """
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
