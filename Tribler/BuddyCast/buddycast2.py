import sys
from random import sample

from BitTornado.bencode import bencode, bdecode
from Tribler.CacheDB.CacheDBHandler import *
from Tribler.__init__ import GLOBAL
from Tribler.utilities import *
from Tribler.Overlay.SecureOverlay import SecureOverlay
from similarity import P2PSim, selectByProbability

def validBuddycastMsg(prefxchg):
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
        self.preflist = self.getMyRecentPrefList()
    
    def clear(self):
        for db in self.dbs:
            db.clear()
            
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
    
    def getPeerPref(self, permid):
        return self.pref_db.getPreferences(permid)
    
    def getMyRecentPrefList(self, num=0):
        return self.mypref_db.getRecentPrefList(num)
    
    def getMyPrefList(self, num=0):    # num = 0 to return all preflist
        if num > 0:
            return self.preflist[:num]
        else:
            return self.preflist

    def getSimilarity(self, permid, num=0):
        pref1 = self.getMyPrefList(num)
        pref2 = self.getPeerPref(permid).keys()
        return P2PSim(pref1, pref2)
    
    def addMyPref(self, infohash, data={}):    # user adds a preference (i.e., downloads a new file)
        
        def updateSimilarity(infohash):
            owners = self.owner_db.getOwners(infohash)
            for owner in owners:
                sim = self.getSimilarity(owner)
                self.peer_db.updatePeer(owner, 'similarity', sim)
        
        self.preflist.insert(0, infohash)
        self.mypref_db.addPreference(infohash, data)
        updateSimilarity(infohash)
        
    def selectBuddycastCandidate(self, nbuddies=10, npeers=10):
        
        def filter(peer):
            keys = ['ip', 'port', 'permid']
            _peer = {}
            for key in keys:
                _peer[key] = peer[key]
            return _peer

        def getTasteBuddies(peers, num):
            return peers
    
        def getRandomPeers(peers, num):
            return peers[:num]
        
        def getTBPeers(ntb=10, nrp=10):
            pass
        
        def getRecentPeerList(ntb=10, nrp=10):    
            # ntb - number of taste buddies
            # nrp - number of random peers
            
            taste_buddies = []
            rand_peers = []
            peers = self.peer_db._items()
            for i in xrange(len(peers)):
                peers[i][1].update({'permid':peers[i][0]})
                if self.pref_db._has_key(peers[i][0]):
                    taste_buddies.append(peers[i][1])
                else:
                    rand_peers.append(peers[i][1])
            return self.getRecentItems(taste_buddies, ntb), self.getRecentItems(rand_peers, nrp)
        
        def getRecentItems(self, all_items, num):
            items = [(item['last_seen'], item) for item in all_items]
            items.sort()
            items.reverse()
            return [item[1] for item in items[:num]]
                
        alpha = 10
        tbs, rps = self.getRecentPeerList(nbuddies*alpha, npeers)
        pass
            
    
class RandomPeer:
    def __init__(self, data_handler, data):
        self.data_handler = data_handler
        self.permid = data['permid']
        self.ip = data['ip']
        try:
            self.port = int(data['port'])
        except:
            self.port = 0
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
        

class BuddycastWorker:
    def __init__(self, buddycast, target=None):
        self.data_handler = buddycast.data_handler
        self.secure_overlay = buddycast.secure_overlay
        self.ip = target['ip']
        self.port = target['port']
        self.permid = target['permid']
        
    def getBuddycastMsg(self, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):

        def filter(peer):
            keys = ['ip', 'port', 'permid']
            _peer = {}
            for key in keys:
                _peer[key] = peer[key]
            return _peer

        def getPeerPrefList(permid, num=10):
            preflist = self.data_handler.getPeerPref(permid).keys()
            if len(preflist) <= num:
                prefs = preflist
            else:
                prefs = sample(preflist, num)    # randomly select 10 prefs to avoid starvation
            return prefs
            
        def getTasteBuddies(peers, num, nbuddyprefs):
            prob_vec = [peer['similarity'] for peer in peers]
            peers = selectByProbability(prob_vec, peers, num)
            for i in xrange(num):
                peers[i] = filter(peers[i])
                peers[i]['age'] = int(time()) - peers[i]['last_seen']
                if peers[i]['age'] < 0:
                    peers[i]['age'] = 0
                peers[i]['preferences'] = getPeerPrefList(peers[i]['permid'], nbuddyprefs)
            return peers
    
        def getRandomPeers(peers, num):
            for i in xrange(num):
                peers[i] = filter(peers[i])
                peers[i]['age'] = int(time()) - peers[i]['last_seen']
                if peers[i]['age'] < 0:
                    peers[i]['age'] = 0
            return peers
    
        data = {}
        data['ip'] = self.ip
        data['port'] = self.port
        data['permid'] = self.permid
        data['name'] = self.name
        data['preferences'] = self.getMyPrefList(nmyprefs)
        tbs, rps = self.getTBPeers(nbuddies, npeers)
        data['taste buddies'] = getTasteBuddies(tbs, nbuddies, nbuddyprefs)
        data['random peers'] = getRandomPeers(rps, npeers)
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
        print "buddycast starts up"
        
    def addMyPref(self, infohash, data={}):
        self.data_handler.addMyPref(infohash, data)
        
    def gotBuddycastMsg(self, msg):
        def updateDB(prefxchg):
            TasteBuddy(self.data_handler, prefxchg).updateDB()
            for b in prefxchg['taste buddies']:
                TasteBuddy(self.data_handler, b).updateDB()
            for p in prefxchg['random peers']:
                RandomPeer(self.data_handler, p).updateDB()

        try:
            buddycast = bdecode(msg)
            validBuddycastMsg(buddycast)
        except Exception, msg:
            print msg
            return
        updateDB(buddycast)
        BuddyCastWorker(self, buddycast).work()
        
    def doBuddycast(self):
        BuddyCastWorker(self).work()

