# Written by Jie Yang
# see LICENSE.txt for license information

from cachedb import *
from time import time
from copy import deepcopy


class BasicDBHandler:
    def __init__(self):
        self.dbs = []
        
    def __del__(self):
        self.sync()

    def sync(self):
        for db in self.dbs:
            db._sync()
            
    def clear(self):
        for db in self.dbs:
            db._clear()
            
            
class MyDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.my_db = MyDB.getInstance(db_dir = db_dir)
        self.peer_db = PeerDB.getInstance(db_dir = db_dir)
        self.dbs = [self.my_db, self.peer_db]
        
    def get(self, key):
        return self.my_db._get(key)

    def put(self, key, value):
        self.my_db._put(key, value)
    
#    def printList(self):
#        data = self.my_db.items()
#        print "========== all records in MyDB table =========="
#        for item in data:
#            print item
#            
#    def getSuperPeersPermID(self):
#        return self.my_db.get('superpeers', [])
#    
#    def getSuperPeers(self):
#        sp = self.my_db.get('superpeers', [])
#        res = []
#        for permid in sp:
#            peer = self.peer_db.get(permid)
#            if peer:
#                res.append(peer)
#        return res
#
#    def addSuperPeer(self, permid):
#        if permid in self.my_db.get('superpeers'):
#            return
#        if self.peer_db.has_key(permid):
#            superpeers = self.getSuperPeers()
#            superpeers.append(permid)
#            self.my_db.update({'superpeers':superpeers})
#
#    def addSuperPeerByPeer(self, peer):
#        permid = peer['permid']
#        if not self.peer_db.has_key(permid):
#            self.peer_db.updateItem(peer)
#        superpeers = self.my_db.get('superpeers')
#        if permid in superpeers:
#            return
#        superpeers.append(permid)
#        self.my_db.update({'superpeers':superpeers})
#
#    def removeSuperPeer(self, permid):
#        try:
#            superpeers = self.getSuperPeers()
#            superpeers.remove(permid)
#            self.my_db.update({'superpeers':superpeers})
#        except:
#            pass
#        
#    def getPrefxchgQueue(self):
#        return self.my_db.get('prefxchg_queue', [])
#    
#    def setPrefxchgQueue(self, q):
#        self.my_db.put('prefxchg_queue', q)


class SuperPeerDBHandler(BasicDBHandler):
    def __init__(self, db_dir=''):
        self.my_db = MyDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db]
        
    def getSuperPeers(self):
        sps = self.my_db.getSuperPeers()
        res = []
        for permid in sps:
            peer = self.peer_db.getItem(permid)
            if peer is not None:
                peer.update({'permid':permid})
                res.append(peer)
        return res
        
    def addSuperPeer(self, permid):
        self.my_db.addSuperPeer(permid)
        self.my_db._sync()        

    def addExternalSuperPeer(self, superpeer):
        if not isinstance(superpeer, dict) or 'permid' not in superpeer:
            return
        permid = superpeer.pop('permid')
        self.peer_db.updateItem(permid, superpeer)
        self.peer_db._sync()
        self.my_db.addSuperPeer(permid)
        self.my_db._sync()     
           

class FriendDBHandler(BasicDBHandler):

    def __init__(self, db_dir=''):
        self.my_db = MyDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.my_db, self.peer_db]
        
    def addExternalFriend(self, friend):
        if not isinstance(friend, dict) or 'permid' not in friend:
            return
        permid = friend.pop('permid')
        self.peer_db.updateItem(permid, friend)
        self.peer_db._sync()
        self.my_db.addFriend(permid)
        self.my_db._sync()
            
    def getFriends(self):
        ids = self.my_db.getFriends()
        friends = []
        for id in ids:
            peer = self.peer_db.getItem(id)
            if peer:
                peer.update({'permid':id})
                friends.append(peer)
        return friends
                    
            
class PeerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.peer_db]
        
    def __len__(self):
        return self.peer_db._size()
        
    def getPeer(self, permid):
        return self.peer_db.getItem(permid)
    
    def addPeer(self, permid, value):
        self.peer_db.updateItem(permid, value)
        
    def hasPeer(self, permid):
        return self.peer_db.hasItem(permid)        

    def findPeers(self, key, value):
        res = []
        if key is 'permid':
            peer = self.getPeer(value)
            if peer:
                peer.update({'permid':value})
                res.append(peer)
        else:
            for permid, peer in self.peer_db._items():
                try:
                    if peer[key] == value:
                        peer.update({'permid':permid})
                        res.append(peer)
                except KeyError:
                    pass
        return res
    
    def updatePeerIPPort(self, permid, ip, port):
        self.peer_db.updateItem(permid, {'ip':ip, 'port':port})
    
