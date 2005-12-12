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
    superpeers: dict ({})    # {'peer_id':weight}

PeerDB - (FriendDB, PreferenceDB, OwnerDB)
  peers.bsd:    # future keys: sys_trust, reliablity, speed, personal_info, ..
    peer_id:{       # peer_id = sha(permid).digest(), 20Bytes
        permid: str    # required
        ip: str ('')
        port: int (0)
        name: str ('unknown')
        last_seen: int (0)
        my_trust: float (5.0)
        similarity: float (0.0)
        }

TorrentDB - (PreferenceDB, MyPreference, OwnerDB)
  torrents.bsd:    # future keys: names, tags, trackers, ..
    torrent_hash:{    # it can be info_hash or merkele hash
        have: int (0)   # 0: have nothing; 
                          1: have this torrent info, but may not have the .torrent file; 
                          2: have this .torrent file, but may not have downloaded the files
                          3: have the files
        recommendation: float (0.0) # -1 ~ 5.0
            # if have > 0, have the following keys
        torrent_name: str ('')
        info: dict ({})   # {name, length, announce, creation date, comment}
        my_rank: int (0)  # 0 ~ 5, as a feedback to recommendation system
            # if have > 1, have the following keys
        torrent_path: str ('')
            # if have > 2, look up mypreferences.bsd for more info
        }
        
MyPrefrenceDB - (TorrentDB)
  mypreferences.bsd:    # future keys: speed
    torrent_hash:{
        created_time: int (0)
        content_length: int (0) # downloaded file size, may be different with info['length']
        content_name: str ('')  # real file name in disk, may be different with info['name']
        content_dir: str ('')   # content_dir + content_name = full path
        my_rank: int(0)  # -1 ~ 5, as a recommendation degree to others
        last_seen: int (0)
        }
        
FriendDB - (PeerDB)
  friends.bsd: 
    peer_id: {
        peer_id: dict ({})    # {peer_id:{'my_trust'}}, only primary friends, future keys: sys_trust
        }

OwnerDB - (PeerDB, TorrentDB)
  owner.bsd:
    torrent_hash:{
        peer_id: dict ({})    # {peer_id:{'my_rank'}},  future keys: tags, name
        }    
    
PrefernceDB - (PeerDB, TorrentDB)
  preferences.bsd:
    peer_id:{
        torrent_hash: dict ({})    # {torrent_hash:{'my_rank'}}
    }
