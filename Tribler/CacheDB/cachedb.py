# Written by Jie Yang
# see LICENSE.txt for license information

## TODO: update database V3:
# TorrentDB: clean relevance, insert time
# PeerDB: clean similarity, insert time
# PreferenceDB: clean  permid:torrent_id:{}

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
        oversion: int(0)    # overlay version, added in 3.7.1, overlay version 4
        connected_times: int(0)    # times to connect the peer successfully
        #tried_times: int(0)        # times to attempt to connect the peer, removed from 3.7.1
        buddycast_times: int(0)    # times to receive buddycast message
        last_buddycast_time: int (0)    # from buddycast 3/tribler 3.7
        #relability (uptime, IP fixed/changing)
        #trust: int (0)    # [0, 100]
        #icon: str ('')    # name + '_' + permid[-4:]
        npeers: int(0)     # added in 4.1, overlay version 6
        ntorrents: int(0)  # added in 4.1, overlay version 6  
        nprefs: int(0)     # added in 4.1, overlay version 6
        nqueries: int(0)   # added in 4.1, overlay version 6
    }

TorrentDB - (PreferenceDB, MyPreference, OwnerDB)
  torrents.bsd:    # future keys: names, tags, trackers, ..
    infohash:{
        relevance: int (0)    # [0, 1000]
        torrent_name: str ('')    # torrent name
        torrent_dir: str ('')    # path of the torrent (without the file name). '\x01' for default path
        info: dict ({})   # {name, length, announce, creation date, comment, announce-list, num_files}
        # new keys in database version 2
        leecher: int (-1)
        seeder: int (-1)
        category: list ()
        ignore_number: int (0)
        last_check_time: long (time())
        retry_number: int (0)
        status: str ("unknown")
        source: str("")
        inserttime: long (time())
        progress: float
        destdir: str("")
    }

PreferenceDB - (PeerDB, TorrentDB)    # other peers' preferences
  preferences.bsd:
    permid:{
        torrent_id:{
        # 'relevance': int (0), 'rank': int (0), removed from 3.6
        }
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
from traceback import print_exc, print_stack
from threading import currentThread

from BitTornado.bencode import bencode, bdecode
from Tribler.utilities import isValidIP

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
# Database schema versions (for all databases)
# 1 = First
# 2 = Added keys to TorrentDB:  leecher,seeder,category,ignore_number,last_check_time,retry_number,status
# 3 = Added keys to TorrentDB: source,inserttime
# 4 = Added keys to PeerDB: npeers, ntorrents, nprefs, nqueries
#
curr_version = 4
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

def init(config_dir, myinfo, db_exception_handler = None):
    """ create all databases """
    
    global home_dir
    home_dir = make_filename(config_dir, 'bsddb')
    if DEBUG:
        print "Init database at", home_dir
    BasicDB.exception_handler = db_exception_handler
    MyDB.getInstance(myinfo, home_dir)
    PeerDB.getInstance(home_dir)
    TorrentDB.getInstance(home_dir)
    PreferenceDB.getInstance(home_dir)
    MyPreferenceDB.getInstance(home_dir)
    OwnerDB.getInstance(home_dir)
    MyDB.updateDBVersion(curr_version)
    
def done(config_dir):
    MyDB.getInstance().close()
    MyPreferenceDB.getInstance().close()
    OwnerDB.getInstance().close()
    PeerDB.getInstance().close()
    PreferenceDB.getInstance().close()
    TorrentDB.getInstance().close()


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
    env.open(dir, db.DB_THREAD|db.DB_INIT_CDB|db.DB_INIT_MPOOL|db.DB_CREATE|db.DB_PRIVATE)
    #d = db.DB(env)
    #d.open(path, filetype, db.DB_THREAD|db.DB_CREATE)
    #_db = BsdDbShelf(d, writeback=writeback) 
    _db = dbshelve.open(filename, flags=db.DB_THREAD|db.DB_CREATE, 
            filetype=filetype, dbenv=env)
    return _db, dir

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
        
    exception_handler = None
        
    def __init__(self, db_dir=''):
        self.default_item = {}    #{'d':1, 'e':'abc', 'f':{'k':'v'}, 'g':[1,'2']} # for test
        if self.__class__ == BasicDB:
            self.db_name = 'basic.bsd'    # for testing
            self.opened = True
            
            self.db_dir = db_dir
            self.filetype = db.DB_BTREE
            self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)
        
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
                print >> sys.stderr, "cachedb: put", len(self.threadnames), name, \
                    self.threadnames[name], time(), self.__class__.__name__
            if not value and type(value) == dict:
                raise Exception('Warning someone tries to insert empty data in db: %s:%s'% (key, value))
            
            dbutils.DeadlockWrap(self._data.put, key, value, max_retries=MAX_RETRIES)
            #self._data.put(key, value)
        except:
            pass
        
    def _has_key(self, key):    # find a key
        try:
            return dbutils.DeadlockWrap(self._data.has_key, key, max_retries=MAX_RETRIES)
            #return self._data.has_key(key)
        except Exception, e:
            print >> sys.stderr, "cachedb: _has_key EXCEPTION BY",currentThread().getName(), Exception, e, self.db_name, `key`
            return False
    
    def _get(self, key, value=None):    # read
        try:
            #if self.db_name == 'torrents.bsd':
            #    self.count += 1
            #    if self.count % 3000 == 0:
            #        print "GET"
            #        print_stack()
            
            return dbutils.DeadlockWrap(self._data.get, key, value, max_retries=MAX_RETRIES)
            #return self._data.get(key, value)
