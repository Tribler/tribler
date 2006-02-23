# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

"""

Rate Control Policies (RCP):
 
1. Never exchange buddycast message with a peer if we have exchanged it in 4 hours. 
 
2. Buddycast message has size limit. If it exceeds the limit, don't handle the message 
   The size limit is: 50 my preferences, 
                      10 taste buddies each containing 10 preferences, 
                      10 random peers.
 
3. Don't reply buddycast message immediately, but schedule the task at the head of a job queue. 
   At most 15 seconds, the first pending task (i.e., buddycast reply) will be executed 
   if the target is not in blocked_list. 
"""

import sys
from random import sample, randint
from math import sqrt
from traceback import print_exc
from sets import Set
from threading import RLock

from BitTornado.bencode import bencode, bdecode
from BitTornado.BT1.MessageID import BUDDYCAST
from Tribler.CacheDB.CacheDBHandler import *
#from Tribler.__init__ import GLOBAL
from Tribler.utilities import *
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.permid import show_permid
from similarity import P2PSim, P2PSim2, selectByProbability


DEBUG = True

def validPeer(peer):
    validPermid(peer['permid'])
    validIP(peer['ip'])
    validPort(peer['port'])

def validBuddyCastData(prefxchg, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):
    
    def validPref(pref, num):
        assert isinstance(prefxchg, list) or \
               isinstance(prefxchg, dict)
        assert len(pref) <= num, len(pref)
        for p in pref:
            validInfohash(p)
            
    validPeer(prefxchg)
    assert isinstance(prefxchg['name'], str)
    validPref(prefxchg['preferences'], nmyprefs)
    
    assert len(prefxchg['taste buddies']) <= nbuddies, len(prefxchg['taste buddies'])
    for b in prefxchg['taste buddies']:
        validPeer(b)
        assert isinstance(b['age'], int) and b['age'] >= 0
        validPref(b['preferences'], nbuddyprefs)
        
    assert len(prefxchg['random peers']) <= npeers, len(prefxchg['random peers'])
    for b in prefxchg['random peers']:
        validPeer(b)
        assert isinstance(b['age'], int) and b['age'] >= 0
    return True


class RandomPeer:
    def __init__(self, data_handler, data):
        self.data_handler = data_handler
        self.permid = data['permid']
        self.ip = data['ip']
        self.port = int(data['port'])
        self.name = data.get('name', '')
        age = data.get('age', 0)
        if age < 0:
            age = 0
        self.last_seen = int(time()) - age
        self.data = {'ip':self.ip, 'port':self.port, 'name':self.name, 'last_seen':self.last_seen}
    
    def updateDB(self):
        if isValidIP(self.ip) and isValidPort(self.port):
            self.updatePeerDB()
        self.data_handler.setPeerCacheChanged(True)
                     
    def updatePeerDB(self):
        self.data_handler.addPeer(self.permid, self.data)
         
         
class TasteBuddy(RandomPeer):
    def __init__(self, data_handler, data):
        RandomPeer.__init__(self, data_handler, data)
        if isinstance(data['preferences'], list):
            self.prefs = data['preferences']
        elif isinstance(data['preferences'], dict):
            self.prefs = data['preferences'].keys()
        else:
            self.prefs = []

    def updateDB(self):    # it's important to update pref_db before update peer_db
        self.updatePrefDB()
        self.updatePeerDB()
        self.data_handler.setPeerCacheChanged(True)
        self.data_handler.setTorrentCacheChanged(True)
        
    def updatePrefDB(self):
        for pref in self.prefs:
            self.data_handler.addTorrent(pref)
            self.data_handler.addPeerPref(self.permid, pref)
        
    def updatePeerDB(self):
        self.data['similarity'] = self.data_handler.getSimilarity(self.permid)
        self.data_handler.addPeer(self.permid, self.data)
        

