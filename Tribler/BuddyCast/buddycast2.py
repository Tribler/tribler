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

from BitTornado.bencode import bencode, bdecode
from Tribler.CacheDB.CacheDBHandler import *
#from Tribler.__init__ import GLOBAL
from Tribler.utilities import *
from Tribler.Overlay.SecureOverlay import SecureOverlay
from similarity import P2PSim, P2PSim2, selectByProbability

def validBuddyCastData(prefxchg, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):
    def validPeer(peer):
        validPermid(peer['permid'])
        validIP(peer['ip'])
        validPort(peer['port'])
    
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
    for p in prefxchg['random peers']:
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
        
    def updatePrefDB(self):
        for pref in self.prefs:
            self.data_handler.addTorrent(pref)
            self.data_handler.addPeerPref(self.permid, pref)
        
    def updatePeerDB(self):
        self.data['similarity'] = self.data_handler.getSimilarity(self.permid)
        self.data_handler.addPeer(self.permid, self.data)
        

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
        if self.data is not None:
            return self.data
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
            msg_data = self.getBuddyCastMsgData()
            buddycast_msg = bencode(msg_data)
        except:
            print_exc()
            print >> sys.stderr, "error in bencode buddycast msg"
            return
        self.factory.sendBuddyCastMsg(self.target, buddycast_msg)
        self.data_handler.addToSendBlockList(self.target, self.factory.short_block_time)


class JobQueue:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self._queue = []

    def _addJob(self, target, position=None):    # position = None: append at tail
        if position is None:
            if isinstance(target, list):
                for w in target:
                    if len(self._queue) < self.max_size:
                        self._queue.append(w)
            else:
                if len(self._queue) < self.max_size:
                    self._queue.append(target)
        else:
            if isinstance(target, list):
                target.reverse()
                for w in target:
                    self._queue.insert(position, w)
                    if len(self._queue) > self.max_size:
                        self._queue.pop(len(self._queue)-1)
                    
            else:
                self._queue.insert(position, target)
                if len(self._queue) > self.max_size:
                    self._queue.pop(len(self._queue)-1)
                
    def addTarget(self, target, priority=0):    # priority: the biger the higher
        if not target:
            return
        if priority == 0:
            self._addJob(target)
        elif priority > 0:
            self._addJob(target, 0)
            
    def getTarget(self):
        if len(self._queue) > 0:
            return self._queue.pop(0)
        else:
            return None


