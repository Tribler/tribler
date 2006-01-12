"""
Database design
Don't use None as a default value

MyDB - (PeerDB)
  mydata.bsd:    # future keys: pictures, 
    version: int (curr_version)    # required
    permid: str                    # required
    ip: str ('')
    port: int (0)
    name: str ('Chitraka')
    torrent_path: str ('')    # default path to store torrents
    superpeers: list ([])     # permid
    prefxchg_queue: list ([]) # permid
    bootstrapping: int (1)
    

PeerDB - (FriendDB, PreferenceDB, OwnerDB)   
  peers.bsd:    # future keys: sys_trust, reliablity, speed, personal_info, ..
    peer_id:{       # peer_id = sha(permid).digest(), 20Bytes
        permid: str    # required
        has_preference: int (0),    #? 0 - doesn't have preference, 1 - have preference
        ip: str ('')
        port: int (0)
        name: str ('unknown')
        last_seen: int (0)
        trust: int (50)    # [0, 100]
        similarity: int (0)    # [0, 1000]
        }

TorrentDB - (PreferenceDB, MyPreference, OwnerDB)
  torrents.bsd:    # future keys: names, tags, trackers, ..
    torrent_id:{    # we just use torrent_hash as the torrent_id in this version
        torrent_hash: str(''),    # to keep consistent with PeerDB
        have: int (0)   # 0: have nothing; 
                          1: have this torrent info, but do not have the .torrent file; 
                          2: have this .torrent file, but have not downloaded the files
                          3: have the files
        relevance: int (0)    # [0, 1000]
            # if have > 0, have the following keys
        name: str ('')    # torrent name
        info: dict ({})   # {name, length, announce, creation date, comment}
        rank: int (0)  # 0 ~ 5, as a feedback to recommendation system
            # if have > 1, have the following keys
        path: str ('')    # path of the torrent (without the file name). '\x01' for default path
            # if have > 2, look up mypreferences.bsd for more info
        }

PrefernceDB - (PeerDB, TorrentDB)
  preferences.bsd:
    peer_id:{
        torrent_id:{'relevance': int (0), 'rank': int (0)}    # re: [0, 1000], rank: [-1, 5]
    }

MyPrefrenceDB - (TorrentDB)
  mypreferences.bsd:    # future keys: speed
    torrent_id:{
        torrent_hash: str ('')
        created_time: int (0)
        content_length: int (0) # downloaded file size, may be different with info['length']
        content_name: str ('')  # real file name in disk, may be different with info['name']
        content_dir: str ('')   # content_dir + content_name = full path
        rank: int(0)  # -1 ~ 5, as a recommendation degree to others
        last_seen: int (0)
        }
        
FriendDB - (PeerDB)
  friends.bsd: 
    peer_id: {
        peer_id: dict ({})    # {peer_id:{'trust'}}, only primary friends, future keys: sys_trust
        }

OwnerDB - (PeerDB, TorrentDB)
  owner.bsd:
    torrent_hash: [peer_id]: list ([])    # future keys: tags, name

"""

import os
from time import time, ctime
from random import random
from sha import sha
from copy import deepcopy

try:
    # For Python 2.3
    from bsddb import db, dbshelve
except ImportError:
    # For earlier Pythons w/distutils pybsddb
    from bsddb3 import db, dbshelve

def setDBPath(db_dir = ''):
    if not db_dir:
        db_dir = '.'
    if not os.access(db_dir, os.F_OK):
        try: 
            os.mkdir(db_dir)
        except os.error, msg:
            print msg
            db_dir = '.'
    return db_dir

home_dir = 'bsddb'
curr_version = 1
permid_length = 112
peer_id_length = 20
torrent_hash_length = 20
torrent_id_length = 20
STRICT_CHECK = False
    
def init(myinfo):
    MyDB.getInstance(myinfo)
    
def open_db(filename, db_dir='', filetype=db.DB_BTREE):
    if not db_dir:
        db_dir = home_dir
    dir = setDBPath(db_dir)
    path = os.path.join(dir, filename)
    try:
        d = dbshelve.open(path, filetype=filetype)
    except Exception, msg:
        print "cannot open dbshelve on", path, msg
        d = dbshelve.open(filename, filetype=filetype)
    return d