class JobQueue:    #TODO: parent class
    def __init__(self, max_size=0):
        self.max_size = max_size
        self._queue = []
        self.lock = RLock()

    def _addJob(self, job, position=None):    # position = None: append at tail
        try:
            self.lock.acquire()
            if position is None:
                if isinstance(job, list):
                    for w in job:
                        if self.max_size == 0 or len(self._queue) < self.max_size:
                            self._queue.append(w)
                else:
                    if self.max_size == 0 or len(self._queue) < self.max_size:
                        self._queue.append(job)
            else:
                if isinstance(job, list):
                    job.reverse()
                    for w in job:
                        self._queue.insert(position, w)
                        if self.max_size != 0 and len(self._queue) > self.max_size:
                            self._queue.pop(len(self._queue)-1)
                        
                else:
                    self._queue.insert(position, job)
                    if self.max_size != 0 and len(self._queue) > self.max_size:
                        self._queue.pop(len(self._queue)-1)
        finally:
            self.lock.release()
                
    def addJob(self, job, priority=0):    # priority: the biger the higher
        if not job:
            return
        if priority == 0:
            self._addJob(job)
        elif priority > 0:
            self._addJob(job, 0)
            
    def getJob(self):
        try:
            self.lock.acquire()
            if len(self._queue) > 0:
                return self._queue.pop(0)
            else:
                return None
        finally:
            self.lock.release()
            
            
class BuddyCastWorker:
    def __init__(self, factory, target, tbs=[], rps=[], nmyprefs=50, nbuddyprefs=10):    
        self.factory = factory
        self.data_handler = factory.data_handler
        self.target = target    # permid
        self.tbs = tbs    # taste buddy list
        self.rps = rps    # random peer list
        self.nmyprefs = nmyprefs
        self.nbuddyprefs = nbuddyprefs
        self.data = None
        
    def getBuddyCastMsgData(self):
        if self.data is None:
            self.data = {}
            self.data['ip'] = self.data_handler.ip
            self.data['port'] = self.data_handler.port
            self.data['permid'] = self.data_handler.permid
            self.data['name'] = self.data_handler.name
            self.data['preferences'] = self.data_handler.getMyPrefList(self.nmyprefs)
            self.data['taste buddies'] = self.data_handler.getTasteBuddies(self.tbs, self.nbuddyprefs)
            self.data['random peers'] = self.data_handler.getRandomPeers(self.rps)
        return self.data
        
    def work(self):
        try:
            validPermid(self.target)
            self.getBuddyCastMsgData()
#            print "** send buddycast", len(self.data['preferences']), \
#                len(self.data['taste buddies']), len(self.data['random peers'])
            buddycast_msg = bencode(self.data)
        except:
            print_exc()
            print >> sys.stderr, "buddycast: error in bencode buddycast msg"
            return
        self.factory.sendBuddyCastMsg(self.target, buddycast_msg)
        self.data_handler.addToSendBlockList(self.target, self.factory.block_time)
        