#        except db.DBRunRecoveryError, e:
#            print >> sys.stderr, "cachedb: Sorry, meet DBRunRecoveryError at get, have to remove the whole database", self.db_name
#            self.report_exception(e)
#            self._recover_db()    # have to clear the whole database
        except Exception,e:
            print >> sys.stderr, "cachedb: _get EXCEPTION BY",currentThread().getName(), Exception, e, self.db_name, `key`, value
            if value is not None:
                return value
            self.report_exception(e)
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
                print >> sys.stderr, "cachedb: del", len(self.threadnames), name, \
                    self.threadnames[name], time(), self.__class__.__name__
                
            dbutils.DeadlockWrap(self._data.delete, key, max_retries=MAX_RETRIES)
            #self._data.delete(key)
        except:
            pass

    def _sync(self):            # write data from mem to disk
        try:
            dbutils.DeadlockWrap(self._data.sync, max_retries=MAX_RETRIES)
#        except db.DBRunRecoveryError, e:
#            print >> sys.stderr, "cachedb: Sorry, meet DBRunRecoveryError at sync, have to remove the whole database", self.db_name
#            self.report_exception(e)
#            self._recover_db()    # have to clear the whole database
        except Exception, e:
            #print >> sys.stderr, "cachedb: synchronize db error", self.db_name, Exception, e
            self.report_exception(e)
            
    def _clear(self):
        dbutils.DeadlockWrap(self._data.clear, max_retries=MAX_RETRIES)
        #self._data.clear()
    
#===============================================================================
#    def _recover_db(self):
#        path = os.path.join(self.db_dir, self.db_name)
#        try:
#            self._data.close()
#            print >> sys.stderr, "cachedb: closed and removing database", path
#            os.remove(path)
#            print >> sys.stderr, "cachedb: removed database", path
#            self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)    # reopen
#            print >> sys.stderr, "cachedb: database is removed and reopened successfully", path
#        except Exception, msg:
#            print_exc()
#            print >> sys.stderr, "cachedb: cannot remove the database", path, Exception, msg
#===============================================================================
    
    def _keys(self):
        try:
            return dbutils.DeadlockWrap(self._data.keys, max_retries=MAX_RETRIES)
            #return self._data.keys()
        except Exception,e:
            print >> sys.stderr, "cachedb: _keys EXCEPTION BY", currentThread().getName(), self.db_name
            #print_exc()
            self.report_exception(e)
            return []
    
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

    def _iteritems(self):
        try:
            return dbutils.DeadlockWrap(self._data.iteritems, max_retries=MAX_RETRIES)
        except:
            print_exc()
            print >> sys.stderr, "cachedb: cachedb.BasicDB._iteritems error", self.__class__.__name__
    
    def close(self):
        if DEBUG:
            print >> sys.stderr, "cachedb: Closing database",self.db_name,currentThread().getName()
        if self.opened:
            try:
                self._sync()
                dbutils.DeadlockWrap(self._data.close, max_retries=MAX_RETRIES)
                if DEBUG:
                    print >> sys.stderr, "cachedb: Done waiting for database close",self.db_name,currentThread().getName()
                #self._data.close()
            except:
                print_exc()
        self.opened = False
        
    def updateDB(self, old_version):
        pass

    def setDefaultItem(self, item):
        df = deepcopy(self.default_item)
        df.update(item)
        return df
    
    def report_exception(self,e):
        #return  # Jie: don't show the error window to bother users
        if BasicDB.exception_handler is not None:
            BasicDB.exception_handler(e)
    
    
