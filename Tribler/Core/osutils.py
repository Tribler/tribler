# Written by Arno Bakker, ABC authors
# see LICENSE.txt for license information
"""
OS-independent utility functions

get_home_dir()      : Returns CSIDL_APPDATA i.e. App data directory on win32
get_picture_dir()
get_free_space(path)
"""

#
# Multiple methods for getting free diskspace
#
import sys
import os
import time
import binascii
import subprocess
import logging

logger = logging.getLogger(__name__)

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
            try:
                # when there are special unicode characters in the username,
                # the following will fail on python 2.4, 2.5, 2.x this will
                # always succeed on python 3.x
                return os.path.expanduser(u"~")
            except Exception as unicode_error:
                pass

            # non-unicode home
            home = os.path.expanduser("~")
            head, tail = os.path.split(home)

            dirs = os.listdir(head)
            udirs = os.listdir(unicode(head))

            # the character set may be different, but the string length is
            # still the same
            islen = lambda dir: len(dir) == len(tail)
            dirs = filter(islen, dirs)
            udirs = filter(islen, udirs)
            if len(dirs) == 1 and len(udirs) == 1:
                return os.path.join(head, udirs[0])

            # remove all dirs that are equal in unicode and non-unicode. we
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
        return GetDiskFreeSpaceEx(path)[0]
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


def get_readable_torrent_name(infohash, raw_filename):
    # return name__infohash.torrent
    hex_infohash = binascii.hexlify(infohash)
    suffix = '__' + hex_infohash + '.torrent'
    save_name = ' ' + fix_filebasename(raw_filename, maxlen=254 - len(suffix)) + suffix
    # use a space ahead to distinguish from previous collected torrents
    return save_name


if sys.platform == "win32":
    import win32pdh

    def getcpuload():
        """ Returns total CPU usage as fraction (0..1).
        Warning: side-effect: sleeps for 0.1 second to do diff """
        # mempath = win32pdh.MakeCounterPath((None, "Memory", None, None, -1, "Available MBytes"))
        cpupath = win32pdh.MakeCounterPath((None, "Processor", "_Total", None, -1, "% Processor Time"))
        query = win32pdh.OpenQuery(None, 0)
        counter = win32pdh.AddCounter(query, cpupath, 0)

        win32pdh.CollectQueryData(query)
        # Collect must be called twice for CPU, see http://support.microsoft.com/kb/262938
        time.sleep(0.1)
        win32pdh.CollectQueryData(query)

        status, value = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_LONG)

        return float(value) / 100.0

elif sys.platform == "linux2":
    def read_proc_stat():
        """ Read idle and total CPU time counters from /proc/stat, see
        man proc """
        f = open("/proc/stat", "rb")
        try:
            while True:
                line = f.readline()
                if len(line) == 0:
                    break
                if line.startswith("cpu "):  # note space
                    words = line.split()
                    total = 0
                    for i in range(1, 5):
                        total += int(words[i])
                    idle = int(words[4])
                    return (total, idle)
        finally:
            f.close()

    def getcpuload():
        """ Returns total CPU usage as fraction (0..1).
        Warning: side-effect: sleeps for 0.1 second to do diff """
        (total1, idle1) = read_proc_stat()
        time.sleep(0.1)
        (total2, idle2) = read_proc_stat()
        total = total2 - total1
        idle = idle2 - idle1
        return 1.0 - (float(idle)) / float(total)
else:
    # Mac
    def getupload():
        raise ValueError("Not yet implemented")


def startfile(filepath):
    if sys.platform == 'darwin':
        subprocess.call(('open', filepath))
    elif sys.platform == 'linux2':
        subprocess.call(('xdg-open', filepath))
    elif hasattr(os, "startfile"):
        os.startfile(filepath)


def is_android(strict=False):
    """
    This functions checks whether Tribler is running on Android or not, using the ANDROID_HOST environment variable.
    When Tribler is launched on Android, this variable is set to "ANDROID-99" where 99 is the current SDK version.

    :param strict: Check if ANDROID_HOST actually starts with "ANDROID". This can be useful for code that must
    absolutely only run on Android, and not on a computer testing the Android specific code.
    :return: Whether this is Android or not.
    """

    # This is not an Android device at all
    if not 'ANDROID_HOST' in os.environ:
        return False

    # No strict mode: always return true when ANDROID_HOST is defined
    if not strict:
        return True
    # Strict mode: actually check whether the variable starts with "ANDROID"
    elif os.environ['ANDROID_HOST'].startswith("ANDROID"):
        return True
    # Strict mode, but the variable doesn't start with "ANDROID"
    else:
        return False
