# written by Yuan Yuan, Jie Yang
# see LICENSE.txt for license information
#
#  
# New Tracker Checking Algortihm by Jie Yang
# ==========================
# 
# Each time when a torrent checking thread starts, it uses one policy to select
# a torrent to check. The question turns to how to set the weight of these policies.
#
# Policy 1: Random 1/3
#   Randomly select a torrent to collect (last_check < 5 min ago)
#
# Policy 2: Oldest (unknown) first  1/3
#   Select the non-dead torrent which was not been checked for the longest time (last_check < 5 min ago)
#
# Policy 3: Popular (good) first    1/3
#   Select the non-dead most popular (3*num_seeders+num_leechers) one which has not been checked in last N seconds
#   (The default N = 4 hours, so at most 4h/torrentchecking_interval popular peers)
#
#===============================================================================

import sys
import threading
from threading import Thread
from random import random, sample
from time import time, asctime
from traceback import print_exc, print_stack

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from Tribler.Core.CacheDB.sqlitecachedb import safe_dict
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker
#from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

DEBUG = False

class TorrentChecking(Thread):
    
    def __init__(self, infohash=None):
        Thread.__init__(self)
        self.setName('TorrentChecking'+self.getName())
        if DEBUG:
            print >> sys.stderr, 'TorrentChecking: Started torrentchecking', threading.currentThread().getName()
        self.setDaemon(True)
        
        self.infohash = infohash
        self.retryThreshold = 10
        self.gnThreashold = 0.9
        self.mldhtchecker = mainlineDHTChecker.getInstance()
        self.db_thread = None   # if it is set, use another thread to access db
        #self.db_thread = OverlayThreadingBridge.getInstance()
        
    def selectPolicy(self):
        policies = ["oldest", "random", "popular"]
        return sample(policies, 1)[0]
        
    def readTorrent(self, torrent):
        try:
            torrent_path = torrent['torrent_path']
            f = open(torrent_path,'rb')
            _data = f.read()
            f.close()
            data = bdecode(_data)
            assert 'info' in data
            del data['info']
            torrent['info'] = data
            return torrent
        except Exception, msg:
            #print_exc()
            return torrent
            
    def run(self):
        """ Gets one torrent from good or unknown list and checks it """
        
        try:
            if DEBUG:
                print >> sys.stderr, "Torrent Checking: RUN", threading.currentThread().getName()
                
            event = threading.Event()
            return_value = safe_dict()
            return_value['event'] = event
            return_value['torrent'] = None
            if self.infohash is None:   # select torrent by a policy
                policy = self.selectPolicy()
                if self.db_thread:
                    self.db_thread.add_task(lambda:
                        TorrentDBHandler.getInstance().selectTorrentToCheck(policy=policy, return_value=return_value))
                else:
                    TorrentDBHandler.getInstance().selectTorrentToCheck(policy=policy, return_value=return_value)
            else:   # know which torrent to check
                if self.db_thread:
                    self.db_thread.add_task(lambda:
                                                 TorrentDBHandler.getInstance().selectTorrentToCheck(infohash=self.infohash, return_value=return_value))
                else:
                    TorrentDBHandler.getInstance().selectTorrentToCheck(infohash=self.infohash, return_value=return_value)
            event.wait(60.0)
            
            torrent = return_value['torrent']
            if DEBUG:
                print >> sys.stderr, "Torrent Checking: get value from DB:", torrent
            
            if not torrent:
                return
    
            if self.infohash is None and torrent['ignored_times'] > 0:
                print >> sys.stderr, 'Torrent_checking: torrent: %s' % torrent
                kw = { 'ignored_times': torrent['ignored_times']-1 }
                if self.db_thread:
                    self.db_thread.add_task(lambda:
                        TorrentDBHandler.getInstance().updateTracker(torrent['infohash'], kw))
                else:
                    TorrentDBHandler.getInstance().updateTracker(torrent['infohash'], kw)
                return
    
            # may be block here because the internet IO
            torrent = self.readTorrent(torrent)    # read the torrent 
            if 'info' not in torrent:    #torrent has been deleted
                if self.db_thread:
                    self.db_thread.add_task(lambda:
                        TorrentDBHandler.getInstance().deleteTorrent(torrent['infohash']))
                else:
                    TorrentDBHandler.getInstance().deleteTorrent(torrent['infohash'])
                return
            
            # TODO: tracker checking also needs to be update
            if DEBUG:
                print >> sys.stderr, "Tracker Checking"
            trackerChecking(torrent)
            
            # Must come after tracker check, such that if tracker dead and DHT still alive, the
            # status is still set to good
            self.mldhtchecker.lookup(torrent['infohash'])
            
            self.updateTorrentInfo(torrent)            # set the ignored_times
            
            kw = {
                'last_check_time': int(time()),
                'seeder': torrent['seeder'],
                'leecher': torrent['leecher'],
                'status': torrent['status'],
                'ignored_times': torrent['ignored_times'],
                'retried_times': torrent['retried_times'],
                #'info': torrent['info']
                }
            
            if DEBUG:
                print >> sys.stderr, "Torrent Checking: selectTorrentToCheck:", kw
            
            if self.db_thread:
                self.db_thread.add_task(lambda:
                    TorrentDBHandler.getInstance().updateTorrent(torrent['infohash'], **kw))
            else:
                TorrentDBHandler.getInstance().updateTorrent(torrent['infohash'], **kw)
        finally:
            if not self.db_thread:
                TorrentDBHandler.getInstance().close()
            
#===============================================================================
#    def tooFast(self, torrent):
#        interval_time = long(time()) - torrent["last_check_time"]
#        if interval_time < 60 * 5:
#            return True
#        return False
#===============================================================================
    
    def updateTorrentInfo(self,torrent):
        if torrent["status"] == "good":
            torrent["ignored_times"] = 0
        elif torrent["status"] == "unknown":
            if torrent["retried_times"] > self.retryThreshold:    # set to dead
                torrent["ignored_times"] = 0
                torrent["status"] = "dead"
            else:
                torrent["retried_times"] += 1 
                torrent["ignored_times"] = torrent["retried_times"]
        elif torrent["status"] == "dead": # dead
            if torrent["retried_times"] < self.retryThreshold:
                torrent["retried_times"] += 1 
                    
    def tooMuchRetry(self, torrent):
        if (torrent["retried_times"] > self.retryThreshold):
            return True
        return False


if __name__ == '__main__':
    from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, str2bin
    configure_dir = sys.argv[1]
    config = {}
    config['state_dir'] = configure_dir
    config['install_dir'] = '.'
    config['peer_icon_path'] = '.'
    init_db(config)
    t = TorrentChecking()
    t.start()
    t.join()
    
    
    infohash_str = 'TkFX5S4qd2DPW63La/VObgOH/Nc='
    infohash = str2bin(infohash_str)
    
    del t
    
    t = TorrentChecking(infohash)
    t.start()
    t.join()
    
