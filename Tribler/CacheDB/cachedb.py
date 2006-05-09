# Written by Jie Yang
# see LICENSE.txt for license information

"""
Database design
Value in bracket is the default value
Don't use None as a default value

MyDB - (PeerDB)
  mydata.bsd:    # future keys: pictures, 
    version: int (curr_version)    # required
    permid: str                    # required
    ip: str ('')
    port: int (0)
    name: str ('Tribler')
    torrent_path: str ('')    # default path to store torrents
    prefxchg_queue: list ([]) # permid
    bootstrapping: int (1)
    max_num_torrents: int (100000)
    max_num_my_preferences: int (1000)
    superpeers: Set([permid])
    friends: Set([permid])
            
PeerDB - (MyFriendDB, PreferenceDB, OwnerDB)   
  peers.bsd:    # future keys: sys_trust, reliablity, speed, personal_info, ..
    permid:{       
        ip: str ('')
        port: int (0)    # listening port, even behind firewall
        name: str ('unknown')
        last_seen: int (0)
        similarity: int (0)    # [0, 1000]
        connected_times: int(0)    # times to connect the peer successfully
        tried_times: int(0)        # times to attempt to connect the peer
        buddycast_times: int(0)    # times to receive buddycast message
        #relability (uptime, IP fixed/changing)
        #trust: int (0)    # [0, 100]
        #icon: str ('')    # name + '_' + permid[-4:]
    }

TorrentDB - (PreferenceDB, MyPreference, OwnerDB)
  torrents.bsd:    # future keys: names, tags, trackers, ..
    infohash:{
        relevance: int (0)    # [0, 1000]
        torrent_name: str ('')    # torrent name
        torrent_dir: str ('')    # path of the torrent (without the file name). '\x01' for default path
        info: dict ({})   # {name, length, announce, creation date, comment, announce-list, num_files}
        leecher: int (0)
        seeder: int (0)
    }

PreferenceDB - (PeerDB, TorrentDB)    # other peers' preferences
  preferences.bsd:
    permid:{
        torrent_id:{'relevance': int (0), 'rank': int (0)}    # re: [0, 1000], rank: [-1, 5]
    }

MyPreferenceDB - (TorrentDB)
  mypreferences.bsd:    # future keys: speed
    infohash:{
        created_time: int (0)   # time to start download/upload the torrent
        content_name: str ('')  # real file name in disk, may be different with info['name']
        content_dir: str ('')   # content_dir + content_name = full path
        rank: int (0)  # [-1, 5], # -1 means it is a fake torrent
        last_seen: int (0)
    }
        
OwnerDB - (PeerDB, TorrentDB)
  owner.bsd:
    infohash: Set([permid])    # future keys: tags, name

"""

import os, sys
from time import time, ctime
from random import random
from sha import sha
from copy import deepcopy
from sets import Set
from traceback import print_exc
from threading import currentThread

#from Tribler.utilities import isValidPermid, isValidInfohash

try:
    # For Python 2.3
    from bsddb import db, dbshelve, dbutils
except ImportError:
    # For earlier Pythons w/distutils pybsddb
    from bsddb3 import db, dbshelve, dbutils

from shelve import BsdDbShelf 

#permid_len = 0  #112
#infohash_len = 20
#

home_dir = 'bsddb'
curr_version = 1
permid_length = 112
infohash_length = 20
torrent_id_length = 20
MAX_RETRIES = 12
STRICT_CHECK = False
DEBUG = False
    
def isValidPermid(permid):    # validate permid in outer layer
    return True
    
def isValidInfohash(infohash):
    return True

def init(config_dir, myinfo):
    """ create all databases """
    
    global home_dir
    home_dir = make_filename(config_dir, 'bsddb')
    MyDB.getInstance(myinfo, home_dir)
    PeerDB.getInstance(home_dir)
    TorrentDB.getInstance(home_dir)
    PreferenceDB.getInstance(home_dir)
    MyPreferenceDB.getInstance(home_dir)
    OwnerDB.getInstance(home_dir)
    
def make_filename(config_dir,filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir,filename)    
    
def setDBPath(db_dir = ''):
    if not db_dir:
        db_dir = '.'
    if not os.access(db_dir, os.F_OK):
        try: 
            os.mkdir(db_dir)
        except os.error, msg:
            print >> sys.stderr, "cachedb: cannot set db path:", msg
            db_dir = '.'
    return db_dir

