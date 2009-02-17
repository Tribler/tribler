# Written by ABC authors
# see LICENSE.txt for license information

import sys
import os
import socket

from threading import Event, Semaphore
from time import sleep
from traceback import print_exc
#from cStringIO import StringIO

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.defaults import dldefaults as BTDefaults
from Tribler.Core.BitTornado.parseargs import parseargs
from Tribler.Core.BitTornado.zurllib import urlopen

DEBUG = False
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
    if DEBUG:
        print 'getClientSocket(%s, %d)' % (host, port)
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