"""

import os
from time import time, ctime
from random import random
from sha import sha

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
    
class BasicDB:
        
    # Policy: only _foo() can operate _data, and only member functions in CacheDBInterface can call _foo()
    def __del__(self):
        self._sync()

    def _sync(self):            # synchronize
        self._data.sync()

    def _update(self, data):    # the only place to write
        try:
            self._data.update(data)
            self._data.sync()    # how often to do sync?
        except:
            pass
        
    def _insert(self, key, value):
        self._update({key:value})
        
    def _get(self, key, value=None):    # read
        return self._data.get(key, value)
        
    def _getall(self):
        return self._data.values()
        
    def _remove(self, key):     # remove
        if key in self._data:
            self._data.pop(key)    
    
    def findKey(self, key):
        if key in self._data:
            return True
        return False

    def updateKey(self, key, value):
        self._insert(key, value)
        
    def updateDB(self, old_version):
        pass
        
#------------ Interface for subclasses --------------#
    def insert(self, data):
        pass
            
    def get(self, key, value=None):
        pass
    
    def update(self, data):
        pass
        
    def remove(self, key):
        pass
        
    def find(self, key):
        pass
    
class MyDB(BasicDB):
    
    __single = None
    init_set = {'version':curr_version, 
                'permid':None, 
                'ip':'', 
                'port':0, 
                'name':'Chitraka', 
                'superpeers':[]}

    def __init__(self, myinfo=None, db_dir=''):
        if MyDB.__single:
            raise RuntimeError, "PeerDB is singleton"
        self.db_name = 'mydata.bsd'
        self._data = open_db(self.db_name, db_dir, filetype=db.DB_HASH)    # dbshelve object
        self.initData(myinfo)
        MyDB.__single = self 
        
    def getInstance(*args, **kw):
        if MyDB.__single is None:
            MyDB(*args, **kw)
        return MyDB.__single
    getInstance = staticmethod(getInstance)

    def initData(self, myinfo=None):
        self.checkVersion(self)
        self._update(myinfo)
        for key, value in self.init_set.items():
            if not self.findKey(key):
                self._insert(key, value)
        
    def checkVersion(self, db):
        old_version = self._get('version')
        if not old_version:
            self.updateKey('version', curr_version)
        elif old_version < curr_version:
            db.updateDB(old_version)
        elif old_version > curr_version:
            raise RuntimeError, "The version of database is too high. Please update the software."
            

class PeerDB(BasicDB):
    """ List of Peers, e.g. Host Cache """
    
    __single = None
    default_peer = {'permid':'',
                    'ip':'',
                    'port':0,
                    'name':'unknown',
                    'last_seen':0,
                    'my_trust':5.0,
                    'similarity':0.0,
                    }
    
    def __init__(self):
        if PeerDB.__single:
            raise RuntimeError, "PeerDB is singleton"
        self.db_name = 'peers.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        PeerDB.__single = self
        self.mydb = MyDB.getInstance()
        self.mydb.checkVersion(self)

    def getInstance(*args, **kw):
        if PeerDB.__single is None:
            PeerDB(*args, **kw)
        return PeerDB.__single
    getInstance = staticmethod(getInstance)

    def getID(self, permid):
        """ Return local id of a peer """
        
        if not isinstance(permid, str):
            return None
        return sha(permid).digest()    # Real engineers keep it simple :)
        
    def setDefault(self, peer):
        """ Set default values to a peer """
        
        for key,value in self.default_peer.items():
            if not peer.has_key(key) or not peer[key]:
                peer[key] = value
        
    def validPeer(self, peer):
        if not (isinstance(peer, dict) and peer.has_key('permid')):
            return False
        return True
                
    def insert(self, peer):
        """ Add a peer if it doesn't exist; otherwise update the status of this peer """
        
        if not self.validPeer(peer):
            return
        id = self.getID(peer['permid'])
        if self.findKey(id):
            self.updateKey(id, peer)
        else:
            self.setDefault(peer)
            self._insert(id, peer)
            
    def get(self, permid, value=None):
        """ search a peer from the database according to its permid """
        
        id = self.getID(permid)
        return self._get(id, value)
    
    def update(self, peer):
        if not self.validPeer(peer):
            return
        permid = peer['permid']
        id = self.getID(permid)
        self.updateKey(id, peer)
        
    def remove(self, permid):
        id = self.getID(permid)
        return self._pop(id)
        
    def find(self, permid):
        id = self.getID(permid)
        return self.findKey(id)
        

class FriendDB:
    """ List of Peers, e.g. Host Cache """
    
    __single = None
    
    def __init__(self):
        if FriendDB.__single:
            raise RuntimeError, "FriendDB is singleton"
        self.db_name = 'friends.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        FriendDB.__single = self
        self.mydb = MyDB.getInstance()
        self.mydb.checkVersion(self)
        self.torrents = TorrentDB.getInstance()    # peers : torrents : preferences = 1 : 1 : 1
        self.preferences = PreferenceDB.getInstance()
        self.peers = PeerDB.getInstance()

    def getInstance(*args, **kw):
        if FriendDB.__single is None:
            FriendDB(*args, **kw)
        return FriendDB.__single
    getInstance = staticmethod(getInstance)

    def __del__(self):
        self._sync()

    def _sync(self):
        self._data.sync()

    def close(self):
        self._data.close()
        
    def updateDB(self, old_version):
        pass
    
    def getAllFriendsID(self):
        return self._data['friends']

    def hasFriendID(self, permid):
        id = self.getID(permid)
        return id in self._data['friends']

    def addFriendID(self, permid):
        if self.hasFriendID(permid):
            return
        if self.peers.hasPeerID(permid):
            id = self.getID(permid)
            self._data['friends'].append(id)

    def removeFriendID(self, permid):
        id = self.getID(permid)
        try:
            self._data['friends'].remove(id)
        except ValueError:
            pass

    def addFriend(self, friend_permid, layer=1, owner=None, detail=None):
        """ add a friend """
        
        friend_id = self.getID(friend_permid)
        if not self._data.has_key(friend_id):
            print "The peer to be friend is not found in record"
            return
        if self.mydb.hasFriendID(friend_permid) and self.mydb[friend_id]:
            pass
        if not owner:
            self.mydb._data['my_friends'].append(friend_id)
            self._data[friend_id]['friend_layer'] = layer
        else:
            owner_id = self.getID(owner)
            if not self._data.has_key(owner_id):
                print "The owner of the friend is not found in record"
                return
            self._data[owner_id]['friends'].append(friend_id)
                        
    def removeFriend(self, friend_permid):
        """ delete a matched record if id is not None;
        otherwise delete a matched record if perm_id is not None
        """
        
        friend_id = self.getID(friend_permid)
        try:
            self.mydb._data['my_friends'].remove(friend_id)
        except:
            pass
        try:
            self._data[friend_id]['friend_layer'] = 0
        except:
            pass
   

