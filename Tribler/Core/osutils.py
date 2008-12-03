# Written by Arno Bakker, ABC authors
# see LICENSE.txt for license information
""" OS-independent utility functions """
    
#
# Multiple methods for getting free diskspace
#
import sys
import os
import binascii

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
                test = win32file.GetDiskFreeSpaceEx(".")
                def getfreespace(path):          
                    list = win32file.GetDiskFreeSpaceEx(path)
                    return list[0]
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
                    mystdin, mystdout = os.popen2("dir " + "\"" + path + "\"")
                    
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

