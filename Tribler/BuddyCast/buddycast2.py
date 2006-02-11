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


        
class DataHandler:
    def __init__(self, block_time, db_dir=''):
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
        self.preflist = self.getMyRecentPrefList()
        
        self.block_time = block_time
        self.block_list = {}
        
        self.uniform_distr = [1]*100
        self.poisson_distr = self.readDistribution('poisson_cdf.txt')
        self.online_pdf = self.poisson_distr
    
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
        
    def addPeer(self, permid, data):
        self.peer_db.addPeer(permid, data)
        
    def addTorrent(self, infohash):
        self.torrent_db.addTorrent(infohash)
    
    def addPeerPref(self, permid, pref):
        self.pref_db.addPreference(permid, pref)
    
    def addMyPref(self, infohash, data={}):    # user adds a preference (i.e., downloads a new file)
        
        def updateSimilarity(infohash):
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
        
        existed = self.preflist.count(infohash)    
        if existed:
            self.preflist.remove(infohash)
        self.preflist.insert(0, infohash)
        self.mypref_db.addPreference(infohash, data)    # update last_seen if the pref exists
        if not existed:    # don't update similarity if the pref exists
            updateSimilarity(infohash)
        
    def getPeerPrefList(self, permid, num=0):
        preflist = self.pref_db.getPrefList(permid)
        if num == 0:
            return preflist
        else:
            prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
    
    def getMyRecentPrefList(self, num=0):
        return self.mypref_db.getRecentPrefList(num)
    
    def getMyPrefList(self, num=0):    # num = 0 to return all preflist
        if num > 0:
            return self.preflist[:num]
        else:
            return self.preflist[:]
            
    def getPeers(self, peerlist, keys):
        return self.peer_db.getPeers(peerlist, keys)

    def getTBPeerList(self, ntb=0, nrp=0):
        """ get permid lists of taste budies and random peers """
        
        tblist = self.peer_db.getTasteBuddyList()
        rplist = self.peer_db.getRandomPeerList()
        if ntb > 0:
            tblist = tblist[:ntb]
        if nrp > 0:
            rplist = rplist[:nrp]
        return tblist, rplist

    def getTBPeerValues(self, tblist, rplist, tb_keys=['similarity'], rp_keys=['last_seen']):
        taste_buddies = self.peer_db.getPeersValue(tblist, tb_keys)
        rand_peers = self.peer_db.getPeersValue(rplist, rp_keys)
        return taste_buddies, rand_peers
        
    def getTasteBuddies(self, peerlist, nbuddyprefs):
        peers = self.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
        for i in xrange(len(peers)):
            peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
            if peers[i]['age'] < 0:
                peers[i]['age'] = 0
            peers[i]['preferences'] = self.getPeerPrefList(peers[i]['permid'], nbuddyprefs)
        return peers

    def getRandomPeers(self, peerlist):
        peers = self.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
        for i in xrange(len(peers)):
            peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
            if peers[i]['age'] < 0:
                peers[i]['age'] = 0
        return peers        
                
    #---------- utilities ----------#
    def readDistribution(self, filename):
        try:
            pdf_file = open(filename, 'r')
        except:
            print >> sys.stderr, "cannot open online pdf file", filename
            return self.uniform_distr    # uniform distribution

        datalines = pdf_file.readlines()
        pdf = []
        for line in datalines:
            line.strip()
            if line.startswith('#'):
                continue
            linedata = line.split()
            for data in linedata:
                try:
                    x = float(data)
                    if x >= 0:
                        pdf.append(x)
                except:
                    print >> sys.stderr, "wrong number in file", data
                    pass
        return pdf
    
    def getSimilarity(self, permid, num=0):
        pref1 = self.getMyPrefList(num)
        pref2 = self.getPeerPrefList(permid)
        sim = P2PSim(pref1, pref2)
        return sim
    
    def getRecentItems(self, all_items, num):
        items = [(item['last_seen'], item) for item in all_items]
        items.sort()
        items.reverse()
        return [item[1] for item in items[:num]]

    # --------- block list --------#
    def addToBlockList(self, permid):
        self.block_list[permid] = int(time()) + self.block_time
        
    def isBlocked(self, permid):
        if not self.block_list.has_key(permid):
            return False
        elif self.block_list[permid] < int(time()):
            self.block_list.pop(permid)        
            return False
        else:
            return True

    #---------- core ----------#
    
    def getBuddyCastData(self, target=None, ntb=10, nrp=10):    
        """ get taste buddies and random peers for buddycast msg """
        
        tblist, rplist = self.getTBPeerList()
        tbs_sim, rps_age = self.getTBPeerValues(tblist, rplist)
        if target is None:
            target = self.selectTarget(tbs_sim, rps_age)
            if target is None:    # no target can be select, stop
                return None, [], []
        tbs = self.selectTasteBuddies(tbs_sim, tblist, ntb)
        rps = self.selectRandomPeers(rps_age, rplist, nrp)
        return target, tbs, rps

    def selectTarget(self, tbs_sim, rps_age):
        r = random()
        target = 'peer_' + str(randint(1, 1000))
        if r < 0.5:    # get a random peer
            pass
        if self.isBlocked(target):
            return None
        
        
        return target

    def selectTasteBuddies(self, tbs_sim, tblist, ntb):

        def selectTBByTopSim(tbs_sim, tblist, ntb):    
            """ get top similar taste buddies """
            
            aux = [(tbs_sim[i], tblist[i]) for i in range(len(tblist))]
            aux.sort()
            aux.reverse()
            ret = []
            for i in xrange(ntb):
                ret.append(aux[i][1])
            return ret
    
        def selectTBBySimProb(tbs_sim, tblist, ntb):
            """ get taste buddies based on their similarity """
            
            tbs_pdf = self.getTasteBuddiesPDF(tbs_sim)    # Probability Density Function of Taste Buddies
            tbs = selectByProbability(tbs_pdf, tblist, ntb)
            return tbs
        

        assert len(tbs_sim) == len(tblist), (len(tbs_sim), len(tblist))
        return selectTBByTopSim(tbs_sim, tblist, ntb)
    
    def selectRandomPeers(self, rps_age, rplist, nrp):
        rps_pdf = self.getRandPeersPDF(rps_age)   # Probability Density Function of Random Peers
        rps = selectByProbability(rps_pdf, rplist, nrp)
        return rps
        
    def getTasteBuddiesPDF(self, sims):    # simply use similarity as probablity
        return sims
        
    def getRandPeersPDF(self, ages):
        """ get online probability based on peer's last seen """
        
        aux = []
        nlist = len(ages)
        npdf = len(self.online_pdf)
        for i in xrange(nlist):
            aux.append([ages[i], i])
        aux.sort()
        aux.reverse()
        for i in xrange(nlist):
            idx = int(1.0*i*npdf/nlist)
            prob = self.online_pdf[idx]
            aux[i] = aux[i][1], prob
        aux.sort()
        for i in xrange(nlist):
            aux[i] = aux[i][1]
        return aux
        
    
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
        data = {}
        data['ip'] = self.data_handler.ip
        data['port'] = self.data_handler.port
        data['permid'] = self.data_handler.permid
        data['name'] = self.data_handler.name
        data['preferences'] = self.data_handler.getMyPrefList(self.nmyprefs)
        data['taste buddies'] = self.data_handler.getTasteBuddies(self.tbs, self.nbuddyprefs)
        data['random peers'] = self.data_handler.getRandomPeers(self.rps)
        self.data = data
        return data
        
    def work(self):
        try:
            validPermid(self.target)
            msg_data = self.getBuddyCastMsgData()
            buddycast_msg = bencode(msg_data)
        except:
            print_exc()
            print >> sys.stderr, "error in bencode buddycast msg"
            return
        if not self.data_handler.isBlocked(self.target):
            self.factory.sendBuddyCast(self.target, buddycast_msg)
        self.data_handler.addToBlockList(self.target)
        