class MyDB(BasicDB):
    
    __single = None

    def __init__(self, myinfo=None, db_dir=''):
        if MyDB.__single:
            raise RuntimeError, "MyDB is singleton"
        self.db_name = 'mydata.bsd'
        self.opened = True
        
        self.db_dir = db_dir
        self.filetype = db.DB_HASH
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)

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
        self.friend_set = Set(self._get('friends'))
            
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
        #elif old_version > curr_version:
            #FIXME: user first install 3.4.0, then 3.5.0. Now he cannot reinstall 3.4.0 anymore
        #    raise RuntimeError, "The version of database is too high. Please update the software."
    checkVersion = staticmethod(checkVersion)
    
    def updateDBVersion(db):
        MyDB.__single._put('version', curr_version)
        MyDB.__single._sync()
    updateDBVersion = staticmethod(updateDBVersion)
    
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
            self.friend_set = Set(fr)
            
    def deleteFriend(self, permid):
        try:
            fr = self._get('friends')
            fr.remove(permid)
            self._put('friends', fr)
            self.friend_set = Set(fr)
        except:
            pass
            
    def isFriend(self, permid):
        return permid in self.friend_set
    
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
        self.opened = True
        
        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)
        
        MyDB.checkVersion(self)
        PeerDB.__single = self
        self.num_encountered_peers = -100
        self.default_item = {
            'ip':'',
            'port':0,
            'name':'',
            'last_seen':0,
            'similarity':0,
            'connected_times':0,
            'oversion':0,   # overlay version
            'buddycast_times':0,
            'last_buddycast_time':0,
            #'trust':50,
            #'reliability':
            #'icon':'',
            'npeers':0,
            'ntorrents':0,
            'nprefs':0,
            'nqueries':0
        }
        
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
        """ Arno: At the moment we keep a copy of the PeerDB in memory,
         see Tribler.vwxGUI.peermanager. This class, however, already converts
         the records using the save-memory by sharing key strings trick (see 
         TorrentDB) so there's no need to have that here. """
        ret = self._get(permid, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        return ret
    
    def hasItem(self, permid):
        return self._has_key(permid)
        
    def updateDB(self, old_version):
        if old_version == 1 or old_version == 2 or old_version == 3:
            def_newitem = {
                'oversion':0,
                'npeers': 0,
                'ntorrents': 0,
                'nprefs': 0,
                'nqueries':0 }
            keys = self._keys()
            for key in keys:
                self._updateItem(key, def_newitem)


class TorrentDB(BasicDB):
    """ Database of all torrent files, including the torrents I don't have yet """
    
    __single = None
        
    def __init__(self, db_dir=''):
        if TorrentDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'torrents.bsd'
        self.opened = True

        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)

        MyDB.checkVersion(self)
        TorrentDB.__single = self
        self.default_item = {
            'relevance':0,
            'torrent_name':'',   # name of the torrent
            'torrent_dir':'',   # dir+name=full path. Default path if the value is '\x01'
            'info':{},   # {name, length, announce, creation date, comment}
            'leecher': -1,
            'seeder': -1,
            'category': [],
            'ignore_number': 0,
            'last_check_time': 0,
            'retry_number': 0,
            'status': 'unknown',
            'source': '',
            'inserttime': 0,
            'progress': 0.0,
            'destdir':'',
            'secret':False # download secretly
        }
        self.infokey = 'info'
        self.infokeys = ['name','creation date','num_files','length','announce','announce-list']
#        self.num_metadatalive = -100
        
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
        
    def getItem(self, infohash, default=False,savemem=False):
        """ Arno: At the moment we keep a copy of the TorrentDB in memory,
         see Tribler.vwxGUI.torrentManager. A lot of memory can be saved
         by reusing/sharing the strings of the keys in the database records (=dicts).
         When the savemem option is enabled, the dict returned will have the
         key strings of the self.default_item. """
        ret = self._get(infohash, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        if savemem:
            newret = {}
            for key in self.default_item:
                newret[key] = ret.get(key)
            newinfo = {}
            for key in self.infokeys:
                newinfo[key] = ret['info'][key]
            newret[self.infokey] = newinfo
            return newret
        return ret
    
    def updateDB(self, old_version):
        if old_version == 1:
            def_newitem = {
                'category': ['?'],
                'ignore_number': 0,
                'last_check_time': long(time()),
                'retry_number': 0,
                'seeder': -1,
                'leecher': -1,
                'status': "unknown"}
            keys = self._keys()
            for key in keys:
                self._updateItem(key, def_newitem)
        if old_version == 1 or old_version == 2:
            def_newitem = {
                'source': '',
                'inserttime': 0,
                'progress': 0.0,
                'destdir':''}
            keys = self._keys()
            for key in keys:
                self._updateItem(key, def_newitem)
            
    
class PreferenceDB(BasicDB):
    """ Peer * Torrent """
    
    __single = None
    
    def __init__(self, db_dir=''):
        if PreferenceDB.__single:
            raise RuntimeError, "PreferenceDB is singleton"
        self.db_name = 'preferences.bsd'
        self.opened = True
        
        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)
        
        MyDB.checkVersion(self)
        PreferenceDB.__single = self 
        self.default_item = {    # subitem actually
            #'relevance':0,     # relevance from the owner of this torrent
            #'rank':0
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
        self.opened = True
        
        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)
        
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

    def hasPreference(self, infohash):
        return self._has_key(infohash)
    
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
        self.opened = True
        
        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)
        
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
 