def open_db2(filename, db_dir='', filetype=db.DB_BTREE):    # backup
    global home_dir
    if not db_dir:
        db_dir = home_dir
    dir = setDBPath(db_dir)
    path = os.path.join(dir, filename)
    try:
        d = dbshelve.open(path, filetype=filetype)
    except Exception, msg:
        print >> sys.stderr, "cachedb: cannot open dbshelve on", path, msg
        d = dbshelve.open(filename, filetype=filetype)
    return d

def open_db(filename, db_dir='', filetype=db.DB_BTREE, writeback=False):
    global home_dir
    if not db_dir:
        db_dir = home_dir
    dir = setDBPath(db_dir)
    path = os.path.join(dir, filename)
    env = db.DBEnv()
    # Concurrent Data Store
    env.open(dir, db.DB_THREAD|db.DB_INIT_CDB|db.DB_INIT_MPOOL|db.DB_CREATE)
    #d = db.DB(env)
    #d.open(path, filetype, db.DB_THREAD|db.DB_CREATE)
    #_db = BsdDbShelf(d, writeback=writeback) 
    _db = dbshelve.open(filename, flags=db.DB_THREAD|db.DB_CREATE, 
            filetype=filetype, dbenv=env)
    return _db

def validDict(data, keylen=0):    # basic requirement for a data item in DB
    if not isinstance(data, dict):
        return False
    for key in data:
        if not isinstance(key, str):
            return False
        if STRICT_CHECK and keylen and len(key) != keylen:
            return False
    return True        
    
def validList(data, keylen=0):
    if not isinstance(data, list):
        return False
    for key in data:
        if not isinstance(key, str):
            return False
        if STRICT_CHECK and keylen and len(key) != keylen:
            return False
    return True        

# Abstract base calss    
class BasicDB:    # Should we use delegation instead of inheritance?
        
    def __init__(self, db_dir=''):
        self.default_item = {'d':1, 'e':'abc', 'f':{'k':'v'}, 'g':[1,'2']} # for test
        if self.__class__ == BasicDB:
            self.db_name = 'basic.bsd'    # for testing
            self._data = open_db(self.db_name, db_dir, filetype=db.DB_HASH)
            #raise NotImplementedError, "Cannot create object of class BasicDB"
    