class WorkerQueue:
    def __init__(self, factory, max_size=10):
        self.factory = factory
        self.max_size = max_size
        self._queue = []

    def _addWorker(self, worker, position=None):    # position = None: append at tail
        if position is None:
            if isinstance(worker, list):
                for w in worker:
                    if len(self._queue) < self.max_size:
                        self._queue.append(w)
            else:
                if len(self._queue) < self.max_size:
                    self._queue.append(worker)
        else:
            if isinstance(worker, list):
                worker.reverse()
                for w in worker:
                    self._queue.insert(position, w)
                    if len(self._queue) > self.max_size:
                        self._queue.pop(len(self._queue)-1)
                    
            else:
                self._queue.insert(position, worker)
                if len(self._queue) > self.max_size:
                    self._queue.pop(len(self._queue)-1)
                
    def addWorker(self, worker, priority=0):    # priority: the biger the higher
        if not worker:
            return
        if priority == 0:
            self._addWorker(worker)
        elif priority > 0:
            self._addWorker(worker, 0)
            
    def getWorker(self):
        if len(self._queue) > 0:
            return self._queue.pop(0)
        else:
            return self.factory.createWorker()


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
        self.block_time = 4*60*60    # 4 hours by default
        self.msg_nbuddies = 10    # number of buddies in buddycast msg
        self.msg_npeers = 10      # number of peers in buddycast msg
        self.msg_nmyprefs = 50    # number of my preferences in buddycast msg
        self.msg_nbuddyprefs = 10 # number of taste buddy's preferences in buddycast msg
        self.max_nworkers = 10    
        # --- others ---
        self.data_handler = DataHandler(block_time=self.block_time, db_dir=db_dir)
        self.rawserver = None
        self.registered = False
        self.worker_queue = WorkerQueue(self, self.max_nworkers)
        self.reply_policy = 0    # 0: don't reply soon, but put worker in job queue instead
                                 # 1: reply buddycast right now
                
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
        
        
    def addMyPref(self, infohash, data={}):
        self.data_handler.addMyPref(infohash, data)
        
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
        if self.data_handler.isBlocked(target):    # RCP 1
            return
        updateDB(buddycast_data)
        worker = self.createWorker(target)
        if self.reply_policy == 0:        # RCP 3
            self.worker_queue.addWorker(worker, 1)
        elif self.reply_policy == 1:    
            worker.work()
            del worker

    def createWorker(self, target=None):    
        """ 
        Create a worker to send buddycast msg. 
        If target is None, a target will be selected 
        """
        
        target, tbs, rps = self.data_handler.getBuddyCastData(target, self.msg_nbuddies, self.msg_npeers)
        if target is not None:
            return BuddyCastWorker(self, target, tbs, rps, self.msg_nmyprefs, self.msg_nbuddyprefs)
        else:
            return None
        
        
    def doBuddyCast(self):
        self.rawserver.add_task(self.doBuddyCast, self.buddycast_interval)
        b = self.worker_queue.getWorker()
        if b is not None:
            b.work()
            del b

    def recommendateItems(self):
        self.data_handler.recommendateItems()
        
    def sendBuddyCast(self, target, msg):
        print self.data_handler.block_list
        print "send", target, "buddy cast msg:", len(msg), hash(msg)
        