class IP2PermIDDB(BasicDB):
    """ IP * Peer """

    __single = None

    def __init__(self, db_dir=''):
        if IP2PermIDDB.__single:
            raise RuntimeError, "IP2PermIDDB is singleton"
        self.db_name = 'ip2permid.bsd'
        self.opened = True

        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, db_dir, filetype=self.filetype)
        IP2PermIDDB.__single = self 

    def getInstance(*args, **kw):
        if IP2PermIDDB.__single is None:
            IP2PermIDDB(*args, **kw)
        return IP2PermIDDB.__single
    getInstance = staticmethod(getInstance)


    def addIP(self, ip, permid):
        if not isValidPermid(permid) or not isValidIP(ip):
            return

        self._put(ip,permid)

    def getPermIDByIP(self, ip):
        if not isValidIP(ip):
            return None

        if not self._has_key(ip):
            return None
        else:
            return self._get(ip)

    def deletePermID(self, permid):
        for ip, permid2 in self._items():
            if permid == permid2:
                self._delete(ip)
                break


# DB extension for BarterCast statistics
class BarterCastDB(BasicDB):

    __single = None

    def __init__(self, db_dir=''):
        if BarterCastDB.__single:
            raise RuntimeError, "BarterCastDB is singleton"
        self.db_name = 'bartercast.bsd'
        self.opened = True

        self.db_dir = db_dir
        self.filetype = db.DB_BTREE
        self._data, self.db_dir = open_db(self.db_name, self.db_dir, filetype=self.filetype)

        MyDB.checkVersion(self)
        BarterCastDB.__single = self
        self.num_encountered_peers = -100
        self.default_item = {
            'last_seen':0,
            'value': 0,
            'downloaded': 0,
            'uploaded': 0,
        }

    def getInstance(*args, **kw):
        if BarterCastDB.__single is None:
            BarterCastDB(*args, **kw)
        return BarterCastDB.__single
    getInstance = staticmethod(getInstance)

    def updateItem(self, (permid_from, permid_to), item={}, update_time=True):    # insert a peer; update it if existed

        if isValidPermid(permid_from) and isValidPermid(permid_to) and validDict(item):

            key = bencode((permid_from, permid_to))
            if self._has_key(key):
                _item = self.getItem((permid_from, permid_to))
                if _item is None:  # database error, the key exists, but the data ain't there
                    return
                _item.update(item)
                if update_time:
                    _item.update({'last_seen':int(time())})
                self._updateItem(key, _item)
            else:
                item = self.setDefaultItem(item)
                if update_time:
                    item.update({'last_seen':int(time())})
                self._put(key, item)

    def deleteItem(self, (permid_from, permid_to)):
        key = bencode((permid_from, permid_to))
        self._delete(key)

    def getItem(self, (permid_from, permid_to), default=False):
        key = bencode((permid_from, permid_to))
        ret = self._get(key, None)
        if ret is None and default:
            ret = deepcopy(self.default_item)
        return ret

    def hasItem(self, (permid_from, permid_to)):
        key = bencode((permid_from, permid_to))
        return self._has_key(key) 
 
#===============================================================================
# class ActionDB(BasicDB):
#    
#    __single = None
#    
#    def __init__(self, db_dir=''):
#        if ActionDB.__single:
#            raise RuntimeError, "ActionDB is singleton"
#        self.db_name = 'actions.bsd'
#        self.opened = True
#        env = db.DBEnv()
#        # Concurrent Data Store
#        env.open(db_dir, db.DB_THREAD|db.DB_INIT_CDB|db.DB_INIT_MPOOL|db.DB_CREATE|db.DB_PRIVATE)
#        self._data = db.DB(dbEnv=env)
#        self._data.open(self.filename, db.DB_RECNO, db.DB_CREATE)
#        ActionDB.__single = self 
#                
#    def getInstance(*args, **kw):
#        if ActionDB.__single is None:
#            ActionDB(*args, **kw)
#        return ActionDB.__single
#    getInstance = staticmethod(getInstance)
#===============================================================================
    
    
        
        