class DataHandler:
    def __init__(self, db_dir=''):
        # --- database handlers ---
        self.my_db = MyDBHandler(db_dir=db_dir)
        self.peer_db = PeerDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.torrent_db = TorrentDBHandler(db_dir=db_dir)
        self.mypref_db = MyPreferenceDBHandler(db_dir=db_dir)
        self.pref_db = PreferenceDBHandler(db_dir=db_dir)
        self.owner_db = OwnerDBHandler(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db, self.superpeer_db, self.owner_db, 
                    self.torrent_db, self.mypref_db, self.pref_db]        
        self.name = self.my_db.get('name', '')
        self.ip = self.my_db.get('ip', '')
        self.port = self.my_db.get('port', 0)
        self.permid = self.my_db.get('permid', '')

        # cache in memory
        self.preflist = self.mypref_db.getRecentPrefList()
        self.peercache_changed = True
        self.tb_list = []
        self.rp_list = []
        
        self.send_block_list = {}
        self.recv_block_list = {}
      
    
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
            self.peer_db.addPeer(permid, data)
        
    def addTorrent(self, infohash):
        self.torrent_db.addTorrent(infohash)
    
    def addPeerPref(self, permid, pref):
        if permid != self.permid:
            self.pref_db.addPreference(permid, pref)
    
    def addMyPref(self, infohash, data={}):    # user adds a preference (i.e., downloads a new file)
        existed = self.preflist.count(infohash)    
        while existed > 0:
            self.preflist.remove(infohash)
            existed -= 1
        self.preflist.insert(0, infohash)
        self.mypref_db.addPreference(infohash, data)    # update last_seen if the pref exists
        if not existed:    # don't update similarity if the pref exists
            self._updateSimilarity(infohash)
        self.setPeerCacheChanged(True)

    def _updateSimilarity(self, infohash):
        peers = self.peer_db.getTasteBuddyList()
        if not peers:
            return
        owners = self.owner_db.getOwners(infohash)
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
                peer = self.peer_db.getPeer(p)
                old_sim = peer['similarity']
                new_sim = int(old_sim * sim_var)
            self.peer_db.updatePeer(p, 'similarity', new_sim)
        
        
    # --- read ---
    def getPeerPrefList(self, permid, num=0):
        preflist = self.pref_db.getPrefList(permid)
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
        try:
            tb_list.remove(self.permid)    # don't include myself
        except:
            pass
        return tb_list
        
    def getRandomPeerList(self):
        rp_list = self.peer_db.getRandomPeerList()
        try:
            rp_list.remove(self.permid)    # don't include myself
        except:
            pass
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

    #---------- utilities ----------#
    def peerCacheChanged(self):
        return self.peercache_changed

    def setPeerCacheChanged(self, changed=True):
        self.peercache_changed = changed
    
    def getSimilarity(self, permid, num=0):
        pref1 = self.getMyPrefList(num)
        pref2 = self.getPeerPrefList(permid)
        sim = P2PSim(pref1, pref2)
        return sim

    # --------- block list --------#
    def addToRecvBlockList(self, permid, block_time):
        if permid is not None:
            self.recv_block_list[permid] = int(time()) + block_time
        
    def addToSendBlockList(self, permid, block_time):
        if permid is not None:
            self.send_block_list[permid] = int(time()) + block_time

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
            
    def getRecvBlockList(self):
        return self.recv_block_list.keys()
    
    def getSendBlockList(self):
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
        
        Taste buddy list - the top 10 similar peers
        Random peer list - From the rest of peer list select 10 random peers 
        based on their online probability.
        
        Online probability of peers: 
            Prob_online(Peer_x) = last_seen(Peer_x) - time_stamp_of_7_days_ago
            set Prob_online(Peer_x) = 0 if Prob_online(Peer_x) > 0.
        """
        
        self._updatePeerCache(nbuddies, target)
        if target is None:
            target = self._selectTarget()
            if target is None:    # no candidate
                return None, None, None
        tbs = self._getMsgBuddies()    # it doesn't change if peer cache hasn't changed
        rps = self._getMsgPeers(npeers)
        return target, tbs, rps
        
    def _getMsgBuddies(self):
        return self.msg_tbs
        
    def _getMsgPeers(self, npeers):
        msg_rps_idx = selectByProbability(self.msg_rps_online[:], npeers)    # must pass a copy of self.msg_rps_online 
        return [self.msg_rps[i] for i in msg_rps_idx]
        
    def _updatePeerCache(self, nbuddies=10, target=None):
        
        def _updateCandidate():
            self.can_tbs, self.can_rps = self._separatePeersForCandidate(self.num_can_tbs)
            self.can_tbs_sims = self.data_handler.getPeersValue(self.can_tbs, ['similarity'])
            can_rps_ages = self.data_handler.getPeersValue(self.can_rps, ['last_seen'])
            self.can_rps_online = self._getOnlineProb(can_rps_ages)
        
        def _updateMessage(nbuddies):
            self.msg_tbs, self.msg_rps = self._separatePeersForMessage(nbuddies)
            msg_rps_ages = self.data_handler.getPeersValue(self.msg_rps, ['last_seen'])
            self.msg_rps_online = self._getOnlineProb(msg_rps_ages)
        
        if not self.data_handler.peerCacheChanged():
            if target is None:
                _updateCandidate()
        else:
            self.tb_list = self.data_handler.getTasteBuddyList()
            self.rp_list = self.data_handler.getRandomPeerList()
            _updateCandidate()
            _updateMessage(nbuddies)
            self.data_handler.setPeerCacheChanged(False)
            
    def _separatePeersForCandidate(self, ntb=100):
        # remove blocked peers
        block_set = Set(self.data_handler.getSendBlockList())
        tb_list = list(Set(self.tb_list) - block_set)
        tb_ages = self.data_handler.getPeersValue(tb_list, ['last_seen'])
        tbs = self._sortList(tb_list, tb_ages)
        rps = list(Set(self.rp_list) - block_set)
        return tbs[:ntb], rps
            
    def _separatePeersForMessage(self, ntb=10):
        self.tb_sims = self.data_handler.getPeersValue(self.tb_list, ['similarity'])
        tbs = self._sortList(self.tb_list, self.tb_sims)
        return tbs[:ntb], tbs[ntb:]+self.rp_list
        
    def _sortList(self, list_to_sort, list_key, order='decrease'):
        nlist = len(list_to_sort)
        assert nlist == len(list_key), (nlist, len(list_key))
        aux = [(list_key[i], i) for i in xrange(nlist)]
        aux.sort()
        if order == 'decrease':
            aux.reverse()
        return [list_to_sort[i] for k, i in aux]
        
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
        target_idx = selectByProbability(self.can_tbs_sims[:], 1)
        return self.can_tbs[target_idx[0]]
        
    def _getPeerCandidate(self):
        if len(self.can_rps) == 0:
            return None
        target_idx = selectByProbability(self.can_rps_online[:], 1)
        return self.can_rps[target_idx[0]]
        
    def _getOnlineProb(self, ages):    
        oldest_age = 7 * 24 * 60 * 60    # 7 days ago
        benchmark = int(time()) - oldest_age
        probs = []
        for i in xrange(len(ages)):
            prob = (ages[i] - benchmark)/60
            if prob < 0:
                prob = 0
            probs.append(prob)
        return probs
    
    # ---------- recommend items ------------
    def recommendateItems(self, num):
        self._updateItemRecommendation()
        file_list = []
        return file_list[:num]
    
    def _updateItemRecommendation(self):
        pass
    


class BuddyCastFactory:
    __single = None
    
    def __init__(self, db_dir=''):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.secure_overlay = SecureOverlay.getInstance()
        # --- variables ---
        # TODO: add these variables into Config
        self.buddycast_interval = 15
        self.long_block_time = 4*60*60    # 4 hours by default
        self.short_block_time = 5*60    # 4 minutes by default
        self.msg_nbuddies = 10    # number of buddies in buddycast msg
        self.msg_npeers = 10      # number of peers in buddycast msg
        self.msg_nmyprefs = 50    # number of my preferences in buddycast msg
        self.msg_nbuddyprefs = 10 # number of taste buddy's preferences in buddycast msg
        self.max_nworkers = 10    
        # --- others ---
        self.registered = False
        self.rawserver = None
        self.data_handler = DataHandler(db_dir=db_dir)
        self.buddycast_core = BuddyCastCore(self.data_handler)
        self.job_queue = JobQueue(self.max_nworkers)
                
    def getInstance(*args, **kw):
        if BuddyCastFactory.__single is None:
            BuddyCastFactory(*args, **kw)
        return BuddyCastFactory.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, secure_overlay, rawserver, port, errorfunc):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.errorfunc = errorfunc
        self.data_handler.updatePort(port)
        self.registered = True
        self.startup()
        
    def is_registered(self):
        return self.registered
    
    def startup(self):
        if self.registered:
            self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
        print >> sys.stderr, "BuddyCast starts up"

    # ----- message handle -----
    def gotBuddyCastMsg(self, msg):
        def updateDB(prefxchg):
            TasteBuddy(self.data_handler, prefxchg).updateDB()
            for b in prefxchg['taste buddies']:
                TasteBuddy(self.data_handler, b).updateDB()
            for p in prefxchg['random peers']:
                RandomPeer(self.data_handler, p).updateDB()
        
        try:
            buddycast_data = bdecode(msg)
            validBuddyCastData(buddycast_data, self.msg_nmyprefs, self.msg_nbuddies, 
                               self.msg_npeers, self.msg_nbuddyprefs)    # RCP 2
        except:
            print_exc()
            return
        target = buddycast_data['permid']
        if self.data_handler.isRecvBlocked(target):    # RCP 1
            return
        self.data_handler.addToRecvBlockList(target, self.long_block_time)
        updateDB(buddycast_data)
        self.job_queue.addTarget(target, priority=1)

    def sendBuddyCastMsg(self, target, msg):
        print "***send", target, "buddy cast msg:", len(msg), hash(msg)
        print "***blocklist:", self.data_handler.send_block_list.keys()
        
    def BuddyCastMsgSent(self, target):    # msg has been sent, long delay
        self.data_handler.addToSendBlockList(target, self.long_block_time)
    
    # ----- interface for external calls -----
    def doBuddyCast(self):
        self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
        taget = self.job_queue.getTarget()
        worker = self.createWorker(target)
        if worker is not None:
            worker.work()
            del worker

    def createWorker(self, target=None):
        """ 
        Create a worker to send buddycast msg. 
        If target is None, a new target will be selected 
        """
        
        if self.data_handler.isSendBlocked(target):    # if target is None, it is not blocked
            return None
        target, tbs, rps = self.buddycast_core.getBuddyCastData(target, self.msg_nbuddies, self.msg_npeers)
#        print "**", target
#        print "**", tbs
#        print "**", rps
        if target is None:    # could not find a buddycast candidate
            return None
        return BuddyCastWorker(self, target, tbs, rps, self.msg_nmyprefs, self.msg_nbuddyprefs)
        
    def addMyPref(self, infohash, data={}):
        self.data_handler.addMyPref(infohash, data)

    def recommendateItems(self, num):
        self.buddycast_core.recommendateItems(num)
        