#def get_peer_id(permid):
#    return sha(permid).digest()    # Real engineers keep it simple :)

def get_peer_id(id):
    return id

def get_torrent_id(torrent_hash):
    return torrent_hash
    
# Abstract base calss    
class BasicDB:    # Should we use delegation instead of inheritance?
        
    def __init__(self):
        if self.__class__ == BasicDB:
            raise NotImplementedError, "Cannot create object of class BasicDB"
    
#------------ Basic operations, used by basic interfaces ----------------------#
    def __del__(self):
        self._data.sync()

    def _get(self, key, value=None):    # read
        return self._data.get(key, value)
        
    def _update(self, data):    # write
        try:
            self._data.update(data)
            self._sync()    # how often to do sync?
        except:
            pass
            
    def _updateItem(self, key, data):
        try:
            _key = self.getID(key)
            x = self._data[_key]
            x.update(data)
            self._data.put(_key, x)
            self._sync()
        except:
            pass

    def _put(self, key, value):    # write
        try:
            self._data.put(key, value)
            self._sync()
        except:
            pass
        
    def _pop(self, key):     # remove
        value = None
        try:
            value = self._data.pop(key)
            self._sync()
        except:
            pass
        return value

    def _delete(self, key):
        try:
            self._data.delete(key)
            self.sync()
        except:
            pass

    def _has_key(self, key):    # find a key
        return self._data.has_key(key)
    
    def _sync(self):
        #self._data.sync()
        pass
    
#------------ Basic interfaces, used by member func and handlers -------------#
    def sync(self):            # write data from mem to disk
        self._data.sync()
            
    def update(self, data):      # may be modified by subclass
        self._update(data)

    def put(self, key, value):
        id = self.getID(key)
        self._put(id, value)
        
    def get(self, key, value=None): 
        id = self.getID(key)
        return self._get(id, value)
    
    def pop(self, key): 
        id = self.getID(key)
        return self._pop(id)
    
    def delete(self, key):
        id = self.getID(key)
        self._delete(id)
        
    def has_key(self, key):    # for tradition
        id = self.getID(key)
        return self._has_key(id)
    
    def items(self):
        return self._data.items()
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()
    
    def size(self):
        return len(self._data)

#------------ Utilities for subclasses --------------#
    def updateDB(self, old_version):    # update database format from an old version
        pass
        
    def setDefault(self, data):    # it is only used by validData()
        for key,value in self.default_data.items():
            if not data.has_key(key):
                data[key] = value

    def validDict(self, data, keylen=0):    # basic requirement for a data item in DB
        if not isinstance(data, dict):
            return False
        for key in data:
            if not isinstance(key, str):
                return False
            if STRICT_CHECK and keylen and len(key) != keylen:
                return False
        return True        
        
    def validList(self, data, keylen=0):
        if not isinstance(data, list):
            return False
        for key in data:
            if not isinstance(key, str):
                return False
            if STRICT_CHECK and keylen and len(key) != keylen:
                return False
        return True        

    def getID(self, key):    # find the local id given the key. 
        raise NotImplementedError, "Cannot call abstrct method - getID"
    
    def validData(self, data):    # to be implemented by subclass, only used when writing data
        raise NotImplementedError, "Cannot call abstrct method - validData"
        
    def validItem(self, item):
        raise NotImplementedError, "Cannot call abstrct method - validItem"