class DataHandler:
    def __init__(self, db_dir=''):
        # --- database handlers ---
        self.my_db = MyDBHandler(db_dir=db_dir)
        self.peer_db = PeerDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.torrent_db = TorrentDBHandler(db_dir=db_dir)
        self.mypref_db = MyPreferenceDBHandler(db_dir=db_dir)
        self.pref_db = PreferenceDBHandler(db_dir=db_dir)
        self.friend_db = FriendDBHandler(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db, self.superpeer_db,
                    self.torrent_db, self.mypref_db, self.pref_db]
        self.name = self.my_db.get('name', '')
        self.ip = self.my_db.get('ip', '')
        self.port = self.my_db.get('port', 0)
        self.permid = self.my_db.get('permid', '')

        # cache in memory
        self.preflist = self.mypref_db.getRecentPrefList()
        self.peercache_changed = True
        self.torrentcache_changed = True
        self.tb_list = []
        self.rp_list = []
        
        # TODO: BlockList class; sync with database
        self.send_block_list = {self.permid:int(time()+10e9)}
        self.recv_block_list = {self.permid:int(time()+10e9)}
        
    
    #---------- database operations ----------#
    def clear(self):
        for db in self.dbs:
            db.clear()
        self.preflist = []
        self.connected_list = []
            
    def sync(self):
        for db in self.dbs:
            db.sync()
        
    def updatePort(self, port):
        self.my_db.put('port', port)
        
    # --- write ---
    def addPeer(self, permid, data):
        if permid != self.permid:
            if permid in self.friend_db.getFriendList():
                # Arno: if friend, don't update name,ip or port
                # the latter should be updated only when directly
                # connecting to eachother via the overlay, not
                # by some external message.
                del data['name']
                del data['ip']
                del data['port']
            self.peer_db.addPeer(permid, data, update_dns=False)
        
    def addTorrent(self, infohash):
        self.torrent_db.addTorrent(infohash)
    
    def addPeerPref(self, permid, pref):
        if permid != self.permid:
            self.pref_db.addPreference(permid, pref)
    
    def addMyPref(self, infohash):    # user adds a preference (i.e., downloads a new file)
        if infohash in self.preflist:
            return
        self.mypref_db.addPreference(infohash)
        self.preflist.insert(0, infohash)
        self._updateSimilarity(infohash)
        self.setPeerCacheChanged(True)

    def _updateSimilarity(self, infohash):
        peers = self.peer_db.getTasteBuddyList()
        if not peers:
            return
        owners = self.torrent_db.getOwners(infohash)
        n = self.mypref_db.size()
        sim_var = sqrt(1.0*n/(n+1))    # new_sim = old_sim * sim_var 
        if len(owners) > 0:
            pref1 = self.getMyPrefList()
            pref1.sort()
        else:
            pref1 = []
        nmypref = len(pref1)
        for p in peers:
            if p in owners:
                pref2 = self.getPeerPrefList(p)
                new_sim = P2PSim2(pref1, pref2)
            else:
                peer = self.peer_db.getPeer(p, True)
                old_sim = peer.get('similarity', 0)
                new_sim = int(old_sim * sim_var)
            self.peer_db.updatePeer(p, 'similarity', new_sim)
            
    def increaseBuddyCastTimes(self, permid):
        self.peer_db.updateTimes(permid, 'buddycast_times', 1)
        
    # --- read ---
    def getPeerPrefList(self, permid, num=0):
        preflist = self.pref_db.getPrefList(permid)
        if num > len(preflist):
            return preflist
        if num == 0:
            return preflist
        else:
            prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
    
    def getMyPrefList(self, num=0):    # num = 0 to return all preflist
        if num > 0:
            return self.preflist[:num]
        else:
            return self.preflist[:]
            
    def getTasteBuddyList(self):
        tb_list = self.peer_db.getTasteBuddyList()
        return tb_list
        
    def getRandomPeerList(self):
        rp_list = self.peer_db.getRandomPeerList()
        return rp_list
    
    def getPeersValue(self, peerlist, keys):
        if len(peerlist) == 0:
            return []
        return self.peer_db.getPeersValue(peerlist, keys)

    def getTasteBuddies(self, peerlist, nbuddyprefs):
        peers = self.peer_db.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
        for i in xrange(len(peers)):
            peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
            if peers[i]['age'] < 0:
                peers[i]['age'] = 0
            peers[i]['preferences'] = self.getPeerPrefList(peers[i]['permid'], nbuddyprefs)
            assert len(peers[i]['preferences']) > 0, peers[i]['permid']
        return peers

    def getRandomPeers(self, peerlist):
        peers = self.peer_db.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
        for i in xrange(len(peers)):
            peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
            if peers[i]['age'] < 0:
                peers[i]['age'] = 0
        return peers        
        
    def getOthersTorrentList(self):
        return self.torrent_db.getOthersTorrentList()
        
    def getOwners(self, infohash):
        return self.torrent_db.getOwners(infohash)
        
    def getPeerSims(self, peer_list):
        sims = []
        for peer in peer_list:
            sim = self.peer_db.getPeerSim(peer)
            sims.append(sim)
        return sims        
        
    def updateTorrentRelevance(self, torrent, relevance):
        self.torrent_db.updateTorrentRelevance(torrent, relevance)
        
    def getTorrentsValue(self, torrent_list, keys):
        return self.torrent_db.getTorrentsValue(torrent_list, keys)
        

    #---------- utilities ----------#
    def validTarget(self, target):
        if target is None:
            return False
        peer = self.peer_db.getPeer(target)
        if peer is None:
            return False
        peer['permid'] = target
        if peer['ip'] == self.ip:    # and peer['port'] == self.port:
            return False
        try:
            validPeer(peer)
            return True
        except:
            return False
    
    # --- cache status --- #
    def peerCacheChanged(self):
        return self.peercache_changed

    def setPeerCacheChanged(self, changed=True):
        self.peercache_changed = changed
    
    def torrentCacheChanged(self):
        return self.torrentcache_changed

    def setTorrentCacheChanged(self, changed=True):
        self.torrentcache_changed = changed

    def getSimilarity(self, permid, num=0):
        pref1 = self.getMyPrefList(num)
        pref2 = self.getPeerPrefList(permid)
        sim = P2PSim(pref1, pref2)
        return sim

    # --- block list --- #
    def addToRecvBlockList(self, permid, block_time):
        if permid is not None:
            self.recv_block_list[permid] = int(time() + block_time)
        
    def addToSendBlockList(self, permid, block_time):
        if permid is not None:
            self.send_block_list[permid] = int(time() + block_time)

    def isRecvBlocked(self, permid):
        if not self.recv_block_list.has_key(permid):
            return False
        elif self.recv_block_list[permid] < int(time()):
            self.recv_block_list.pop(permid)        
            return False
        else:
            return True

    def isSendBlocked(self, permid):
        if not self.send_block_list.has_key(permid):
            return False
        elif self.send_block_list[permid] < int(time()):
            self.send_block_list.pop(permid)        
            return False
        else:
            return True
            
    def _updateBlockList(self, block_list):
        for peer in block_list.keys():
            if block_list[peer] < time():
                block_list.pop(peer)
            
    def getRecvBlockList(self):
        self._updateBlockList(self.recv_block_list)
        return self.recv_block_list.keys()
    
    def getSendBlockList(self):
        self._updateBlockList(self.send_block_list)
        return self.send_block_list.keys()
    

