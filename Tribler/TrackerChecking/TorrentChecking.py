# written by Niels Zeilemaker
# inspired by old TorrentChecking written by Yuan Yuan, Jie Yang, uses their torrent selection policies
# see LICENSE.txt for license information
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
from threading import Thread, Lock, currentThread
from random import sample
from time import time
from os import path
from collections import deque
try:
    prctlimported = True
    import prctl
except ImportError,e:
    prctlimported = False

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.TrackerChecking.TrackerChecking import trackerChecking,\
    multiTrackerChecking

from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker
from Tribler.Core.DecentralizedTracking.MagnetLink.MagnetLink import MagnetLink
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from traceback import print_exc
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_UPDATE
from Tribler.Core.CacheDB.Notifier import Notifier
from bisect import insort
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Core.CacheDB.sqlitecachedb import forceAndReturnDBThread, bin2str,\
    forceDBThread

QUEUE_SIZE_LIMIT = 250
DEBUG = False

class TorrentChecking(Thread):
    
    __single = None
    
    def __init__(self, interval = 15):
        if TorrentChecking.__single:
            raise RuntimeError, "Torrent Checking is singleton"
        TorrentChecking.__single = self
        
        Thread.__init__(self)
        
        self.setName('TorrentChecking'+self.getName())
        if DEBUG:
            print >> sys.stderr, 'TorrentChecking: Started torrentchecking from', threading.currentThread().getName()
        self.setDaemon(True)
        
        self.retryThreshold = 10
        self.interval = interval
        
        self.queue = deque()
        self.queueset = set()
        self.queueLock = Lock()
        
        self.mldhtchecker = mainlineDHTChecker.getInstance()
        self.torrentdb = TorrentDBHandler.getInstance()
        self.notifier = Notifier.getInstance()
        
        self.sleepEvent = threading.Event()
        
        self.start()
            
    def getInstance(*args, **kw):
        if TorrentChecking.__single is None:
            TorrentChecking(*args, **kw)
        return TorrentChecking.__single
    getInstance = staticmethod(getInstance)
    
    def setInterval(self, interval):
        self.interval = interval
                
    def selectPolicy(self):
        policies = ["oldest", "random", "popular"]
        return sample(policies, 1)[0]
        
    #add a torrent to the queue, this will schedule a call to update the status etc. for this torrent
    #if the queue is currently full, it will not!
    def addToQueue(self, infohash):
        if infohash not in self.queueset and len(self.queueset) < QUEUE_SIZE_LIMIT:
            torrent = self.torrentdb.selectTorrentToCheck(infohash=infohash)
            if not torrent:
                return False
            
            diff = time() - (torrent['last_check'] or 0)
            if diff < 1800:
                if DEBUG:
                    print >> sys.stderr, "TorrentChecking: checking too soon:", torrent

                return False
            
            self.queueLock.acquire()
            
            self.queue.append(torrent)
            self.queueset.add(infohash)
            
            self.queueLock.release()
            
            self.sleepEvent.set()
            return True
        return False
    
    #add a torrent to the queue, this will schedule a call to update the status etc. for this torrent
    #if the queue is currently full, it will not!
    def addTorrentToQueue(self, torrent):
        if torrent.infohash not in self.queueset and len(self.queueset) < QUEUE_SIZE_LIMIT:
        
            #convert torrent gui-dbtuple to internal format
            res = {'torrent_id':torrent._torrent_id, 
                   'ignored_times':0, 
                   'retried_times':0, 
                   'torrent_path':'',
                   'infohash':torrent.infohash,
                   'status':'good',
                   'last_check':0}
        
            if 'last_check' in torrent:
                res['last_check'] = torrent.last_check
            if 'trackers' in torrent:
                res['trackers'] = torrent.trackers
        
            self.queueLock.acquire()
            
            self.queue.append(res)
            self.queueset.add(torrent.infohash)
            
            self.queueLock.release()
        
            self.sleepEvent.set()
            
            return True
        return False
    
    @forceAndReturnDBThread
    def selectTorrentToCheck(self):
        policy = self.selectPolicy()
        return self.torrentdb.selectTorrentToCheck(policy=policy)
            
    def run(self):
        """ Gets one torrent from good or unknown list and checks it """
        
        if prctlimported:
            prctl.set_name("Tribler"+currentThread().getName())
        
        #request new infohash from queue
        while True:
            start = time()
            self.sleepEvent.clear()
            
            didTrackerCheck = False
            
            try:
                torrent = None
                try:   
                    self.queueLock.acquire()
                    
                    while True:
                        torrent = self.queue.popleft()
                        self.queueset.discard(torrent['infohash'])
                        if DEBUG:
                            print >> sys.stderr, "TorrentChecking: get value from QUEUE:", torrent
                            
                        break
                    
                    self.queueLock.release()
                
                except:
                    self.queueLock.release()
    
                    torrent = self.selectTorrentToCheck()
                    if DEBUG:
                        print >> sys.stderr, "TorrentChecking: get value from DB:", torrent
            
                if torrent:
                    self.doCheck(torrent)
            
            except: #make sure we do not crash while True loop
                print_exc()
            
            # schedule sleep time, only if we do not have any infohashes scheduled
            if len(self.queue) == 0:
                diff = time() - start
                remaining = int(self.interval - diff)
                if remaining > 0:
                    if DEBUG:
                        print >> sys.stderr, "TorrentChecking: going to sleep for", remaining
                    self.sleepEvent.wait(remaining)
                        
    def doCheck(self, torrent):
        if torrent:
            diff = time() - (torrent['last_check'] or 0)
            if diff < 1800:
                pass
            
            elif torrent['ignored_times'] > 0:
                #ignoring this torrent
                if DEBUG:
                    print >> sys.stderr, 'TorrentChecking: ignoring torrent:', torrent
                    
                kw = { 'ignored_times': torrent['ignored_times'] - 1 }
                self.torrentdb.updateTorrent(torrent['infohash'], **kw)
                
            else:
                multi_announce_dict = {}
                multi_announce_dict[torrent['infohash']] = (-2, -2)
                
                # read the torrent from disk / use other sources to specify trackers
                torrent = self.readTrackers(torrent)
                if self.hasTrackers(torrent):
                    if DEBUG:
                        print >> sys.stderr, "TorrentChecking: tracker checking", torrent["info"].get("announce", ""), torrent["info"].get("announce-list", "")
                        trackerStart = time()
                    
                    multi_announce_dict = multiTrackerChecking(torrent, self.GetInfoHashesForTracker)
                    if DEBUG:
                        print >> sys.stderr, "TorrentChecking: tracker checking took ", time() - trackerStart, torrent["info"].get("announce", "") ,torrent["info"].get("announce-list", "")
                
                # Modify last_check time such that the torrents in queue will be skipped if present in this multi-announce
                with self.queueLock:
                    for tor in self.queue:
                        if tor['infohash'] in multi_announce_dict:
                            tor['last_check'] = time()

                # Update torrent with new status
                self.updateTorrents(torrent, multi_announce_dict)
    
    def readTrackers(self, torrent):
        torrent = self.readTorrent(torrent)
        if not self.hasTrackers(torrent):
            torrent = self.dbreadTrackers(torrent)
        return torrent
                    
    def readTorrent(self, torrent):
        try:
            torrent_path = torrent['torrent_path']
            
            if not path.isfile(torrent_path):
                #torrent not found, try filename + current torrent collection directory
                torrent_collection_dir = Session.get_instance().get_torrent_collecting_dir()
                _, torrent_filename = path.split(torrent_path)
                torrent_path = path.join(torrent_collection_dir, torrent_filename)
                
            if path.isfile(torrent_path):
                f = open(torrent_path,'rb')
                _data = f.read()
                f.close()
            
                data = bdecode(_data)
            
                assert 'info' in data
                del data['info']
                
                torrent['info'] = data
                
        except Exception:
            #print_exc()
            pass
        return torrent
    
    @forceAndReturnDBThread
    def dbreadTrackers(self, torrent):
        announce = announce_list = None
        
        #try using magnet torrentcollecting url
        sources = self.torrentdb.getTorrentCollecting(torrent['torrent_id'])
        for source, in sources:
            if source.startswith('magnet'):
                dn, xt, trs = MagnetLink.parse_url(source)
                
                if len(trs) > 0:
                    if 'info' not in torrent:
                        torrent["info"] = {}
                    
                    announce = trs[0]
                    announce_list = [trs]
                break
        
        if not (announce or announce_list):
            #see if we have a TorrentTracker entry
            trackers = self.torrentdb.getTracker(torrent['infohash'])
        
            if trackers and len(trackers) > 0:
                announce_list = []
                
                for tracker, tier in trackers:
                    if tier == 0:
                        announce = tracker
                    else:
                        #tier 1 is actually first in announce-list
                        tier = max(tier-1, 0)
                        while len(announce_list) <= tier:
                            announce_list.append([])
                        
                        announce_list[tier].append(tracker)
            
        if announce and announce_list:   
            if 'info' not in torrent:
                torrent["info"] = {}

            torrent["info"]["announce"] = announce
            torrent['info']["announce-list"] = announce_list
            
        return torrent
    
    @forceAndReturnDBThread
    def updateTorrents(self, torrent, announce_dict):
        for key, values in announce_dict.iteritems():
            seeders, leechers = values
            seeders = max(-2, seeders)
            leechers = max(-2, leechers)
            
            status = "unknown"
            if seeders > 0 or leechers > 0:
                status = "good"
            elif seeders < -1 and leechers < -1:
                status = "dead"
                
            retried_times = 0
            ignored_times = 0
            if key == torrent['infohash']:
                if status == "unknown":
                    if torrent["retried_times"] > self.retryThreshold:    # set to dead
                        status = "dead"
                    else:
                        retried_times = torrent["retried_times"] + 1 
                        ignored_times = retried_times
                
                elif status == "dead": # dead
                    if torrent["retried_times"] < self.retryThreshold:
                        retried_times = torrent["retried_times"] + 1
            
            #store result
            curkw = {'seeder':seeders, 'leecher':leechers, 'ignored_times': ignored_times, 'last_check_time': long(time()), 'status': status, 'retried_times':retried_times}
            self.torrentdb.updateTorrent(key, **curkw)
                    
            if DEBUG:
                print >> sys.stderr, "TorrentChecking: new status:", curkw
            
            if key == torrent['infohash']:
                if status == 'dead':
                    self.mldhtchecker.lookup(torrent['infohash'])
                    
    def hasTrackers(self, torrent):
        emptyAnnounceList = emptyAnnounce = True
        if 'info' in torrent:
            emptyAnnounceList = len(torrent["info"].get("announce-list", [])) == 0
            emptyAnnounce = torrent["info"].get("announce", "") == ""
            
        return not emptyAnnounceList or not emptyAnnounce
    
    def GetInfoHashesForTracker(self, tracker):
        isLocked = False
        try:
            tracker = unicode(tracker)
            
            #see if any other torrents in queue have this tracker
            infohashes = []
            
            self.queueLock.acquire()
            isLocked = True
            for torrent in self.queue:
                if torrent and 'trackers' in torrent:
                    if tracker in torrent['trackers']:
                        infohashes.append(torrent['infohash'])
            
            self.queueLock.release()
            isLocked = False
            
            if DEBUG:
                print >> sys.stderr, "TorrentChecking: Found %d additional infohashes for tracker %s in QUEUE"%(len(infohashes), tracker)
            
            if len(infohashes) < 10:
                max_last_check = int(time()) - 4*60*60
                infohashes.extend(self.torrentdb.getTorrentsFromTracker(tracker, max_last_check, 10 - len(infohashes)))
                
            if DEBUG:
                print >> sys.stderr, "TorrentChecking: Returning %d additional infohashes for tracker %s"%(len(infohashes), tracker)
            return infohashes
        
        except UnicodeDecodeError:
            if isLocked:
                self.queueLock.release()
            
            return []

if __name__ == '__main__':
    DEBUG = True
    
    from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, str2bin
    configure_dir = sys.argv[1]
    config = {}
    config['state_dir'] = configure_dir
    config['install_dir'] = '.'
    config['peer_icon_path'] = '.'
    config['torrent_collecting_dir'] = '.'
    config['superpeer'] = True
    init_db(config)
    
    t = TorrentChecking()
        
    infohash_str = 'TkFX5S4qd2DPW63La/VObgOH/Nc='
    infohash = str2bin(infohash_str)
    
    t.addToQueue(infohash)
