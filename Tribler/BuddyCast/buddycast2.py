from Tribler.CacheDB.CacheDBHandler import *
from Tribler.__init__ import GLOBAL
from BitTornado.bencode import bencode, bdecode
from Tribler.utilities import *
from similarity import P2PSim, selectByProbability
from random import sample


class RandomPeer:
    def __init__(self, buddycast, data):
        self.buddycast = buddycast
        self.peer_db = self.buddycast.peer_db
        self.dbs = [self.peer_db]
        
        self.permid = data['permid']
        self.ip = data['ip']
        self.name = data.get('name', '')
        try:
            self.port = int(data['port'])
        except:
            self.port = 0
        age = data.get('age', 0)
        self.last_seen = int(time()) - age
        if not isValidIP(self.ip) or self.port == 0:
            self.connectable = False
        else:
            self.connectable = True
        self.data = {'ip':self.ip, 'port':self.port, 'name':self.name, 'last_seen':self.last_seen}
    
    def sync(self):
        for db in self.dbs:
            db.sync()
    
    def updateDB(self):
        self.updatePeerDB()
                     
    def updatePeerDB(self):
        #print "***add peer db:", self.permid, self.data
        self.peer_db.addPeer(self.permid, self.data)
         
         
class TasteBuddy(RandomPeer):
    def __init__(self, buddycast, data):
        RandomPeer.__init__(self, buddycast, data)
        self.torrent_db = self.buddycast.torrent_db
        self.pref_db = self.buddycast.pref_db
        self.dbs += [self.torrent_db, self.pref_db]
        self.mypref_db = self.buddycast.mypref_db
        if isinstance(data['preferences'], list):
            self.prefs = data['preferences']
        elif isinstance(data['preferences'], dict):
            self.prefs = data['preferences'].keys()
        else:
            self.prefs = []

    def updateDB(self):
        self.updatePeerDB()
        self.updateTorrentDB()
        self.updatePrefDB()
        self.sync()
        
    def updatePeerDB(self):
        
        def getSimilarity(num):
            pref1 = self.buddycast.getMyPrefList(num)
            pref2 = self.prefs
            return P2PSim(pref1, pref2)
        
        self.similarity = getSimilarity(100)
        self.data['similarity'] = self.similarity
        #print "***add peer db:", self.permid, self.data
        self.peer_db.addPeer(self.permid, self.data)
        
    def updateTorrentDB(self):
        #print "^^^add torrent db:", self.prefs
        for t in self.prefs:
            self.torrent_db.addTorrent(t)
            
    def updatePrefDB(self):
        for pref in self.prefs:
            self.pref_db.addPreference(self.permid, pref)
        