class MyDB(BasicDB):
    
    __single = None

    def __init__(self, myinfo=None, db_dir=''):
        if MyDB.__single:
            raise RuntimeError, "MyDB is singleton"
        self.db_name = 'mydata.bsd'
        self._data = open_db(self.db_name, db_dir, filetype=db.DB_HASH)    # dbshelve object
        MyDB.__single = self 
        self.default_data = {
            'version':curr_version, 
            'permid':'', 
            'ip':'127.0.0.1', 
            'port':0, 
            'name':'Chitraka', 
            'torrent_path':'',
            'bootstrapping':1, 
            'max_num_torrents': 100000,
            'max_num_my_preferences': 1000,
            'superpeers':[],    #permid list
            'prefxchg_queue':[],
        }
        self.preload_keys = ['ip', 'torrent_path', 'permid']    # these keys can be changed at each bootstrap
        self.initData(myinfo)
            
    def getInstance(*args, **kw):
        if MyDB.__single is None:
            MyDB(*args, **kw)
        return MyDB.__single
    getInstance = staticmethod(getInstance)

    def setDefault(self, data):    # it is only used by validData()
        for key,value in self.default_data.items():
            if self.has_key(key) and self.get(key):
                continue
            if not data.has_key(key) or not data[key]:
                data[key] = value
                
    def getID(self, key):
        return key

    def validData(self, data):    # to be implemented by subclass, only used by update
        return self.validDict(data)

    def initData(self, myinfo=None):
        MyDB.checkVersion(self)
        if not myinfo:
            myinfo = {}
        self.setDefault(myinfo)
        self.load(myinfo)
        
    def load(self, myinfo):
        for key in myinfo:
            if not self.has_key(key) or key in self.preload_keys:
                self.put(key, myinfo[key])
        
    def checkVersion(db):
        if not MyDB.__single:
            MyDB()        # it should never be entered
        old_version = MyDB.__single.get('version')
        if not old_version:
            MyDB.__single.put('version', curr_version)
        elif old_version < curr_version:
            db.updateDB(old_version)
        elif old_version > curr_version:
            raise RuntimeError, "The version of database is too high. Please update the software."
    checkVersion = staticmethod(checkVersion)
    

class PeerDB(BasicDB):
    """ List of Peers, e.g. Host Cache """
    
    __single = None
    
    def __init__(self):
        if PeerDB.__single:
            raise RuntimeError, "PeerDB is singleton"
        self.db_name = 'peers.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        MyDB.checkVersion(self)
        PeerDB.__single = self
        self.default_data = {
            'permid':'',
            'has_preference':0,
            'ip':'',
            'port':0,
            'name':'unknown',
            'last_seen':0,
            'trust':50,
            'similarity':0,
        }

    def getInstance(*args, **kw):
        if PeerDB.__single is None:
            PeerDB(*args, **kw)
        return PeerDB.__single
    getInstance = staticmethod(getInstance)

    def getID(self, permid):
        return get_peer_id(permid)   # Return local id of a peer
        
    def validData(self, data):    # data = {peer_id:item}
        if not self.validDict(data, peer_id_length):
            return False
        for item in data.values():
            if not self.validItem(item):
                return False
    
    def validItem(self, item):    # an item presents a peer
        if not self.validDict(item):
            return False
        if not item.has_key('permid') or not isinstance(item['permid'], str):
            return False
        if STRICT_CHECK and len(item['permid']) != permid_length:            
            return False
        if not self.has_key(item['permid']):
            self.setDefault(item)
        return True    

    def updateItem(self, item):    # insert a peer; update it if existed
        if self.validItem(item):
            permid = item['permid']
            if self.has_key(permid):
                self._updateItem(permid, item)
            else:
                self.put(permid, item)
                
    def deleteItem(self, item):
        permid = item['permid']
        self.delete(permid)
        

