import sys
from random import sample
from math import sqrt

from BitTornado.bencode import bencode, bdecode
from Tribler.CacheDB.CacheDBHandler import *
from Tribler.__init__ import GLOBAL
from Tribler.utilities import *
from Tribler.Overlay.SecureOverlay import SecureOverlay
from similarity import P2PSim, P2PSim2, selectByProbability

def validBuddyCastData(prefxchg):
    def validPeer(peer):
        validPermid(peer['permid'])
        validIP(peer['ip'])
        validPort(peer['port'])
    
    def validPref(pref):
        assert isinstance(prefxchg, list) or \
               isinstance(prefxchg, dict)
        for p in pref:
            validInfohash(p)
            
    validPeer(prefxchg)
    assert isinstance(prefxchg['name'], str)
    validPref(prefxchg['preferences'])
    for b in prefxchg['taste buddies']:
        validPeer(b)
        assert isinstance(b['age'], int) and b['age'] >= 0
        validPref(b['preferences'])
    for p in prefxchg['random peers']:
        validPeer(b)
        assert isinstance(b['age'], int) and b['age'] >= 0
    return True


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
        self.preflist = self.getMyRecentPrefList()
        self.connected_list = []    # peer in this list should not be connected in 4 hours
    
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
        
    def getPeerPrefList(self, permid):
        return self.pref_db.getPrefList(permid)
    
    def getMyRecentPrefList(self, num=0):
        return self.mypref_db.getRecentPrefList(num)
    
    def getMyPrefList(self, num=0):    # num = 0 to return all preflist
        if num > 0:
            return self.preflist[:num]
        else:
            return self.preflist[:]
            
    def getPeers(self, peerlist, keys):
        return self.peer_db.getPeers(peerlist, keys)

    #---------- utilities ----------#
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

    def getTBPeerList(self, ntb=0, nrp=0):
        """ get permid lists of taste budies and random peers """
        
        tblist = self.peer_db.getTasteBuddyList()
        rplist = self.peer_db.getRandomPeerList()
        if ntb > 0:
            tblist = tblist[:ntb]
        if nrp > 0:
            rplist = rplist[:nrp]
        return tblist, rplist

    def getTBPeers(self, ntb=0, nrp=0, tb_keys=['permid', 'last_seen', 'similarity'], rp_keys=['permid', 'last_seen']):
        tblist, rplist = self.getTBPeerList(ntb, nrp)
        taste_buddies = self.peer_db.getPeers(tblist, tb_keys)
        rand_peers = self.peer_db.getPeers(rplist, rp_keys)
        return taste_buddies, rand_peers

                
    #---------- core ----------#
    
#    def selectBuddyCastCandidate(self, nbuddies=10, npeers=10):
#        # TODO: new algorithm
#        def filter(peer):
#            keys = ['ip', 'port', 'permid']
#            _peer = {}
#            for key in keys:
#                _peer[key] = peer[key]
#            return _peer
#
#        def getTasteBuddies(peers, num):
#            return peers
#    
#        def getRandomPeers(peers, num):
#            return peers[:num]
#        
#        alpha = 10
#        tbs, rps = self.TBPeers(nbuddies*alpha, npeers)
#        pass
#
#    def getMsgTBPeers(self, ntb=10, nrp=10):    
#        # ntb - number of taste buddies
#        # nrp - number of random peers
#        
#        taste_buddies = []
#        rand_peers = []
#        peers = self.peer_db.getItems()
#        for i in xrange(len(peers)):
#            peers[i][1].update({'permid':peers[i][0]})
#            if self.pref_db.hasPreference(peers[i][0]):
#                taste_buddies.append(peers[i][1])
#            else:
#                rand_peers.append(peers[i][1])
#        return self.getRecentItems(taste_buddies, ntb), self.getRecentItems(rand_peers, nrp)
#    

    def getMsgTBPeers(self, ntb=10, nrp=10):    
        """ get taste buddies and random peers for buddycast msg """
        
        tbs, rps = self.getTBPeers()
        
        
        return tbs, rps
        

    
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
    def __init__(self, buddycast, target=None):
        self.data_handler = buddycast.data_handler
        self.secure_overlay = buddycast.secure_overlay
        if not target:
            target = self.getBuddyCastTarget()
        self.ip = target['ip']
        self.port = int(target['port'])
        self.permid = target['permid']
        self.name = target.get('name', '')
            
    def getBuddyCastTarget(self):
        target = {'ip':'1.2.3.4', 'port':1234, 'permid':'permid1'}
        return target
        
    def getBuddyCastMsg(self, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):

        def getPeerPrefList(permid, num=10):
            preflist = self.data_handler.getPeerPrefList(permid)
            if len(preflist) <= num:
                prefs = preflist
            else:
                prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
            
        def getTasteBuddies(peerlist, nbuddyprefs):
            peers = self.data_handler.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
            for i in xrange(len(peers)):
                peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
                if peers[i]['age'] < 0:
                    peers[i]['age'] = 0
                peers[i]['preferences'] = getPeerPrefList(peers[i]['permid'], nbuddyprefs)
            return peers
    
        def getRandomPeers(peerlist):
            peers = self.data_handler.getPeers(peerlist, ['permid', 'ip', 'port', 'last_seen'])
            for i in xrange(len(peers)):
                peers[i]['age'] = int(time()) - peers[i].pop('last_seen')
                if peers[i]['age'] < 0:
                    peers[i]['age'] = 0
            return peers
    
        data = {}
        data['ip'] = self.ip
        data['port'] = self.port
        data['permid'] = self.permid
        data['name'] = self.data_handler.name
        data['preferences'] = self.data_handler.getMyPrefList(nmyprefs)
        tbs, rps = self.data_handler.getMsgTBPeers(nbuddies, npeers)
        data['taste buddies'] = getTasteBuddies(tbs, nbuddyprefs)
        data['random peers'] = getRandomPeers(rps)
        return data
    
    def work(self):
        pass
    

class BuddyCastFactory:
    __single = None
    
    def __init__(self, db_dir=''):
        if BuddyCastFactory.__single:
            raise RuntimeError, "BuddyCastFactory is singleton"
        BuddyCastFactory.__single = self 
        self.data_handler = DataHandler(db_dir)
        self.secure_overlay = SecureOverlay.getInstance()
        # --- constants ---
        self.buddycast_interval = GLOBAL.do_buddycast_interval
        self.rawserver = None
        self.registered = False
                
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
            validBuddyCastData(buddycast_data)
        except Exception, msg:
            print >> sys.stderr, msg
            return
        updateDB(buddycast_data)
        b = BuddyCastWorker(self, buddycast_data)
        b.work()
        del b
        
    def doBuddyCast(self):
        b = BuddyCastWorker(self)
        b.work()
        del b

    def recommendateItems(self):
        self.data_handler.recommendateItems()
        
        