class BuddyCastCore:
    def __init__(self, data_handler):
        self.data_handler = data_handler
        self.num_can_tbs = 100

    # ---------- create buddycast message ------------
    def getBuddyCastData(self, target=None, nbuddies=10, npeers=10):
        """ 
        Get target, taste buddy list and random peer list for buddycast message.
        If target is not given, select a target.
        
        Taste Buddy: the peer which has profile
        Random Peer: the peer which doesn't have profile
        
        Target selection algorithm:
        - the chance to select a taste buddy or a random peer is 50% respectively
        - Any peer in sending block list cannot be selected as a target
        - select a taste buddy candidate:
            First get recent 100 taste buddies and then select one based on their similarity
        - select a random peer candidate:
            Select one peer from random peers based on their last seen timestamp.
        
        Taste buddies and random peers selection algorithm:
        Taste buddy list - the top 10 similar taste buddies
        Random peer list - From the rest of peer list (include taste buddies and random peers)
        randomly select 10 peers based on their online probability.
        
        Online probability of peers: 
            Prob_online(Peer_x) = last_seen(Peer_x) - time_stamp_of_7_days_ago
            set Prob_online(Peer_x) = 0 if Prob_online(Peer_x) > 0.
        """
        
        self._updatePeerCache(nbuddies, target)
        if target is None:
            target = self._selectTarget()
            if target is None:    # no candidate
                return None, None, None
        tbs = self._getMsgBuddies(nbuddies, target)    # it doesn't change if peer cache hasn't changed
        rps = self._getMsgPeers(npeers, target)
        return target, tbs, rps
        
    def _getMsgBuddies(self, nbuddies, target):
        msg_tbs = self.msg_tbs[:nbuddies]
        if target in msg_tbs:
            msg_tbs.remove(target)
        return msg_tbs
        
    def _getMsgPeers(self, npeers, target):
        # must pass a copy of self.msg_rps_online 
        msg_rps_idx = selectByProbability(self.msg_rps_online[:], npeers, inplace=False)    
        msg_rps = [self.msg_rps[i] for i in msg_rps_idx]
        if target in msg_rps:
            msg_rps.remove(target)
        return msg_rps
        
    def _updatePeerCache(self, nbuddies=10, target=None):
        
        def _updateCandidate():
            self.can_tbs, self.can_rps = self._separatePeersForCandidate(self.num_can_tbs)
            self.can_tbs_sims = self.data_handler.getPeersValue(self.can_tbs, ['similarity'])
            can_rps_ages = self.data_handler.getPeersValue(self.can_rps, ['last_seen'])
            self.can_rps_online = self._getOnlineProb(can_rps_ages)
        
        def _updateMessage(nbuddies):
            self.msg_tbs, self.msg_rps = self._separatePeersForMessage(nbuddies)
            self.msg_tbs = _filterUnseenPeers(self.msg_tbs)
            self.msg_rps = _filterUnseenPeers(self.msg_rps)
            msg_rps_ages = self.data_handler.getPeersValue(self.msg_rps, ['last_seen'])
            self.msg_rps_online = self._getOnlineProb(msg_rps_ages)
        
        def _filterUnseenPeers(peer_list):
            conns = self.data_handler.getPeersValue(peer_list, ['connected_times'])
            for i in xrange(len(conns)):
                if conns[i] == 0:
                    peer_list[i] = None
            return filter(None, peer_list)
        
        if False:    #not self.data_handler.peerCacheChanged():    # FIXME: peerCacheChanged must be handled by PeerDBHandler
            if target is None:
                _updateCandidate()
        else:
            self.tb_list = self.data_handler.getTasteBuddyList()
            self.rp_list = self.data_handler.getRandomPeerList()
            participants = [self.data_handler.permid]
            if target is not None:
                participants.append(target)
            self._removeItems(self.tb_list, participants)
            self._removeItems(self.rp_list, participants)
            if target is None:
                _updateCandidate()
            _updateMessage(nbuddies)
            self.data_handler.setPeerCacheChanged(False)

    def _removeItems(self, the_list, items):
        for p in items:
            if p in the_list:
                the_list.remove(p)
            
    def _separatePeersForCandidate(self, ntb=100):
        # remove blocked peers
        block_set = Set(self.data_handler.getSendBlockList())
        tb_list = list(Set(self.tb_list) - block_set)
        tb_ages = self.data_handler.getPeersValue(tb_list, ['last_seen'])
        tbs = sortList(tb_list, tb_ages)
        rps = list(Set(self.rp_list) - block_set)
        return tbs[:ntb], rps
            
    def _separatePeersForMessage(self, ntb=10):
        self.tb_sims = self.data_handler.getPeersValue(self.tb_list, ['similarity'])
        tb_list = sortList(self.tb_list, self.tb_sims)
        return tb_list[:ntb], tb_list[ntb:]+self.rp_list
        
