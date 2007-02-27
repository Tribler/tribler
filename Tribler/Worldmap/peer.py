# Written by Jie Yang
# see LICENSE.txt for license information

import socket
import sys

from ipinfo import IPInfo
from threading import Timer

class MyPeer:
    """ This class presents the user himself """
    
    def __init__(self, ABCTorrent):
        self.torrent = ABCTorrent
        self.statistics = None
        self.ip = str(socket.gethostbyname(socket.gethostname()))
        self.ip_info = IPInfo.lookupIPInfo(self.ip)
        self.display = False
        #print "create my peer"

    def updateStatistics(self, statistics):
        self.statistics = statistics
        

class BTPeer:
    """ This class presents an actived peer. It contains all information about this peer,
    displays this peer in the world map, and manages the popup info window
    """
    
    def __init__(self, bt_info, ABCTorrent, rawserver = None, permid=''):
        self.torrent = ABCTorrent
        self.bt_info = bt_info
        self.active = True
        self.ip = bt_info['ip']
        self.permid = permid    # When a peer comes can I get its PermID??
        if self.permid:        # Use PermID by default
            self.id_type = 'permid'
        else:
            self.id_type = 'ip'
            self.id = self.ip
        self.ip_info = None
        self.torrent.peer_swarm[self.ip] = self
        ## Arno: using the raw server doesn't work. It delays normal
        ## communication too much. HACK IT! FIXME if too much timers allocated
        #rawserver.add_task(self.lookupIPInfo, 0)
        try:
            t = Timer(0,self.lookupIPInfo)
            t.setDaemon(True) # make them stop on exit, don't wait
            t.start()
        except:
            pass

    def updateBTInfo(self, bt_info):
        self.bt_info.update(bt_info)
        
    def lookupIPInfo(self):
        self.ip_info = IPInfo.lookupIPInfo(self.ip)   


