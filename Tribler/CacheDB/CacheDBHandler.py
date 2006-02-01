# Written by Jie Yang
# see LICENSE.txt for license information

from cachedb import *
from time import time
from copy import deepcopy


class MyDBHandler:
    
    def __init__(self):
        self.mydb = MyDB.getInstance()
        self.peers = PeerDB.getInstance()
        
    def __del__(self):
        self.sync()

    def sync(self):
        self.mydb.sync()
        self.peers.sync()
    
    def printList(self):
        data = self.mydb.items()
        print "========== all records in MyDB table =========="
        for item in data:
            print item
            
    def get(self, key):
        return self.mydb.get(key)

    def put(self, key, value):
        self.mydb.put(key, value)
    
    def getSuperPeersPermID(self):
        return self.mydb.get('superpeers', [])
    
    def getSuperPeers(self):
        sp = self.mydb.get('superpeers', [])
        res = []
        for permid in sp:
            peer = self.peers.get(permid)
            if peer:
                res.append(peer)
        return res

    def addSuperPeer(self, permid):
        if permid in self.mydb.get('superpeers'):
            return
        if self.peers.has_key(permid):
            superpeers = self.getSuperPeers()
            superpeers.append(permid)
            self.mydb.update({'superpeers':superpeers})

    def addSuperPeerByPeer(self, peer):
        permid = peer['permid']
        if not self.peers.has_key(permid):
            self.peers.updateItem(peer)
        superpeers = self.mydb.get('superpeers')
        if permid in superpeers:
            return
        superpeers.append(permid)
        self.mydb.update({'superpeers':superpeers})

    def removeSuperPeer(self, permid):
        try:
            superpeers = self.getSuperPeers()
            superpeers.remove(permid)
            self.mydb.update({'superpeers':superpeers})
        except:
            pass
        
    def getPrefxchgQueue(self):
        return self.mydb.get('prefxchg_queue', [])
    
    def setPrefxchgQueue(self, q):
        self.mydb.put('prefxchg_queue', q)
        
            
class PeerDBHandler:
    
    def __init__(self):
        self.peers = PeerDB.getInstance()

    def __del__(self):
        self.sync()
    
    def sync(self):
        self.peers.sync()
        
    def size(self):
        return self.peers.size()

    def getAllPeers(self, key=None):
        all_values = self.peers.values()
        if key is None:
            return all_values
        else:
            return [all_values[i][key] for i in xrange(len(all_values))]
        
    def getPeers(self, key, value):
        all_peers = self.peers.values()
        res = []
        try:
            for peer in all_peers:
                if peer[key] == value:
                    res.append(peer)
        except:
            pass    # key error
        return res
    
    def printList(self):
        records = self.peers.values()
        print "========== all records in peer table ==========", len(records)
        for record in records:
            print record
        
    def filter(self, peer):
        default_keys = self.peers.default_data.keys()
        for key in peer.keys():
            if key not in default_keys:
                peer.pop(key)
            
    def updatePeer(self, peer):
        self.peers.updateItem(peer)
        
    def updatePeerIPPort(self, permid, ip, port):
        peer = {'permid':permid, 'ip':ip, 'port':port}
        self.peers.updateItem(peer)
        
    def updatePeerTrust(self, permid, trust):
        peer = {'permid':permid, 'my_trust':trust}
        self.peers.updateItem(peer)
        
    def updatePeerSim(self, permid, sim):
        peer = {'permid':permid, 'similarity':sim}
        self.peers.updateItem(peer)
        
    def getPeer(self, permid):
        return self.peers.get(permid)
        
    def hasPeer(self, peer):
        permid = peer['permid']
        return self.hasPermID(permid)
        
    def hasPermID(self, permid):
        return self.peers.has_key(permid)
        
    def findPeers(self, key, value):
        res = []
        if key not in self.peers.default_peer:
            pass
        elif key is 'permid':
            peer = self.getPeer(value)
            if peer:
                res.append(peer)
        else:
            try:
                for peer in self.peers.values():
                    if peer[key] == value:
                        res.append(peer)
            except KeyError:
                pass
        return res
        

class PreferenceDBHandler:
    
    def __init__(self):
        self.preferences = PreferenceDB.getInstance()
        self.owners = OwnerDB.getInstance()
        self.torrents = TorrentDB.getInstance()
        self.peers = PeerDB.getInstance()
        
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
#        if not self.peers.has_key(permid):
#            peer = {'permid':permid}
#            self.peers.updateItem(peer)
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
        
        
class FriendDBHandler:

    def __init__(self):
        self.friends = FriendDB.getInstance()
        
    def __del__(self):
        self.sync()
    
    def sync(self):
        self.friends.sync()
    
    def printList(self):
        records = self.friends.values()
        print "========== all records in friends table ==========", len(records)
        for record in records:
            print record
            
    def size(self):
        return self.friends.size()            
            
    def getFriends(self):
        return 
            
    def getAllFriendsID(self):
        pass

    def hasFriendID(self, permid):
        pass

    def addFriendID(self, permid):
        pass

    def removeFriendID(self, permid):
        pass

    def addFriend(self, friend_permid, layer=1, owner=None, detail=None):
        pass
                        
    def removeFriend(self, friend_permid):
        pass    
        
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
        self.peers = PeerDB.getInstance()
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