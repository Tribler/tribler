    
#
# Multiple methods for getting free diskspace
#
try:
    # Unix
    from os import statvfs
    import statvfs
    def getfreespace(path):
        s = os.statvfs(path)
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
                        print "getfreespace: can't determine freespace of ",path
                        print "0?"
                        for line in mystdout:
                            print line
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