#    def _sortList(self, list_to_sort, list_key, order='decrease'):
#        nlist = len(list_to_sort)
#        assert nlist == len(list_key), (nlist, len(list_key))
#        aux = [(list_key[i], i) for i in xrange(nlist)]
#        aux.sort()
#        if order == 'decrease':
#            aux.reverse()
#        return [list_to_sort[i] for k, i in aux]
        
    def _selectTarget(self):
        r = random()
        if r < 0.5:    # select a taste buddy based on similarity
            target = self._getBuddyCandidate()
        else:          # select a random peer based on age
            target = self._getPeerCandidate()
        return target
    
    def _getBuddyCandidate(self):
        if len(self.can_tbs) == 0:
            return None
        target_idx = selectByProbability(self.can_tbs_sims[:], 1, inplace=False)
        return self.can_tbs[target_idx[0]]
        
    def _getPeerCandidate(self):
        if len(self.can_rps) == 0:
            return None
        target_idx = selectByProbability(self.can_rps_online[:], 1, inplace=False)
        return self.can_rps[target_idx[0]]
        
    def _getOnlineProb(self, ages):    
        return self._prob2(ages)
        
    def _prob2(self, ages):
        if not ages:
            return []
        oldest_age = 8 * 60 * 60
        unit = 60
        benchmark = max(ages)
        probs = []
        for i in xrange(len(ages)):
            prob = oldest_age/unit - (benchmark - ages[i])/unit    # 5 mins
            if prob < 0:
                prob = 0
            probs.append(prob)
        return probs
        
    def _prob1(self, ages):    # linear probability
        oldest_age = 7 * 24 * 60 * 60    # 7 dyas
        benchmark = int(time()) - oldest_age
        probs = []
        for i in xrange(len(ages)):
            prob = (ages[i] - benchmark)/5 *60    # 5 mins
            if prob < 0:
                prob = 0
            probs.append(prob)
        return probs
    
    # ---------- recommend items ------------
    def recommendateItems(self, num=15):
        if self.data_handler.torrentCacheChanged():
            self._updateItemRecommendation()
            self.recom_list = self._updateRecommendedItemList(num)
            self.data_handler.setTorrentCacheChanged(False)
        return self.recom_list
            
    def _updateItemRecommendation(self):
        self.ot_list = self.data_handler.getOthersTorrentList()
        self._naiveUserBasedRecommendation()    # TODO: advanced recommendation algorithm
        
    def _naiveUserBasedRecommendation(self):
        """
        Relevance of item(i): Sum of the similarity of all the owners of item(i)
        """
        for torrent in self.ot_list:
            owners = self.data_handler.getOwners(torrent)
            sims = self.data_handler.getPeerSims(owners)
            relevance = sum(sims)
            self.data_handler.updateTorrentRelevance(torrent, relevance)
        
    def _updateRecommendedItemList(self, num):
        relevance =  self.data_handler.getTorrentsValue(self.ot_list, ['relevance'])
        recom_list = sortList(self.ot_list, relevance)
        return recom_list[:num]


