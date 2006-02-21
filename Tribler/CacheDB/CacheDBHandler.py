# Written by Jie Yang
# see LICENSE.txt for license information

from cachedb import *
from copy import deepcopy
from sets import Set

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
        
    def addFriend(self, permid):
        self.my_db.addFriend(permid)
        self.my_db._sync()
        
    def addExternalFriend(self, friend):
        if not isinstance(friend, dict) or 'permid' not in friend:
            return
        permid = friend.pop('permid')
        self.peer_db.updateItem(permid, friend)
        self.peer_db._sync()
        self.my_db.addFriend(permid)
        self.my_db._sync()
            
    def getFriendList(self):
        return self.my_db.getFriends()
            
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
        self.my_db.deleteFriend(permid)
        self.my_db._sync()  
        
class PeerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.peer_db]
        
    def __len__(self):
        return self.peer_db._size()
        
    def getPeer(self, permid, default=False):
        return self.peer_db.getItem(permid, default)
        
    def getPeerSim(self, permid):
        x = self.peer_db.getItem(permid)
        if not x:
            return 0
        return x.get('similarity', 0)
        
    def getPeerList(self):    # get the list of all peers' permid
        return self.peer_db._keys()
        
    def getTasteBuddyList(self):
        return self.pref_db._keys()

    def getRandomPeerList(self):
        # TODO: improve performance 
        return list(Set(self.peer_db._keys()) - Set(self.pref_db._keys()))
        
    def getPeers(self, peer_list, keys):    # get a list of dictionaries given peer list
        peers = []
        if 'permid' in keys:
            permid = True
            keys.remove('permid')
        else:
            permid = False
        for peer in peer_list:
            p = self.peer_db.getItem(peer, default=True)
            if permid:
                d = {'permid':peer}
            else:
                d = {}
            for key in keys:
                d[key] = p[key]
            peers.append(d)
        
        return peers
        
    def getPeersValue(self, peer_list, keys=None):    # get a list of values given peer list 
        if not keys:
            keys = self.peer_db.default_item.keys()
        values = []
        for peer in peer_list:
            p = self.peer_db.getItem(peer, default=True)
            if len(keys) == 1:
                values.append(p[keys[0]])
            else:
                d = []
                for key in keys:
                    d.append(p[key])
                values.append(d)
        
        return values
    
    def addPeer(self, permid, value, update_dns=True):
        self.peer_db.updateItem(permid, value, update_dns)
        
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
        
    def deletePeer(self, permid):
        self.peer_db._delete(permid)        


class PreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.pref_db, self.owner_db]
        
    def getPreferences(self, permid):
        return self.pref_db.getItem(permid)
        
    def getPrefList(self, permid):
        return self.pref_db._get(permid,{}).keys()
    
    def addPreference(self, permid, infohash, data={}):
        self.pref_db.addPreference(permid, infohash, data)
        self.owner_db.addOwner(infohash, permid)

    def deletePreference(self, permid, infohash):
        self.torrent_db.deletePreference(permid, infohash)
        self.owner_db.deleteOwner(infohash, permid)
        
    def hasPreference(self, permid):
        return self.pref_db._has_key(permid)
        
    def getNumPrefs(self, permid):
        if not self.pref_db._has_key(permid):
            return 0
        x = self.pref_db.getItem(permid)
        return len(x)
        
class TorrentDBHandler(BasicDBHandler):

    def __init__(self, db_dir=''):
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.torrent_db]
        
    def addTorrent(self, infohash, torrent={}):
        self.torrent_db.updateItem(infohash, torrent)
        
    def getTorrent(self, infohash):
        return self.torrent_db.getItem(infohash)
        
    def getTorrents(self, torrent_list, keys=None):    # get a list of dictionaries given torrent list
        if not keys:
            keys = self.torrent_db.default_item.keys()
            keys += ['infohash']
        torrents = []
        if 'infohash' in keys:
            infohash = True
            keys.remove('infohash')
        else:
            infohash = False
        for torrent in torrent_list:
            p = self.torrent_db.getItem(torrent, default=True)
            if infohash:
                d = {'infohash':torrent}
            else:
                d = {}
            for key in keys:
                d[key] = p[key]
            torrents.append(d)
        
        return torrents
        
    def hasTorrent(self, infohash):
        return self.torrent_db._has_key(infohash)
            
