# Written by Jie Yang
# see LICENSE.txt for license information

from cachedb import *
from time import time
from copy import deepcopy


class BasicDBHandler:
    def __init__(self):
        self.dbs = []    # don't include read only database
        
    def __del__(self):
        self.sync()
        
    def size(self):
        return self.dbs[0]._size()

    def sync(self):
        for db in self.dbs:
            db._sync()
            
    def clear(self):
        for db in self.dbs:
            db._clear()

    def printList(self):
        records = self.dbs[0]._items()
        for key, value in records:
            print key, value 

            
            
class MyDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.my_db = MyDB.getInstance(db_dir = db_dir)
        self.peer_db = PeerDB.getInstance(db_dir = db_dir)
        self.dbs = [self.my_db, self.peer_db]
        
    def get(self, key, value=''):
        return self.my_db._get(key, value)

    def put(self, key, value):
        self.my_db._put(key, value)
    
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
        
    def size(self):
        return len(self.my_db.getSuperPeers())
    
    def printList(self):
        print self.my_db.getSuperPeers()
        
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
        
    def size(self):
        return len(self.my_db.getFriends())

    def printList(self):
        print self.my_db.getFriends()
        
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
            
    def deleteFriend(self,permid):
        print "*********** sync friend db before", len(self.my_db.getFriends()), self.my_db.getFriends()
        self.my_db.deleteFriend(permid)
        self.my_db._sync()  
        print "*********** sync friend db after", len(self.my_db.getFriends()), self.my_db.getFriends()

class PeerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.peer_db]
        
    def __len__(self):
        return self.peer_db._size()
        
    def getPeer(self, permid):
        return self.peer_db.getItem(permid)
        
    def getPeerList(self):    # get the list of all peers' permid
        return self.peer_db._keys()
        
    def getTasteBuddyList(self):
        return self.pref_db._keys()

    def getRandomPeerList(self):
        peers = self.peer_db._keys()
        rand_peers = []
        for i in xrange(len(peers)):
            if not self.pref_db._has_key(peers[i]):
                rand_peers.append(peers[i])
        return rand_peers
        
    def getPeers(self, peer_list, keys):    # get peers given peer_list
        peers = []
        if 'permid' in keys:
            permid = True
            keys.remove('permid')
        else:
            permid = False
        for peer in peer_list:
            p = self.peer_db.getItem(peer)
            if permid:
                d = {'permid':peer}
            else:
                d = {}
            for key in keys:
                if key in p:
                    d.update({key:p[key]})
            peers.append(d)
        
        return peers
        
    def getPeersValue(self, peer_list, keys):
        values = []
        if not keys:
            return []
        for peer in peer_list:
            p = self.peer_db.getItem(peer)
            d = []
            if len(keys) == 1:
                if keys[0] in p:
                    d = p[keys[0]]
            else:
                for key in keys:
                    if key in p:
                        d.append(p[key])
            if d != []:
                values.append(d)
        
        return values
    
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
    
    def updatePeer(self, permid, key, value):
        self.peer_db.updateItem(permid, {key:value})
    
    def updatePeerIPPort(self, permid, ip, port):
        self.peer_db.updateItem(permid, {'ip':ip, 'port':port})
        
    def getItems(self):
        return self.peer_db._items()
        
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


class PreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.pref_db, self.owner_db]
        
    def getPreferences(self, permid):
        return self.pref_db.getItem(permid)
        
    def getPrefList(self, permid):
        return self.pref_db._get(permid,[]).keys()
    
    def addPreference(self, permid, torrent_hash, data={}):
        self.pref_db.addPreference(permid, torrent_hash, data)
        self.owner_db.addOwner(torrent_hash, permid)

    def deletePreference(self, permid, torrent_hash):
        self.torrent_db.deletePreference(permid, torrent_hash)
        self.owner_db.deleteOwner(torrent_hash, permid)
        
    def hasPreference(self, permid):
        return self.pref_db._has_key(permid)
        
class TorrentDBHandler(BasicDBHandler):

    def __init__(self, db_dir=''):
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.dbs = [self.torrent_db]
        
    def size(self):
        return self.torrent_db.size()

    def addTorrent(self, infohash, torrent={}):
        self.torrent_db.updateItem(infohash, torrent)
        
    def getTorrent(self, torrent_hash):
        return self.torrent_db.getItem(torrent_hash)
            
#    def findTorrent(self, torrent_hash=None, torrent_id=None):    # find both id and hash
#        pass
#
#    def updateTorrentRank(self, torrent_hash, rank):
#        pass
#            
#    def updateTorrent(self, torrent_hash, torrent):
#        pass
#        
#    def removeTorrent(self, torrent_hash):
#        pass
    

class MyPreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.dbs = [self.mypref_db]
    
    def getPreferences(self, key=None):
        all_items = self.mypref_db._items()
        if key is None:
            ret = []
            for item in all_items:
                item[1].update({'infohash':item[0]})
                ret.append(item[1])
            return ret
        else:
            return [all_items[i][1][key] for i in xrange(len(all_items))]
        
    def removeFakeTorrents(self, items):
        fakes = []
        for i in xrange(len(items)):
            torrent = items[i][0]
            if self.torrent_db.getRank(torrent) < 0:
                fakes.append(i)
        for i in fakes:
            items.pop(i)
        
    def getRecentPrefList(self, num=0):    # num = 0: all files
        all_items = self.mypref_db._items()
        self.removeFakeTorrents(all_items)
        prefs = [(item[1]['last_seen'], item[0]) for item in all_items]
        prefs.sort()
        prefs.reverse()
        if num > 0:
            return [item[1] for item in prefs[:num]]
        else:
            return [item[1] for item in prefs]
    
    def getRecentPrefs(self, num=10):
        all_items = self.getPreferences()
        prefs = [(item['last_seen'], item) for item in all_items]
        prefs.sort()
        prefs.reverse()
        return [item[1] for item in prefs[:num]]
    
    def addPreference(self, torrent_hash, data={}):
        self.mypref_db.updateItem(torrent_hash, data)

    def deletePreference(self, torrent_hash):
        self.mypref_db.deleteItem(torrent_hash)
        

class OwnerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.owner_db, self.torrent_db, self.peer_db, self.mypref_db]
        
    def getOwners(self, torrent_hash):
        return self.owner_db.getItem(torrent_hash)
        
def test_mydb():
    mydb = MyDBHandler()
    
def test_all():
    test_mydb()
    
if __name__ == '__main__':
    test_all()