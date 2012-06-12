# written by Yuan Yuan, Jie Yang
# modified by Niels Zeilemaker: implemented work queue instead of multiple threads
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
from threading import Thread, Lock
from random import sample
from time import time
from os import path
from collections import deque

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

QUEUE_SIZE_LIMIT = 250
DEBUG = False

class TorrentChecking(Thread):
    
    __single = None
    
    def __init__(self, interval = 15):
        if TorrentChecking.__single:
            raise RuntimeError, "TorrentChecking is singleton"
        TorrentChecking.__single = self
        
        Thread.__init__(self)
        
        self.setName('TorrentChecking'+self.getName())
        if DEBUG:
            print >> sys.stderr, 'TorrentChecking: Started torrentchecking', threading.currentThread().getName()
        self.setDaemon(True)
        
        self.retryThreshold = 10
        self.gnThreashold = 0.9
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
        
    def readTorrent(self, torrent):
        try:
            torrent_path = torrent['torrent_path']
            
            if not path.isfile(torrent_path):
                #torrent not found, try filename + current torrent collection directory
                torrent_collection_dir = Session.get_instance().get_torrent_collecting_dir()
                _, torrent_filename = path.split(torrent_path)
                torrent_path = path.join(torrent_collection_dir, torrent_filename)
            
            if not path.isfile(torrent_path):
                #torrent still not found, determine filename + current torrent collection directory
                torrent_path = path.join(torrent_collection_dir, get_collected_torrent_filename(torrent['infohash']))
                
            if path.isfile(torrent_path):
                f = open(torrent_path,'rb')
                _data = f.read()
                f.close()
            
                data = bdecode(_data)
            
                assert 'info' in data
                del data['info']
                
                torrent['info'] = data
            return torrent
        except Exception:
            #print_exc()
            return torrent
        
    def readTrackers(self, torrent):
        torrent = self.readTorrent(torrent)
        
        if not self.hasTrackers(torrent):
            #try using magnet torrentcollecting url
            sources = self.torrentdb.getTorrentCollecting(torrent['torrent_id'])
            for source, in sources:
                if source.startswith('magnet'):
                    dn, xt, trs = MagnetLink.parse_url(source)
                    
                    if len(trs) > 0:
                        if 'info' not in torrent:
                            torrent["info"] = {}
                        
                        torrent["info"]["announce"] = trs[0]
                        torrent["info"]["announce-list"] = [trs]
                    break
                
        if not self.hasTrackers(torrent):
            #see if we have a TorrentTracker entry
            trackers = self.torrentdb.getTracker(torrent['infohash'])
            
            if trackers and len(trackers) > 0:
                if 'info' not in torrent:
                    torrent["info"] = {}
                    torrent["info"]["announce"] = ''
            
                for tracker, tier in trackers:
                    if tier == 0:
                        torrent["info"]["announce"] = tracker
                    else:
                        #tier 1 is actually first in announce-list
                        
                        tier = max(tier-1, 0)
                        if "announce-list" not in torrent['info']:
                            torrent['info']["announce-list"] = []
                        
                        while len(torrent["info"]["announce-list"]) <= tier:
                            torrent['info']["announce-list"].append([])
                        
                        torrent['info']["announce-list"][tier].append(tracker)
        
        return torrent
    
    #add a torrent to the queue, this will schedule a call to update the status etc. for this torrent
    #if the queue is currently full, it will not!
    def addToQueue(self, infohash):
        if True or infohash not in self.queueset and len(self.queueset) < QUEUE_SIZE_LIMIT:
            torrent = self.torrentdb.selectTorrentToCheck(infohash=infohash)
            
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
            
    def run(self):
        """ Gets one torrent from good or unknown list and checks it """
        #request new infohash from queue
        while True:
            start = time()
            self.sleepEvent.clear()
            fromQueue = False
            didTrackerCheck = False
            
            try:    
                try:
                    self.queueLock.acquire()
                    
                    while True:
                        torrent = self.queue.popleft()
                        self.queueset.discard(torrent['infohash'])
                    
                        fromQueue = True
                    
                        diff = time() - (torrent['last_check'] or 0)
                        if diff < 1800:
                            if DEBUG:
                                print >> sys.stderr, "Torrent Checking: checking too soon:", torrent
                            continue    
                    
                        if DEBUG:
                            print >> sys.stderr, "Torrent Checking: get value from QUEUE:", torrent
                            
                        break
                    
                    self.queueLock.release()
                
                except:
                    self.queueLock.release()
                    
                    policy = self.selectPolicy()
                    torrent = self.torrentdb.selectTorrentToCheck(policy=policy)
                    
                    if DEBUG:
                        print >> sys.stderr, "Torrent Checking: get value from DB:", torrent
                    
                if torrent:
                    notify = []
                    
                    if fromQueue and torrent['ignored_times'] > 0:
                        #ignoring this torrent
                        if DEBUG:
                            print >> sys.stderr, 'Torrent Checking: ignoring torrent:', torrent
                            
                        kw = { 'ignored_times': torrent['ignored_times'] -1 }
                        
                    else:
                        # read the torrent from disk / use other sources to specify trackers
                        torrent = self.readTrackers(torrent)
                        if self.hasTrackers(torrent):
                            if DEBUG:
                                print >> sys.stderr, "Torrent Checking: tracker checking", torrent["info"].get("announce", "") ,torrent["info"].get("announce-list", "")
                                trackerStart = time()
                                   
                            multidict = multiTrackerChecking(torrent, self.GetInfoHashesForTracker)
                            didTrackerCheck = True
                            if DEBUG:
                                print >> sys.stderr, "Torrent Checking: tracker checking took ", time() - trackerStart, torrent["info"].get("announce", "") ,torrent["info"].get("announce-list", "")
                            
                            for key, values in multidict.iteritems():
                                if key != torrent['infohash']:
                                    seeder, leecher = values
                                    
                                    if seeder > 0 or leecher > 0:
                                        #store result
                                        curkw = {'seeder':seeder, 'leecher':leecher, 'ignored_times': 0, 'last_check_time': long(time()), 'status':'good'}
                                        self.torrentdb.updateTorrent(key, commit = False, notify = False, **curkw)
                                        notify.append(key)
                                        
                                        if DEBUG:
                                            print >> sys.stderr, "Torrent Checking: new status:", curkw
                                    
                                    for tor in self.queue:
                                        if tor and tor['infohash'] == key:
                                            tor['last_check'] = time()
                        
                        if not didTrackerCheck:
                            torrent["seeder"] = -2
                            torrent["leecher"] = -2
                            
                        # Update torrent with new status
                        self.updateTorrentInfo(torrent)
    
                        # Save in DB                    
                        kw = {
                            'last_check_time': int(time()),
                            'seeder': torrent['seeder'],
                            'leecher': torrent['leecher'],
                            'status': torrent['status'],
                            'ignored_times': torrent['ignored_times'],
                            'retried_times': torrent['retried_times']
                        }
                        
                    # Must come after tracker check, such that if tracker dead and DHT still alive, the
                    # status is still set to good
                    if torrent['status'] == 'dead':
                        self.mldhtchecker.lookup(torrent['infohash'])
                
                    if DEBUG:
                        print >> sys.stderr, "Torrent Checking: new status:", kw
                
                    self.torrentdb.updateTorrent(torrent['infohash'], notify = didTrackerCheck, **kw)
                    
                    #notify after commit
                    for infohash in notify:
                        self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)
            except:
                print_exc()
                    
            # schedule sleep time, only if we do not have any infohashes scheduled
            if len(self.queue) == 0:
                diff = time() - start
                remaining = int(self.interval - diff)
                if remaining > 0:
                    self.sleepEvent.wait(remaining)
            
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
                print >> sys.stderr, "Torrent Checking: Found %d additional infohashes for tracker %s in QUEUE"%(len(infohashes), tracker)
            
            if len(infohashes) < 10:
                max_last_check = int(time()) - 4*60*60
                infohashes.extend(self.torrentdb.getTorrentsFromTracker(tracker, max_last_check, 10 - len(infohashes)))
                
            if DEBUG:
                print >> sys.stderr, "Torrent Checking: Returning %d additional infohashes for tracker %s"%(len(infohashes), tracker)
            return infohashes
        
        except UnicodeDecodeError:
            if isLocked:
                self.queueLock.release()
            
            return []

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
        
    infohash_str = 'TkFX5S4qd2DPW63La/VObgOH/Nc='
    infohash = str2bin(infohash_str)
    
    t.addToQueue(infohash)