#    def getTorrentList(self):    # get the list of all peers' permid
#        return self.torrent_db._keys()
#        
#    def getMyTorrentList(self):
#        return self.mypref_db._keys()
        
    def getOthersTorrentList(self, num=-1):    # get the list of torrents which are not in my preference
        all_list = list(Set(self.torrent_db._keys()) - Set(self.mypref_db._keys()))
        if num < 0:
            return all_list
        values = []
        for torrent in all_list:
            t = self.torrent_db.getItem(torrent, default=True)
            values.append(t['relevance'])
        nlist = len(all_list)
        aux = [(values[i], i) for i in xrange(nlist)]
        aux.sort()
        aux.reverse()
        return [all_list[i] for k, i in aux[:num]]
            
    def getTorrentsValue(self, torrent_list, keys=None):    # get a list of values given peer list 
        if not keys:
            keys = self.torrent_db.default_item.keys()
        if not isinstance(keys, list):
            keys = [str(keys)]
        values = []
        for torrent in torrent_list:
            t = self.torrent_db.getItem(torrent, default=True)
            if len(keys) == 1:
                values.append(t[keys[0]])
            else:
                d = []
                for key in keys:
                    d.append(t[key])
                values.append(d)
        
        return values
        
    def getNoMetaTorrents(self):    # get the list of torrents which only have an infohash without the metadata
        def noMetaData(infohash):
            value = self.torrent_db._get(infohash)
            name = value.get('torrent_name', None)
            return not name
        
        all_list = self.getOthersTorrentList()
        return filter(noMetaData, all_list)
        
    def hasMetaData(self, infohash):
        value = self.torrent_db._get(infohash)
        name = value.get('torrent_name', None)
        return name
            
    def getOwners(self, infohash):
        return self.owner_db.getItem(infohash)
        
    def updateTorrentRelevance(self, torrent, relevance):
        self.torrent_db.updateItem(torrent, {'relevance':relevance})
            
    def deleteTorrent(self, infohash):
        self.torrent_db._delete(infohash)
        

class MyPreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.dbs = [self.mypref_db, self.torrent_db]
    
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
            
    def getPrefList(self):
        return self.mypref_db._keys()
        
    def getPrefs(self, pref_list, keys):    # get a list of dictionaries given peer list
        peers = []
        for torrent in pref_list:
            d = self.mypref_db.getItem(torrent, default=True)
            t = self.torrent_db.getItem(torrent, default=True)
            try:
                d.update(t)
            except:
                continue
            if 'infohash' in keys:
                d.update({'infohash':torrent})
            for key in d.keys():
                if key not in keys:
                    d.pop(key)
            peers.append(d)
        
        return peers
        
    def removeFakeTorrents(self, items):
        valid_torrents = []
        for i in xrange(len(items)):
            torrent = items[i][0]
            if self.mypref_db.getRank(torrent) >= 0:
                valid_torrents.append(items[i])
        return valid_torrents
            
    def getRecentPrefList(self, num=0):    # num = 0: all files
        all_items = self.mypref_db._items()
        valid_items = self.removeFakeTorrents(all_items)
        prefs = [(item[1]['last_seen'], item[0]) for item in valid_items]
        prefs.sort()
        prefs.reverse()
        if num > 0:
            return [item[1] for item in prefs[:num]]
        else:
            return [item[1] for item in prefs]

    def hasPreference(self, infohash):
        return self.mypref_db._has_key(infohash)
            
    def addPreference(self, infohash, data={}):
        if not data and self.hasPreference(infohash):
            return
        self.mypref_db.updateItem(infohash, data)

    def deletePreference(self, infohash):
        self.mypref_db.deleteItem(infohash)
        
    def updateRank(self, infohash, rank):
        self.mypref_db.updateItem(infohash, {'rank':rank})
        self.sync()

class OwnerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.owner_db]
        
def test_mydb():
    mydb = MyDBHandler()
    
def test_all():
    test_mydb()
    
if __name__ == '__main__':
    test_all()