class TorrentDB:
    """ Database table of torrent files, including my and my friends' torrents, 
    e.g. File cache 
    """
    torrents_columns = ['id', 'torrent_hash', 'torrent_name', 'torrent_path', 
                                 'content_name', 'content_path', 'content_size',
                                 'num_files', 'others', 'created_time', 'last_seen',
                                 'my_rank', 'recommendation', 'have']
        
    __single = None
    
    def __init__(self):
        if TorrentDB.__single:
            raise RuntimeError, "TorrentDB is singleton"
        self.db_name = 'torrents.bsd'
        self._data = open_db(self.db_name)    # dbshelve object
        TorrentDB.__single = self 
        self.torrents = open_db(self.db_name)    # dbshelve object
        self.peers = PeerDB.getInstance()    # peers : torrents : preferences = 1 : 1 : 1
        self.preferences = PreferenceDB.getInstance()
                
    def getInstance(*args, **kw):
        if TorrentDB.__single is None:
            TorrentDB(*args, **kw)
        return TorrentDB.__single
    getInstance = staticmethod(getInstance)

    def __del__(self):
        self._sync()

    def _sync(self):
        self._data.sync()
        
    def close(self):
        self._data.close()
        
    def createDB(self, db_dir=None):
        try:
            self.torrents.CreateTable(self.torrents_table, self.torrents_columns)
        except TableDBError:
            pass
        
    def getMaxID(self):
        max_id = 0
        ids = self.torrents.Select(self.torrents_table, ['id'], {'id':Cond()})
        for id in ids:
            loadRecord(id)
            if id['id'] >= max_id:
                max_id = int(id['id'])
        return max_id        
        
    def getRecords(self):
        records = self.torrents.Select(self.torrents_table, 
                                       self.torrents_columns, {self.torrents_columns[0]:Cond()})
        for record in records:
            loadRecord(record)    # restore the original data type
        return records

    def printRecords(self):
        records = self.getRecords()
        print "========== all records in torrent table=============", len(records)
        for record in records:
            print record
   
    def addTorrent(self, torrent, have=1):
        torrent_hash = torrent.get('torrent_hash', '')
        records = self.findTorrent(torrent_hash=torrent_hash)
        if not records:
            current = int(time()) - int(random()*300000)
            record = {'created_time':current, 'last_seen':current, 
                      'recommendation':0, 'have':have}
            record.update(torrent)
            if not record.has_key('my_rank'):
                record['my_rank'] = 0
            id = record['id'] = self.getMaxID() + 1
            dumpRecord(record)
            self.torrents.Insert(self.torrents_table, record)
        else:
            id = records[0]['id']
            self.updateTorrent(id, torrent)
        return id
            
    def findTorrent(self, torrent_hash=None, torrent_id=None):    # find both id and hash
        """ search torrents in the database """
        
        if torrent_id:
            res = self.torrents.Select(self.torrents_table, self.torrents_columns, 
                                       conditions = {'id':ExactCond(dump(torrent_id))})
        elif torrent_hash:
            res = self.torrents.Select(self.torrents_table, self.torrents_columns, 
                                       conditions = {'torrent_hash':ExactCond(dump(torrent_hash))})
        else:
            res = []
        for item in res:
            loadRecord(item)
        return res    
        
    def updateTorrentRank(self, torrent_id, rank):
        
        self.torrents.Modify(self.torrents_table,
                        conditions={'id':ExactCond(dump(torrent_id))},
                        mappings={'my_rank':lambda x:dump(rank)})
            
    def updateTorrent(self, torrent_id, torrent):
        
        def setTorrentPath(path=None):
            path = os.path.abspath(torrent.get('torrent_path', '.'))
            return dump(path)
            
        self.torrents.Modify(self.torrents_table,
                        conditions={'id':ExactCond(dump(torrent_id))},
                        mappings={'last_seen':setTime, 'torrent_path':setTorrentPath})
        
    def removeTorrent(self, torrent_id):
        pass
    