#    def getAllPeers(self, key=None):
#        all_values = self.peer_db.values()
#        if key is None:
#            return all_values
#        else:
#            return [all_values[i][key] for i in xrange(len(all_values))]
#        
#    def getPeers(self, key, value):
#        all_peers = self.peer_db.values()
#        res = []
#        try:
#            for peer in all_peers:
#                if peer[key] == value:
#                    res.append(peer)
#        except:
#            pass    # key error
#        return res
#    
#    def printList(self):
#        records = self.peer_db.values()
#        print "========== all records in peer table ==========", len(records)
#        for record in records:
#            print record
#        
#    def filter(self, peer):
#        default_keys = self.peer_db.default_data.keys()
#        for key in peer.keys():
#            if key not in default_keys:
#                peer.pop(key)
#            
#    def updatePeer(self, peer):
#        self.peer_db.updateItem(peer)
#        
#    def updatePeerIPPort(self, permid, ip, port):
#        peer = {'permid':permid, 'ip':ip, 'port':port}
#        self.peer_db.updateItem(peer)
#        
#    def updatePeerTrust(self, permid, trust):
#        peer = {'permid':permid, 'my_trust':trust}
#        self.peer_db.updateItem(peer)
#        
#    def updatePeerSim(self, permid, sim):
#        peer = {'permid':permid, 'similarity':sim}
#        self.peer_db.updateItem(peer)
#        
#    def hasPermID(self, permid):
#        return self.peer_db.has_key(permid)
#        


class PreferenceDBHandler:
    
    def __init__(self):
        self.preferences = PreferenceDB.getInstance()
        self.owners = OwnerDB.getInstance()
        self.torrents = TorrentDB.getInstance()
        self.peer_db = PeerDB.getInstance()
        
    def __del__(self):
        self.sync()
    
    def sync(self):
        self.preferences.sync()
        self.owners.sync()
        self.torrents.sync()
    
    def printList(self):
        records = self.preferences.items()
        print "========== all records in preferences table ==========", len(records)
        for record in records:
            print record
            
    def size(self):
        return self.preferences.size()            
            
    def getPreferences(self, permid):
        return self.preferences.get(permid, {})

    def addPreferences(self, permid, preferences):
#        if not self.peer_db.has_key(permid):
#            peer = {'permid':permid}
#            self.peer_db.updateItem(peer)
        for torrent in preferences:
            self.addPreference(permid, torrent, preferences[torrent])

    def addPreference(self, permid, torrent_hash, data):
        if not self.torrents.has_key(torrent_hash):
            torrent = {'torrent_hash':torrent_hash}
            self.torrents.updateItem(torrent)
        self.preferences.addPreference(permid, torrent_hash, data)
        self.owners.addOwner(torrent_hash, permid)

    def deletePreference(self, permid, torrent_hash):
        self.torrents.deletePreference(permid, torrent_hash)
        
        
class TorrentDBHandler:

    def __init__(self):
        self.torrents = TorrentDB.getInstance()
        
    def __del__(self):
        self.sync()
    
    def sync(self):
        self.torrents.sync()
        
    def printList(self):
        records = self.torrents.values()
        print "========== all records in torrent table ==========", len(records)
        for record in records:
            print record
            
    def size(self):
        return self.torrents.size()

    def addTorrent(self, torrent, have=1):
        torrent.update({'have':have})
        self.torrents.updateItem(torrent)
        self.sync()
        
    def getTorrent(self, torrent_hash):
        return self.torrents.get(torrent_hash)
            
    def findTorrent(self, torrent_hash=None, torrent_id=None):    # find both id and hash
        pass

    def updateTorrentRank(self, torrent_hash, rank):
        pass
            
    def updateTorrent(self, torrent_hash, torrent):
        pass
        
    def removeTorrent(self, torrent_hash):
        pass
    

class MyPreferenceDBHandler:
    
    def __init__(self):
        self.myprefs = MyPreferenceDB.getInstance()
        self.torrents = TorrentDB.getInstance()
    
    def __del__(self):
        self.sync()
    
    def sync(self):
        self.myprefs.sync()
        self.torrents.sync()
            
    def size(self):
        return self.myprefs.size()
            
    def getPreferences(self, key=None):
        all_values = self.myprefs.values()
        if key is None:
            return all_values
        else:
            return [all_values[i][key] for i in xrange(len(all_values))]
    
    def addPreference(self, torrent_hash):
        torrent={}
        torrent.update({'torrent_hash':torrent_hash})
        _torrent = deepcopy(torrent)
        _torrent.update({'have':1})
        self.myprefs.updateItem(torrent_hash, torrent)
        self.torrents.updateItem(_torrent)
        self.sync()

    def deletePreference(self, torrent_hash):
        self.myprefs.deleteItem(torrent_hash)
        
    def printList(self):
        records = self.myprefs.items()
        print "========== all records in my preferences table ==========", len(records)
        for key, value in records:
            print key, value 


class OwnerDBHandler:
    
    def __init__(self):
        self.owners = OwnerDB.getInstance()
        self.torrents = TorrentDB.getInstance()
        self.peer_db = PeerDB.getInstance()
        self.myprefs = MyPreferenceDB.getInstance()
        
    def __del__(self):
        self.sync()
    
    def sync(self):
        self.owners.sync()
        
    def getOwners(self, torrent_hash):
        return self.owners.get(torrent_hash)
        
    def getAllOwners(self):
        return self.owners.items()
        
    def printList(self):
        records = self.owners.items()
        print "========== all records in owner table ==========", len(records)
        for key, value in records:
            print key, value 
    
def test_mydb():
    mydb = MyDBHandler()
    
def test_all():
    test_mydb()
    
if __name__ == '__main__':
    test_all()