class BuddyCastFactory:
    __single = None
    
    def __init__(self, db_dir=''):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.secure_overlay = SecureOverlay.getInstance()
        # --- variables ---
        # TODO: add these variables into Config
        self.db_dir = db_dir
        self.block_time = 4*60*60    # 4 hours by default
        self.msg_nbuddies = 10    # number of buddies in buddycast msg
        self.msg_npeers = 10      # number of peers in buddycast msg
        self.msg_nmyprefs = 50    # number of my preferences in buddycast msg
        self.msg_nbuddyprefs = 10 # number of taste buddy's preferences in buddycast msg
        self.buddycast_interval = 15
        self.recommendate_interval = 6 #60 + 11    # update recommendation interval; use prime number to avoid conflict
        self.sync_interval = 5*60 + 11    # sync database every 5 min
        self.max_nworkers = self.block_time/self.buddycast_interval
        
        # --- others ---
        self.registered = False
        self.rawserver = None
                
    def getInstance(*args, **kw):
        if BuddyCastFactory.__single is None:
            BuddyCastFactory(*args, **kw)
        return BuddyCastFactory.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, secure_overlay, rawserver, port, errorfunc, start=True):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.errorfunc = errorfunc
        
        #self.collect_torrents = CollectTorrentQueue(self)
        self.data_handler = DataHandler(db_dir=self.db_dir)
        self.buddycast_core = BuddyCastCore(self.data_handler)
        self.buddycast_job_queue = JobQueue(self.max_nworkers)
        if isValidPort(port):
            self.data_handler.updatePort(port)
        self.registered = True
        if start:
            self.startup()
        
    def is_registered(self):
        return self.registered
    
    def sync(self):
        self.data_handler.sync()
    
    def startup(self):
        if self.registered:
            self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
            self.rawserver.add_task(self.sync, self.sync_interval)
            self.rawserver.add_task(self.recommendateItems, self.recommendate_interval)
        if DEBUG:
            print >> sys.stderr, "buddycast: BuddyCast starts up"

    # ----- message handle -----
    def handleMessage(self, permid, message):
        
        t = message[0]
        
        if t == BUDDYCAST:
            self.gotBuddyCastMsg(message[1:], permid)
        else:
            print >> sys.stderr, "buddycast: wrong message to buddycast", message
            
    def gotBuddyCastMsg(self, msg, permid):
        def updateDB(prefxchg):
            TasteBuddy(self.data_handler, prefxchg).updateDB()
            for b in prefxchg['taste buddies']:
                TasteBuddy(self.data_handler, b).updateDB()
            for p in prefxchg['random peers']:
                RandomPeer(self.data_handler, p).updateDB()
        
        try:
            buddycast_data = bdecode(msg)
            #print_dict(buddycast_data)
            if DEBUG:
                print >> sys.stderr, "buddycast: got buddycast msg", len(msg), buddycast_data['ip']
            validBuddyCastData(buddycast_data, self.msg_nmyprefs, self.msg_nbuddies, self.msg_npeers, self.msg_nbuddyprefs)    # RCP 2            
            if not self._checkPeerConsistency(buddycast_data, permid):
               print >> sys.stderr, "buddycast: warning: buddycast's permid doens't match sender's permid"
               return
        except:
            print_exc()
            return
        target = buddycast_data['permid']
        self.data_handler.increaseBuddyCastTimes(target)
        if self.data_handler.isRecvBlocked(target):    # RCP 1
            return
        self.data_handler.addToRecvBlockList(target, self.block_time)
        updateDB(buddycast_data)
        self.buddycast_job_queue.addJob(target, priority=1)

    def _checkPeerConsistency(self, buddycast_data, permid):
        if permid != buddycast_data['permid']:
            return False