#------------ Basic interfaces, used by member func and handlers -------------#
    def __del__(self):
        self.close()
        
    threadnames = {}
    
    def _put(self, key, value):    # write
        try:
            if DEBUG:
                name = currentThread().getName()
                if name not in self.threadnames:
                    self.threadnames[name] = 0
                self.threadnames[name] += 1
                print "****bsddb: put", len(self.threadnames), name, \
                    self.threadnames[name], time(), self.__class__.__name__
                    
            dbutils.DeadlockWrap(self._data.put, key, value, max_retries=MAX_RETRIES)
            #self._data.put(key, value)
        except:
            pass
        
    def _has_key(self, key):    # find a key
        try:
            return dbutils.DeadlockWrap(self._data.has_key, key, max_retries=MAX_RETRIES)
            #return self._data.has_key(key)
        except:
            return False
    
    def _get(self, key, value=None):    # read
        try:
            return dbutils.DeadlockWrap(self._data.get, key, value, max_retries=MAX_RETRIES)
            #return self._data.get(key, value)
        except:
            print_exc()
            return None
        
    def _updateItem(self, key, data):
        try:
            x = self._get(key)
            if isinstance(x, dict):
                x.update(data)
            else:
                x = data
            self._put(key, x)
        except:
            print_exc()
    
    def _delete(self, key):
        try:
            if DEBUG:
                name = currentThread().getName()
                if name not in self.threadnames:
                    self.threadnames[name] = 0
                self.threadnames[name] += 1
                print "****bsddb: del", len(self.threadnames), name, \
                    self.threadnames[name], time(), self.__class__.__name__
                
            dbutils.DeadlockWrap(self._data.delete, key, max_retries=MAX_RETRIES)
            #self._data.delete(key)
        except:
            pass

    def _sync(self):            # write data from mem to disk
        dbutils.DeadlockWrap(self._data.sync, max_retries=MAX_RETRIES)
        #self._data.sync()
            
    def _clear(self):
        dbutils.DeadlockWrap(self._data.clear, max_retries=MAX_RETRIES)
        #self._data.clear()
    
    def _keys(self):
        return dbutils.DeadlockWrap(self._data.keys, max_retries=MAX_RETRIES)
        #return self._data.keys()
    
    def _values(self):
        return dbutils.DeadlockWrap(self._data.values, max_retries=MAX_RETRIES)
        #return self._data.values()
    
    def _items(self):
        return dbutils.DeadlockWrap(self._data.items, max_retries=MAX_RETRIES)
        #return self._data.items()
    
    def _size(self):
        try:
            return dbutils.DeadlockWrap(len, self._data, max_retries=MAX_RETRIES)
            #return len(self._data)
        except:
            print_exc()
            print >> sys.stderr, "cachedb: cachedb.BasicDB._size error", self.__class__.__name__
            return 0
    
    def close(self):
        try:
            self._sync()
            dbutils.DeadlockWrap(self._data.close, max_retries=MAX_RETRIES)
            #self._data.close()
        except:
            print_exc()
        
    def updateDB(self, old_version):
        raise NotImplementedError

    def setDefaultItem(self, item):
        df = deepcopy(self.default_item)
        df.update(item)
        return df
    
    
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
            'ip':'', 
            'port':0, 
            'name':'Tribler', 
            'torrent_path':'',
            'prefxchg_queue':[],
            'bootstrapping':1, 
            'max_num_torrents':100000,
            'max_num_my_preferences':1000,
            'superpeers':Set(),
            'friends':Set(),
        }
        self.preload_keys = ['ip', 'torrent_path', 'permid']    # these keys can be changed at each bootstrap
        self.initData(myinfo)
            
    def getInstance(*args, **kw):
        if MyDB.__single is None:
            MyDB(*args, **kw)
        if MyDB.__single._size() < len(MyDB.__single.default_data):
            MyDB.__single.initData()
        return MyDB.__single
    getInstance = staticmethod(getInstance)

    def setDefault(self, data):    # it is only used by validData()
        dd = deepcopy(self.default_data)
        dd.update(data)
        return dd

    def initData(self, myinfo=None):
        MyDB.checkVersion(self)
        if not myinfo:
            myinfo = {}
        myinfo = self.setDefault(myinfo)
        self.load(myinfo)
        
    def load(self, myinfo):
        for key in myinfo:
            if not self._has_key(key) or key in self.preload_keys:    # right?
                self._put(key, myinfo[key])
        
    def checkVersion(db):
        if not MyDB.__single:
            MyDB()        # it should never be entered
        old_version = MyDB.__single._get('version')
        if not old_version:
            MyDB.__single._put('version', curr_version)
        elif old_version < curr_version:
            db.updateDB(old_version)
        elif old_version > curr_version:
            raise RuntimeError, "The version of database is too high. Please update the software."
    checkVersion = staticmethod(checkVersion)
    
    # superpeers
    def addSuperPeer(self, permid):
        if isValidPermid(permid):
            sp = self._get('superpeers')
            sp.add(permid)
            self._put('superpeers', sp)
            
    def deleteSuperPeer(self, permid):
        if isValidPermid(permid):
            try:
                sp = self._get('superpeers')
                sp.remove(permid)
                self._put('superpeers', sp)
            except:
                pass
            
    def isSuperPeer(self, permid):
        return permid in self._get('superpeers')
    
    def getSuperPeers(self):
        superpeers = self._get('superpeers')
        if superpeers is not None:
            return list(superpeers)
        else:
            return []
    
    # friends
    def addFriend(self, permid):
        if isValidPermid(permid):
            if not 'friends' in self._keys():
                print >> sys.stderr, "cachedb: addFriend key error", self._keys()
            fr = self._get('friends')
            fr.add(permid)
            self._put('friends', fr)
            
    def deleteFriend(self, permid):
        try:
            fr = self._get('friends')
            fr.remove(permid)
            self._put('friends', fr)
        except:
            pass
            
    def isFriend(self, permid):
        return permid in self._get('friends')
    
    def getFriends(self):
        friends = self._get('friends')
        if friends is not None:
            return list(friends)
        else:
            return []
    