class PreferenceDB:
    """ Peer cache * Torrent files """
    
    __single = None
    
    def __init__(self):
        if PreferenceDB.__single:
            raise RuntimeError, "PreferenceDB is singleton"
        self.db_name = 'peer_torrent'
        self._data = open_db(self.db_name)    # dbshelve object
        PreferenceDB.__single = self 
        self.preferences_columns = ['peer_id', 'torrent_id', 'created_time']
        self.db_name = 'preferences.bsd'
        self.preferences = open_db(self.db_name)    # dbshelve object
        self.peers = PeerDB.getInstance()    # peers : torrents : preferences = 1 : 1 : 1
        self.torrents = TorrentDB.getInstance()
                
    def getInstance(*args, **kw):
        if PreferenceDB.__single is None:
            PreferenceDB(*args, **kw)
        return PreferenceDB.__single
    getInstance = staticmethod(getInstance)

    def __del__(self):
        self._sync()

    def _sync(self):
        self._data.sync()
 
    def close(self):
        self._data.close()
        
    def createDB(self, db_dir=None):
        try:
            self.preferences.CreateTable(self.preferences_table, self.preferences_columns)
        except TableDBError:
            pass
        
    def getRecords(self):
        records = self.preferences.Select(self.preferences_table, self.preferences_columns, 
                                          {self.preferences_columns[0]:Cond()})
        for record in records:
            loadRecord(record)    # restore the original data type
        return records

    def printRecords(self):
        records = self.getRecords()
        print "========== all records in preferences table=============", len(records)
        for record in records:
            print record
                    
    def addPreference(self, peer_id, torrent_hash):
        torrents = self.torrents.findTorrent(torrent_hash=torrent_hash)    # find torrent_id by torrent_hash
        if not torrents:
            torrent = {'torrent_hash':torrent_hash}
            torrent_id = self.torrents.addTorrent(torrent)
        else:
            torrent = torrents[0]
            torrent_id= torrent['id']
        records = self.findPreference(peer_id, torrent_id)
        if not records:
            record = {'peer_id':peer_id, 'torrent_id':torrent_id, 'created_time':int(time())}
            dumpRecord(record)
            self.preferences.Insert(self.preferences_table, record)
                    
    def removePreference(self, peer_id=None, torrent_id=None):
        """ delete a record if both peer_id and torrent_id are matched;
        otherwise delete all matched records if peer_id is given;
        otherwise delete all matched records if torrent_id is given;
        """
        
        if peer_id and torrent_id:
            self.preferences.Delete(self.preferences_table, 
                                    {'peer_id':ExactCond(dump(peer_id)), 
                                     'torrent_id':ExactCond(dump(peer_id))})
        elif peer_id:
            self.preferences.Delete(self.preferences_table, 
                                    {'peer_id':ExactCond(dump(peer_id))})
        elif torrent_id:
            self.preferences.Delete(self.preferences_table, 
                                    {'torrent_id':ExactCond(dump(torrent_id))})
        
    def findPreference(self, peer_id=None, torrent_id=None):
        """ search records according to its peer_id or torrent_id in the database """
        
        if peer_id and torrent_id:
            res = self.preferences.Select(self.preferences_table, self.preferences_columns, 
                              conditions = {'peer_id':ExactCond(dump(peer_id)),
                                            'torrent_id':ExactCond(dump(torrent_id))})
        elif peer_id:
            res = self.preferences.Select(self.preferences_table, self.preferences_columns, 
                              conditions = {'peer_id':ExactCond(dump(peer_id))})
        elif torrent_id:
            res = self.preferences.Select(self.preferences_table, self.preferences_columns, 
                              conditions = {'torrent_id':ExactCond(dump(torrent_id))})
        else:
            res = []
        for item in res:
            loadRecord(item)
        return res   
    
class MyPreferenceDB: 
    pass

class OwnerDB:
    pass
        

    