class BuddyCast:
    __single = None
    
    def __init__(self, db_dir=''):
        if BuddyCast.__single:
            raise RuntimeError, "BuddyCast is singleton"
        BuddyCast.__single = self 
        # --- database handlers ---
        self.my_db = MyDBHandler(db_dir=db_dir)
        self.peer_db = PeerDBHandler(db_dir=db_dir)
        self.superpeer_db = SuperPeerDBHandler(db_dir=db_dir)
        self.friend_db = FriendDBHandler(db_dir=db_dir)
        self.torrent_db = TorrentDBHandler(db_dir=db_dir)
        self.mypref_db = MyPreferenceDBHandler(db_dir=db_dir)
        self.pref_db = PreferenceDBHandler(db_dir=db_dir)
        self.owner_db = OwnerDBHandler(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db, self.superpeer_db, self.friend_db,
                    self.torrent_db, self.mypref_db, self.pref_db, self.owner_db]
        # --- constants. they should be stored in mydb ---
        self.max_bc_len = 30     # max buddy cache length
        self.max_rc_len = 100    # max random peer cache length
        self.max_pc_len = 100    # max my preference cache length
        
        self.max_pl_len = 10     # max amount of preferences in prefxchg message
        self.max_tb_len = 10     # max amount of taste buddies in prefxchg message
        self.max_rp_len = 10     # max amount of random peers in prefxchg message
        self.max_pcq_len = 3     # max prefxchg_candidate_queue length
        
        self.buddycast_interval = GLOBAL.do_buddycast_interval
        # --- variables ---
        self.my_ip = ''
        self.my_port = 0
        self.my_name = ''
        self.my_prefxchg_msg = {}
        self.rawserver = None
        self.registered = False
                
    def getInstance(*args, **kw):
        if BuddyCast.__single is None:
            BuddyCast(*args, **kw)
        return BuddyCast.__single
    getInstance = staticmethod(getInstance)
    
    def clear(self):
        for db in self.dbs:
            db.clear()
            
    def sync(self):
        for db in self.dbs:
            db.sync()
        
    def register(self, secure_overlay, rawserver, port, errorfunc):    
        if self.registered:
            return
        self.secure_overlay = secure_overlay
        self.rawserver = rawserver
        self.errorfunc = errorfunc
        self.my_name = self.my_db.get('name')
        self.my_ip = self.my_db.get('ip')
        self.my_port = port
        self.my_db.put('port', port)
        self.my_db.sync()
        self.registered = True
        self.startup()
        
    def is_registered(self):
        return self.registered
    
    def startup(self):
        print "buddycast starts up"
        
    def gotPrefxchg(self, msg):
        try:
            prefxchg = bdecode(msg)
            if not self.validPrefxchg(prefxchg):
                print "invalid pref"
                return
        except:
            return
        self.updateDB(prefxchg)
        
    def validPrefxchg(self, prefxchg):
        def validPeer(peer):
            validPermid(peer['permid'])
            validIP(peer['ip'])
            validPort(peer['port'])
        
        def validPref(pref):
            assert isinstance(prefxchg, list) or \
                   isinstance(prefxchg, dict)
            for p in pref:
                validInfohash(p)
                
        try:
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
        except Exception, msg:
            print Exception, msg
            return False
        return True
        
    def updateDB(self, prefxchg):
        TasteBuddy(self, prefxchg).updateDB()
        for b in prefxchg['taste buddies']:
            TasteBuddy(self, b).updateDB()
        for p in prefxchg['random peers']:
            RandomPeer(self, p).updateDB()
            
    def addMyPref(self, infohash, data={}):
        
        def getSimilarity(permid):
            pref1 = self.getMyPrefList(100)
            pref2 = self.pref_db.getPreferences(permid).keys()
            return P2PSim(pref1, pref2)
        
        def updateSimilarity(infohash):
            owners = self.owner_db.getOwners(infohash)
            for owner in owners:
                sim = getSimilarity(owner)
                self.peer_db.updatePeer(owner, 'similarity', sim)
        
        self.mypref_db.addPreference(infohash, data)
        updateSimilarity(infohash)
        
    def getMyPrefList(self, num=0):    # num = 0 to return all preflist
        return self.mypref_db.getRecentPrefList(num)
    
    def getMyPrefxchg(self, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):

        def filter(peer):
            keys = ['ip', 'port', 'permid']
            _peer = {}
            for key in keys:
                _peer[key] = peer[key]
            return _peer

        def getPeerPrefList(permid, num=10):
            preflist = self.pref_db.getPreferences(permid).keys()
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
            if num > len(peers):
                num = len(peers)
            for i in xrange(num):
                peers[i] = filter(peers[i])
                peers[i]['age'] = int(time()) - peers[i]['last_seen']
                if peers[i]['age'] < 0:
                    peers[i]['age'] = 0
            return peers[:num]
    

        alpha = 10
        data = {}
        data['ip'] = self.ip
        data['port'] = self.port
        data['permid'] = self.permid
        data['name'] = self.name
        data['preferences'] = self.getMyPrefList(nmyprefs)
        tbs, rps = self.peer_db.getRecentPeerList(nbuddies*alpha, npeers)
        data['taste buddies'] = getTasteBuddies(tbs, nbuddies, nbuddyprefs)
        data['random peers'] = getRandomPeers(rps, npeers)
        return data

    def selectPrefxchgCandidate(self, nbuddies=10, npeers=10):
        
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
        
        
        alpha = 10
        tbs, rps = self.peer_db.getRecentPeerList(nbuddies*alpha, npeers)
        pass