class PeerDB(BasicDB):
    """ List of Peers, e.g. Host Cache """
    
    __single = None
    
    def __init__(self, db_dir=''):
        if PeerDB.__single:
            raise RuntimeError, "PeerDB is singleton"
        self.db_name = 'peers.bsd'
        self._data = open_db(self.db_name, db_dir)    # dbshelve object
        MyDB.checkVersion(self)
        PeerDB.__single = self
        self.default_item = {
            'ip':'',
            'port':0,
            'name':'',
            'last_seen':0,
            'similarity':0,
            'connected_times':0,
            'tried_times':0,
            'buddycast_times':0,
            #'trust':50,
            #'reliability':
            #'icon':'',
        }
        self.new_encountered_peer = True
        
    def getInstance(*args, **kw):
        if PeerDB.__single is None:
            PeerDB(*args, **kw)
        return PeerDB.__single
    getInstance = staticmethod(getInstance)

    def updateItem(self, permid, item={}, update_dns=True, update_time=True):    # insert a peer; update it if existed
#        if item.has_key('name'):
#            assert item['name'] != 'qfqf'
        if isValidPermid(permid) and validDict(item):
            if self._has_key(permid):
                _item = self.getItem(permid)
                if _item is None:  # database error, the key exists, but the data ain't there
                    return
                if not update_dns:
                    if item.has_key('ip'):
                        item.pop('ip')
                    if item.has_key('port'):
                        item.pop('port')
                _item.update(item)
                if update_time:
                    _item.update({'last_seen':int(time())})
                self._updateItem(permid, _item)
            else:
                item = self.setDefaultItem(item)
                if update_time:
                    item.update({'last_seen':int(time())})
                self._put(permid, item)
                
    def deleteItem(self, permid):
        self._delete(permid)
        
    def getItem(self, permid, default=False):
        ret = self._get(permid, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        return ret
    
    def hasItem(self, permid):
        return self._has_key(permid)
        
    def hasNewEncounteredPeer(self, v):
        self.new_encountered_peer = v


class TorrentDB(BasicDB):
    """ Database of all torrent files, including the torrents I don't have yet """
    
    __single = None
        
    def __init__(self, db_dir=''):
        if TorrentDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'torrents.bsd'
        self._data = open_db(self.db_name, db_dir)    # dbshelve object
        MyDB.checkVersion(self)
        TorrentDB.__single = self
        self.default_item = {
            'relevance':0,
            'torrent_name':'',   # name of the torrent
            'torrent_dir':'',   # dir+name=full path. Default path if the value is '\x01'
            'info':{},   # {name, length, announce, creation date, comment}
        }
        self.new_metadata = True
        
    def getInstance(*args, **kw):
        if TorrentDB.__single is None:
            TorrentDB(*args, **kw)
        return TorrentDB.__single
    getInstance = staticmethod(getInstance)
    
    def updateItem(self, infohash, item={}):    # insert a torrent; update it if existed
        if isValidInfohash(infohash) and validDict(item):
            if self._has_key(infohash):
                _item = self.getItem(infohash)
                if not _item:
                    print >> sys.stderr, "cachedb: Error in cachedb.TorrentDB.updateItem: database inconsistant!", self._has_key(infohash), self.getItem(infohash)
                    return
                _item.update(item)
                self._updateItem(infohash, _item)
            else:
                item = self.setDefaultItem(item)
                self._put(infohash, item)

    def deleteItem(self, infohash):
        self._delete(infohash)
        
    def getItem(self, infohash, default=False):
        ret = self._get(infohash, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        return ret
    
    def hasNewMetadata(self, v):
        self.new_metadata = v
        

class PreferenceDB(BasicDB):
    """ Peer * Torrent """
    
    __single = None
    
    def __init__(self, db_dir=''):
        if PreferenceDB.__single:
            raise RuntimeError, "PreferenceDB is singleton"
        self.db_name = 'preferences.bsd'
        self._data = open_db(self.db_name, db_dir)    # dbshelve object
        MyDB.checkVersion(self)
        PreferenceDB.__single = self 
        self.default_item = {    # subitem actually
            'relevance':0,     # relevance from the owner of this torrent
            'rank':0
        }

    def getInstance(*args, **kw):
        if PreferenceDB.__single is None:
            PreferenceDB(*args, **kw)
        return PreferenceDB.__single
    getInstance = staticmethod(getInstance)

    def addPreference(self, permid, infohash, data={}):    # add or update pref
        if not isValidPermid(permid) or not isValidInfohash(infohash):
            return
        
        if not self._has_key(permid):
            data = self.setDefaultItem(data)
            item = {infohash:data}
        else:
            if self.hasPreference(permid, infohash):
                _data = self.getPreference(permid, infohash)
                _data.update(data)
            else:
                _data = self.setDefaultItem(data)
            _item = {infohash:_data}
            item = self.getItem(permid)
            item.update(_item)
        self._put(permid, item)
                        
    def deletePreference(self, permid, infohash):
        if self._has_key(permid):
            preferences = self._get(permid)
            preferences.pop(infohash)
            self._put(permid, preferences)
            
    def getPreference(self, permid, infohash):
        if self._has_key(permid):
            preferences = self._get(permid)
            if preferences.has_key(infohash):
                return preferences[infohash]
        return None
            
    def hasPreference(self, permid, infohash):
        if self._has_key(permid):
            return infohash in self._get(permid)
        else:
            return False

    def deleteItem(self, permid):
        self._delete(permid)

    def getItem(self, permid):
        return self._get(permid, {})


class MyPreferenceDB(BasicDB):     #  = FileDB
    
    __single = None
        
    def __init__(self, db_dir=''):
        if MyPreferenceDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'mypreferences.bsd'
        self._data = open_db(self.db_name, db_dir)    # dbshelve object
        MyDB.checkVersion(self)
        MyPreferenceDB.__single = self 
        self.default_item = {
            'created_time':0,
            'rank':0,  # -1 ~ 5, as a recommendation degree to others
            'content_name':'',  # real file name in disk, may be different with info['name']
            'content_dir':'',   # dir + name = full path
            'last_seen':0,
        }
                
    def getInstance(*args, **kw):
        if MyPreferenceDB.__single is None:
            MyPreferenceDB(*args, **kw)
        return MyPreferenceDB.__single
    getInstance = staticmethod(getInstance)

    def updateItem(self, infohash, item={}):    # insert a torrent; update it if existed
        if isValidInfohash(infohash) and validDict(item):
            if self._has_key(infohash):
                _item = self.getItem(infohash)
                _item.update(item)
                _item.update({'last_seen':int(time())})
                self._updateItem(infohash, _item)
            else:
                self.default_item['created_time'] = self.default_item['last_seen'] = int(time())
                item = self.setDefaultItem(item)
                self._put(infohash, item)
        self._sync()
                
    def deleteItem(self, infohash):
        self._delete(infohash)
        self._sync()
        
    def getItem(self, infohash, default=False):
        ret = self._get(infohash, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        return ret
    
    def getRank(self, infohash):
        v = self._get(infohash)
        if not v:
            return 0
        return v.get('rank', 0)
        
    
class OwnerDB(BasicDB):
    """ Torrent * Peer """
    
    __single = None
    
    def __init__(self, db_dir=''):
        if OwnerDB.__single:
            raise RuntimeError, "OwnerDB is singleton"
        self.db_name = 'owners.bsd'
        self._data = open_db(self.db_name, db_dir)    # dbshelve object
        OwnerDB.__single = self 
                
    def getInstance(*args, **kw):
        if OwnerDB.__single is None:
            OwnerDB(*args, **kw)
        return OwnerDB.__single
    getInstance = staticmethod(getInstance)
    
    def getNumOwners(self, infohash):
        owners = self._get(infohash)
        if owners is not None:
            n = len(owners)
        else:
            n = 0
        #print n, `infohash`, owners
        return n
        

    def addOwner(self, infohash, permid):
        if isValidPermid(permid) and isValidInfohash(infohash):
            if self._has_key(infohash):
                owners = self._get(infohash)
                owners.add(permid)
                self._put(infohash, owners)
            else:
                self._put(infohash, Set([permid]))
        
    def deleteOwner(self, infohash, permid):
        try:
            owners = self._get(infohash)
            owners.remove(permid)
            if not owners:    # remove the item if it is empty
                self._delete(infohash)
            else:
                self._put(infohash, owners)
        except:
            pass
        
    def isOwner(self, permid, infohash):
        if self._has_key(infohash):
            owners = self._get(infohash)
            return permid in owners
        else:
            return False
        
    def deleteItem(self, infohash):
        self._delete(infohash)

    def getItem(self, infohash):
        owners = self._get(infohash)
        if owners is not None:
            return list(owners)
        else:
            return []
                    