# written by Yuan Yuan
# see LICENSE.txt for license information


from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from Tribler.TrackerChecking.TorrentCheckingList import TorrentCheckingList
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler

from threading import Thread
from random import random
from time import time, asctime

DEBUG = False

class TorrentChecking(Thread):
    
    def __init__(self):
        self.torrentList = TorrentCheckingList.getInstance()
        self.retryThreshold = 10
        self.gnThreashold = 0.9
        self.torrent_db = SynTorrentDBHandler()
        Thread.__init__(self)
        self.setName('TorrentChecking'+self.getName())
        if DEBUG:
            print 'TorrentChecking: Started torrentchecking'
        self.setDaemon(True)
        
    def run(self):
        self.torrentList.acquire()
        g = self.torrentList.getGoodLen()
        n = self.torrentList.getUnknownLen()
        self.torrentList.release()

        r = random()
        if (r < self.gnFun(g, n)):
            # good list
            if (g == 0):
                return;

            self.torrentList.acquire()
            torrent = self.torrentList.getFirstGood()
            self.torrentList.release()
            if not torrent:
                return
            if DEBUG:
                #print "TorrentChecking: ", asctime(), "Get From Good", repr(torrent["info"]["name"])
                pass
            # whether to ignore
            if (torrent["ignore_number"] > 0):    
                torrent["ignore_number"] -= 1
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, 
                                              ignore_number=torrent["ignore_number"])
                return
            
            # whether too fast
            if (self.tooFast(torrent)):
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True)
                return
            
            # may be block here because the internet IO
            trackerChecking(torrent)
            
            self.setIgnoreNumber(torrent)            # set the ignore_number
            
            kw = {
                'last_check_time': int(time()),
                'seeder': torrent['seeder'],
                'leecher': torrent['leecher'],
                'status': torrent['status'],
                'ignore_number': torrent['ignore_number'],
                'retry_number': torrent['retry_number'],
                #'info': torrent['info']
                }
            self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, **kw)
        else:   
            # unknown list
            if (n == 0):
                return
            
            self.torrentList.acquire()
            torrent = self.torrentList.getFirstUnknown()
            self.torrentList.release()
            if not torrent:
                return
            if DEBUG:
                #print "TorrentChecking: ", asctime(), "Get from Unknown", repr(torrent["info"]["name"])
                pass
            # whether to ignore
            if (torrent["ignore_number"] > 0):    
                torrent["ignore_number"] -= 1
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, 
                                              ignore_number=torrent["ignore_number"])
                return
            
            # whether too fast
            if (self.tooFast(torrent)):
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True)
                return
            
            # may be block here because the internet IO
            trackerChecking(torrent)
            
            self.setIgnoreNumber(torrent)
            kw = {
                'last_check_time': int(time()),
                'seeder': torrent['seeder'],
                'leecher': torrent['leecher'],
                'status': torrent['status'],
                'ignore_number': torrent['ignore_number'],
                'retry_number': torrent['retry_number'],
                #'info': torrent['info']
                }
            self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, **kw)
        
        
    
    def gnFun(self, g, n):            # judgeing to pop list_good or list_unknown
        if (n == 0):
            return 1
        total = float(g + 2 * n)        # list_unkown 2x as fast as list_good
        result = g / total
        if (result > self.gnThreashold):
            result = self.gnThreashold
        return result
            
    def tooFast(self, torrent):
        interval_time = long(time()) - torrent["last_check_time"]
        if interval_time < 60 * 5:
            return True
        return False
    
        
    def setIgnoreNumber(self,torrent):
        if (torrent["status"] == "good"):
            torrent["ignore_number"] = 0
        elif (torrent["status"] == "unknown"):
            if (torrent["retry_number"] > self.retryThreshold):    # dead
                torrent["ignore_number"] = 0
            else:
                torrent["ignore_number"] = torrent["retry_number"]
        else:
            torrent["ignore_number"] = 0
        
    def tooMuchRetry(self, torrent):
        if (torrent["retry_number"] > self.retryThreshold):
            return True
        return False