class TorrentDB(BasicDB):
    """ Database of all torrent files, including the torrents I don't have yet """
    
    __single = None
        
    def __init__(self):
        if TorrentDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'torrents.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        MyDB.checkVersion(self)
        TorrentDB.__single = self 
        self.default_data = {
            'torrent_hash':'',
            'have': 0,
            'recommendation': 0,
            'relevance':0,
            'name': '',
            'length': 0,
            #'info': {},   # {name, length, announce, creation date, comment}
            'rank': 0,  # 0 ~ 5, as a feedback to recommendation system
            'path': '', # path+name=full path. Default path if the value is '\x01'
        }                
        
    def getInstance(*args, **kw):
        if TorrentDB.__single is None:
            TorrentDB(*args, **kw)
        return TorrentDB.__single
    getInstance = staticmethod(getInstance)

    def getID(self, torrent_hash):    # Return local id of a torrent
        return get_torrent_id(torrent_hash)
        
    def validData(self, data):    # data = {torrent_id:item}
        if not self.validDict(data, torrent_id_length):
            return False
        for item in data.values():
            if not self.validItem(item):
                return False
    
    def validItem(self, item):    # an item presents a torrent
        if not self.validDict(item):
            return False
        if not item.has_key('torrent_hash') or not isinstance(item['torrent_hash'], str):
            return False
        if STRICT_CHECK and len(item['torrent_hash']) != torrent_hash_length:
            return False
        if not self.has_key(item['torrent_hash']):
            self.setDefault(item)
        return True    

    def updateItem(self, item):    # insert a preference; update it if existed
        if self.validItem(item):
            key = item['torrent_hash']
            if self.has_key(key):
                self._updateItem(key, item)
            else:
                self.put(key, item)

    def deleteItem(self, item):
        torrent_hash = item['torrent_hash']
        self.delete(torrent_hash)
        
    
class PreferenceDB(BasicDB):
    """ Peer * Torrent """
    
    __single = None
    
    def __init__(self):
        if PreferenceDB.__single:
            raise RuntimeError, "PreferenceDB is singleton"
        self.db_name = 'preferences.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        self.default_data = {'relevance': 0, 'rank': 0}
        PreferenceDB.__single = self 
                
    def getInstance(*args, **kw):
        if PreferenceDB.__single is None:
            PreferenceDB(*args, **kw)
        return PreferenceDB.__single
    getInstance = staticmethod(getInstance)

    def getID(self, permid):
        return get_peer_id(permid)   # Return local id of a peer
   
    def validData(self, data):    # data = {peer_id:item, peer_id2:item2}
        if not self.validDict(data, peer_id_length):
            return False
        for item in data.values():
            if not self.validItem(item):
                return False
        return True
    
    def validItem(self, item):    # item = [permid1, permid2]
        if not self.validDict(item, torrent_id_length):
            return False
        for subitem in item.values():
            if not self.validDict(subitem):
                return False
            self.setDefault(subitem)  
        return True


    def addPreference(self, permid, torrent_hash, data={}):    # add or update pref
        torrent_id = get_torrent_id(torrent_hash)
        item = {torrent_id:data}
        self.validItem(item)
        if not self.has_key(permid):
            self.put(permid, item)
        else:
            preferences = self.get(permid)
            if torrent_id not in preferences or data:
                preferences.update(item)
                self.put(permid, preferences)
            
    def deletePreference(self, permid, torrent_hash):
        torrent_id = get_torrent_id(torrent_hash)
        if self.has_key(permid):
            preferences = self.get(permid)
            if torrent_id in preferences:
                preferences.pop(torrent_id)
                self.put(permid, preferences)
                
    def deleteItem(self, permid):
        self.delete(permid)
            
            
class MyPreferenceDB(BasicDB): 
    
    __single = None
        
    def __init__(self):
        if MyPreferenceDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'mypreferences.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        MyDB.checkVersion(self)
        MyPreferenceDB.__single = self 
        self.default_data = {
            'torrent_hash':'',    # use redundancy to keep program simple
            'created_time':0,
            'content_length':0, # downloaded file size, may be different with info['length']
            'content_name':'',  # real file name in disk, may be different with info['name']
            'content_dir':'',   # content_dir + content_name = full path
            'rank':0,  # -1 ~ 5, as a recommendation degree to others
            'last_seen':0,
        }
                
    def getInstance(*args, **kw):
        if MyPreferenceDB.__single is None:
            MyPreferenceDB(*args, **kw)
        return MyPreferenceDB.__single
    getInstance = staticmethod(getInstance)

    def getID(self, torrent_hash):    # Return local id of a torrent
        return get_torrent_id(torrent_hash)
        
    def validData(self, data):    # data = {torrent_id:item}
        if not self.validDict(data, torrent_id_length):
            return False
        for key,value in data.items():
            if not self.validItem(key, value):
                return False
        return True
    
    def validItem(self, key, item):    # an item presents a preference (e.g., a preferred torrent)
        if not self.validDict(item):
            return False
        if not item.has_key('torrent_hash') and not item['torrent_hash']:
            return False
        if not self.has_key(key):
            self.setDefault(item)
        return True    
    
    def setDefault(self, data):
        for key,value in self.default_data.items():
            if not data.has_key(key):
                if key == 'created_time' or key == 'last_seen':
                    data[key] = int(time())
                else:
                    data[key] = value
                    
    def updateItem(self, key, item):    # insert a preference; update it if existed
        if self.validItem(key, item):
            if self.has_key(key):
                self._updateItem(key, item)
            else:
                self.put(key, item)
                
    def deleteItem(self, torrent_hash):
        self.delete(torrent_hash)
        

