from Tribler.CacheDB.CacheDBHandler import *
from Tribler.__init__ import GLOBAL
from BitTornado.bencode import bencode, bdecode
from Tribler.utilities import isValidIP, print_prefxchg_msg
from similarity import P2PSim

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
        self.prefs = data['preferences']

    def updateDB(self):
        self.updatePeerDB()
        self.updateTorrentDB()
        self.updatePrefDB()
        self.sync()
        
    def updatePeerDB(self):
        self.similarity = self.getSimilarity()
        self.data['similarity'] = self.similarity
        #print "***add peer db:", self.permid, self.data
        self.peer_db.addPeer(self.permid, self.data)
        
    def getSimilarity(self):
        pref1 = self.buddycast.getMyPrefList(50)
        pref2 = self.prefs
        return P2PSim(pref1, pref2)
    
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
        except:
            return
        self.updateDB(prefxchg)
        
    def updateDB(self, prefxchg):
        TasteBuddy(self, prefxchg).updateDB()
        for b in prefxchg['taste buddies']:
            TasteBuddy(self, b).updateDB()
        for p in prefxchg['random peers']:
            RandomPeer(self, p).updateDB()

    def getMyPrefxchg(self, nmyprefs=50, nbuddies=10, npeers=10, nbuddyprefs=10):
        data = {}
        data['ip'] = self.ip
        data['port'] = self.port
        data['permid'] = self.permid
        data['preferences'] = self.getMyPrefList(nmyprefs)
        data['taste buddies'] = self.getTasteBuddies(nbuddies, nbuddyprefs)
        data['random peers'] = self.getRandomPeers(npeers)
        return data
        
    def getMyPrefList(self, num=50):
        return self.mypref_db.getRecentPrefList(num)
        
    def getTasteBuddies(self, nbuddies, nbuddyprefs):
        buddies = []
        return buddies
    
    def getRandomPeers(self, num):
        peers = []
        return peers
    
    
        