#            raise RuntimeError, "buddycast message permid doesn't match: " + \
#                hash(permid) + " " + hash(buddycast_data['permid'])
        return True

    def sendBuddyCastMsg(self, target, msg):
        if DEBUG:
            print >> sys.stderr, "buddycast: send buddycast msg:", show_permid(target), len(msg)
        #print "*** blocklist:", len(self.data_handler.send_block_list)
        if not self.data_handler.isSendBlocked(target):
            self.secure_overlay.addTask(target, BUDDYCAST + msg)
        
    def BuddyCastMsgSent(self, target):    # msg has been sent, long delay
        self.data_handler.addToSendBlockList(target, self.block_time)
    
    # ----- interface for external calls -----
    def doBuddyCast(self):
        self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
        target = self.buddycast_job_queue.getJob()
        worker = self._createWorker(target)
        if worker is not None:
            worker.work()
            del worker
        else:
            if DEBUG:
                print >> sys.stderr, "buddycast: no peer to do buddycast"

    def _createWorker(self, target=None):
        """ 
        Create a worker to send buddycast msg. 
        If target is None, a new target will be selected 
        """
        
        if self.data_handler.isSendBlocked(target):    # if target is None, it is not blocked and can go ahead
            return None
        target, tbs, rps = self.buddycast_core.getBuddyCastData(target, self.msg_nbuddies, self.msg_npeers)
        if self.data_handler.validTarget(target):
            return BuddyCastWorker(self, target, tbs, rps, self.msg_nmyprefs, self.msg_nbuddyprefs)
        else:
            return None
        
    def addMyPref(self, infohash):
        if self.registered:
            self.data_handler.addMyPref(infohash)

    def recommendateItems(self, num=15):
        return self.buddycast_core.recommendateItems(num)
        
