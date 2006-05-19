import wx
import sys
import os
import socket

from threading import Event, Semaphore
from time import sleep
from traceback import print_exc
#from cStringIO import StringIO

from wx.lib import masked

from BitTornado.ConfigDir import ConfigDir
from BitTornado.bencode import bdecode
from BitTornado.download_bt1 import defaults as BTDefaults
from BitTornado.parseargs import parseargs
from BitTornado.zurllib import urlopen


################################################################
#
# Helper methods
#
# Contains commonly used helper functions
#
################################################################

#
# Check to see if a file both exists and is readable
#
def existsAndIsReadable(filename):
    return os.access(filename, os.F_OK) and os.access(filename, os.R_OK)

#
# Intersection of two lists (or dictionaries)
#
def intersection(list1, list2):
    if list1 is None or list2 is None:
        return []
    
    # (Order matters slightly so that has_key is called fewer times)
    if len(list1) < len(list2):
        smaller = list1
        bigger = list2
    else:
        smaller = list2
        bigger = list1
    
    int_dict = {}
    if isinstance(bigger, dict):
        bigger_dict = bigger
    else:
        bigger_dict = {}
        for e in bigger:
            bigger_dict[e] = 1
    for e in smaller:
        if e in bigger_dict:
            int_dict[e] = bigger_dict[e]
    return int_dict.keys()

#
# Union of two lists (or dictionaries)
#
def union(list1, list2):
    if list1 is None:
        list1 = {}
    if list2 is None:
        list2 = {}
    
    # (Order matters slightly so that has_key is called fewer times)
    if len(list1) < len(list2):
        smaller = list1
        bigger = list2
    else:
        smaller = list2
        bigger = list1    
    
    if isinstance(bigger, dict):
        union_dict = bigger
    else:
        union_dict = {}
        for e in bigger:
            union_dict[e] = bigger[e]
    for e in smaller:
        union_dict[e] = smaller[e]
    return union_dict

#
# Difference of two dictionaries
# (A - B)
#
def difference(list1, list2):
    if list2 is None:
        return list1
    if list1 is None:
        return {}
        
    diff_dict = list1.copy()
    for e in list2:
        if e in diff_dict:
            del diff_dict[e]
    return diff_dict

#
# Get a socket to send on
#
def getClientSocket(host, port):
    s = None
    
    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error:
            s = None
            continue

        try:
            s.connect(sa)
        except socket.error:
            print_exc()
            s.close()
            s = None
            continue
        break
        
    return s
    
#
# Get a socket to listen on
#
def getServerSocket(host, port):
    s = None

    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
        af, socktype, proto, canonname, sa = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error:
            print_exc()
            s = None
            continue
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(sa)
            s.listen(1)
        except socket.error:
            print_exc()
            s.close()
            s = None
            continue
        break

    return s

#
# Get a socket (either client or server)
# Will make up to 5 attempts to get the socket
#
def getSocket(host, port, sockettype = "client", attempt = 5):
    s = None

    tries = 0

    while s is None and tries < attempt:
        try:
            if sockettype == "server":
                s = getServerSocket(host, port)
            else:
                s = getClientSocket(host, port)
        except:
            s = None
                
        if s is None:
            # Try several times, increase in time each try
            sleep(0.01 * tries)
            tries += 1
            
    return s
    
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
            
            
def stopTorrentsIfNeeded(torrentlist):
    # Error : all selected torrents must be inactive to get extracted
    showDialog = True

    # See which torrents are active
    activetorrents = [ABCTorrentTemp for ABCTorrentTemp in torrentlist if ABCTorrentTemp.status.isActive()]

    # Ask to stop other torrents if necessary
    if activetorrents > 0:
        singleTorrent = len(activetorrents) == 1
        for ABCTorrentTemp in activetorrents:
            if ABCTorrentTemp.dialogs.stopIfNeeded(showDialog, singleTorrent):
                # Torrent was stopped, don't show the dialog anymore
                showDialog = False
            else:
                # Selected not to stop the torrent, return False
                return False
    
    # At this point all selected torrents should be stopped
    return True