class FriendDB(BasicDB):
    """ Peer * Peer """
    
    __single = None
    
    def __init__(self):
        if FriendDB.__single:
            raise RuntimeError, "FriendDB is singleton"
        self.db_name = 'friends.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        MyDB.checkVersion(self)
        FriendDB.__single = self
        self.default_data = {'trust':5}
        
    def getInstance(*args, **kw):
        if FriendDB.__single is None:
            FriendDB(*args, **kw)
        return FriendDB.__single
    getInstance = staticmethod(getInstance)
 
    def getID(self, permid):
        return get_peer_id(permid)   # Return local id of a peer
           
    def validData(self, data):    # data = {peer_id:item, peer_id2:item2}
        if not self.validDict(data, peer_id_length):
            return False
        for key,value in data.items():
            if not self.validItem(key, value):
                return False
        return True
    
    def validItem(self, key, item):    # item = {friend_peer_id:{'trust':5}, friend_peer_id2:{'trust':5}}
        if not self.validDict(item, peer_id_length):
            return False
        for key,value in item.items():    # key=friend_peer_id, value = {'trust':5}
            if not self.validDict(value):
                return False
            if not self.has_key(key):
                self.setDefault(item)
        return True

    def updateItem(self, key, item):    # insert a peer's friends list, update it if existed
        if self.validItem(item):
            if self.has_key(key):
                self._updateItem(key, item)
            else:
                self.put(key, item)
                
    def deleteItem(self, permid):
        self.delete(permid)
            

class OwnerDB(BasicDB):
    """ Torrent * Peer """
    
    __single = None
    
    def __init__(self):
        if OwnerDB.__single:
            raise RuntimeError, "OwnerDB is singleton"
        self.db_name = 'owners.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        OwnerDB.__single = self 
                
    def getInstance(*args, **kw):
        if OwnerDB.__single is None:
            OwnerDB(*args, **kw)
        return OwnerDB.__single
    getInstance = staticmethod(getInstance)

    def validData(self, data):    # data = {torrent_id:item, torrent_id2:item2}
        if not self.validDict(data, torrent_id_length):
            return False
        for item in data.values():
            if not self.validItem(item):
                return False
        return True

    def getID(self, torrent_hash):    # Return local id of a torrent
        return get_torrent_id(torrent_hash)
            
    def validItem(self, item):    # item = [permid1, permid2]
        return self.validList(item, permid_length)

#    def updateItem(self, key, item):    # should use addOwner instead
#        if self.validItem(item):
#            if self.has_key(key):
#                self._updateItem(key, item)
#            else:
#                self.put(key, item)

    def addOwner(self, torrent_hash, permid):
        peer_id = get_peer_id(permid)
        if not self.has_key(torrent_hash):
            self.put(torrent_hash, [peer_id])
        else:
            owners = self.get(torrent_hash)
            if peer_id not in owners:
                owners.append(peer_id)
                self.put(torrent_hash, owners)
            
    def deleteOwner(self, torrent_hash, permid):
        peer_id = get_peer_id(permid)
        if self.has_key(torrent_hash):
            owners = self.get(torrent_hash)
            if peer_id in owners:
                owners.remove(peer_id)
                self.put(torrent_hash, owners)

    def deleteItem(self, torrent_hash):
        self.delete(torrent_hash)
                    