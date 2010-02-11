# Written by Arno Bakker, ABC authors
# see LICENSE.txt for license information
"""
OS-independent utility functions

get_home_dir()      : Returns CSIDL_APPDATA i.e. App data directory on win32
get_picture_dir()
getfreespace(path)
"""
    
#
# Multiple methods for getting free diskspace
#
import sys
import os
import binascii

if sys.platform == "win32":
    try:
        from win32com.shell import shell
        def get_home_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_PROFILE = &H28
            # C:\Documents and Settings\username
            return shell.SHGetSpecialFolderPath(0, 0x28)

        def get_appstate_dir():
            # http://www.mvps.org/access/api/api0054.htm
            # CSIDL_APPDATA = &H1A
            # C:\Documents and Settings\username\Application Data
            return shell.SHGetSpecialFolderPath(0, 0x1a)

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
            except Exception, unicode_error:
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
                appdir = os.path.join(homedir,u"AppData",u"Roaming")
            else:
                appdir = os.path.join(homedir,u"Application Data")
            return appdir

        def get_picture_dir():
            return get_home_dir()

        def get_desktop_dir():
            home = get_home_dir()
            return os.path.join(home,u"Desktop")
            
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

if sys.version.startswith("2.4"):
    os.SEEK_SET = 0
    os.SEEK_CUR = 1
    os.SEEK_END = 2

try:
    # Unix
    from os import statvfs
    import statvfs
    def getfreespace(path):
        s = os.statvfs(path.encode("utf-8"))
        size = s[statvfs.F_BAVAIL] * long(s[statvfs.F_BSIZE])
        return size
except:
    if (sys.platform == 'win32'):
        try:
            # Windows if win32all extensions are installed
            import win32file
            try:
                # Win95 OSR2 and up
                # Arno: this code was totally broken as the method returns
                # a list of values indicating 1. free space for the user,
                # 2. total space for the user and 3. total free space, so
                # not a single value.
                win32file.GetDiskFreeSpaceEx(".")
                def getfreespace(path):
                    # Boudewijn: the win32file module is NOT unicode
                    # safe! We will try directories further up the
                    # directory tree in the hopes of getting a path on
                    # the same disk without the unicode...
                    while True:
                        try:
                            return win32file.GetDiskFreeSpaceEx(path)[0]
                        except:
                            path = os.path.split(path)[0]
                            if not path:
                                raise
            except:                
                # Original Win95
                # (2GB limit on partition size, so this should be
                #  accurate except for mapped network drives)
                # Arno: see http://aspn.activestate.com/ASPN/docs/ActivePython/2.4/pywin32/win32file__GetDiskFreeSpace_meth.html
                def getfreespace(path):
                    [spc, bps, nfc, tnc] = win32file.GetDiskFreeSpace(path)
                    return long(nfc) * long(spc) * long(bps)
                    
        except ImportError:
            # Windows if win32all extensions aren't installed
            # (parse the output from the dir command)
            def getfreespace(path):
                try:
                    mystdin, mystdout = os.popen2(u"dir " + u"\"" + path + u"\"")
                    
                    sizestring = "0"
                
                    for line in mystdout:
                        line = line.strip()
                        # Arno: FIXME: this won't work on non-English Windows, as reported by the IRT
                        index = line.rfind("bytes free")
                        if index > -1 and line[index:] == "bytes free":
                            parts = line.split(" ")
                            if len(parts) > 3:
                                part = parts[-3]
                                part = part.replace(",", "")
                                sizestring = part
                                break

                    size = long(sizestring)                    
                    
                    if size == 0L:
                        print >>sys.stderr,"getfreespace: can't determine freespace of ",path
                        for line in mystdout:
                            print >>sys.stderr,line
                            
                        size = 2**80L
                except:
                    # If in doubt, just return something really large
                    # (1 yottabyte)
                    size = 2**80L
                
                return size
    else:
        # Any other cases
        # TODO: support for Mac? (will statvfs work with OS X?)
        def getfreespace(path):
            # If in doubt, just return something really large
            # (1 yottabyte)
            return 2**80L


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
    s = name.strip() # Arno: remove initial or ending space
    if sys.platform == 'win32' and s.endswith('..'):
        s = s[:-2]
    return s


def get_readable_torrent_name(infohash, raw_filename):
    # return name__infohash.torrent
    hex_infohash = binascii.hexlify(infohash)
    suffix = '__' + hex_infohash + '.torrent'
    save_name = ' ' + fix_filebasename(raw_filename, maxlen=254-len(suffix)) + suffix
    # use a space ahead to distinguish from previous collected torrents
    return save_name

