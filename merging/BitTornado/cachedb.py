
import os
from time import time, ctime

try:
    import cPickle
    pickle = cPickle
except ImportError:
    import pickle
try:
    # For Python 2.3
    from bsddb.dbtables import bsdTableDB, TableDBError, Cond, ExactCond, LikeCond
except ImportError:
    # For earlier Pythons w/distutils pybsddb
    from bsddb3.dbtables import bsdTableDB, TableDBError, Cond, ExactCond, LikeCond

from ConfigDir import ConfigDir

db_name = 'btcache.db'

def setDBPath(db_dir = None):
    if not db_dir:
        config_dir = ConfigDir()
        dir_root = config_dir.dir_root
        db_dir = os.path.join(dir_root, 'bsddb')
    
    if not os.access(db_dir, os.F_OK):
        try: 
            os.mkdir(db_dir)
        except os.error:
            config_dir = ConfigDir()
            db_dir = config_dir.dir_root
    return db_dir

home_dir = setDBPath('./bsddb')

def dump(value):
    return pickle.dumps(value, 1)

def load(value):
    return pickle.loads(value)

def dumpRecord(record):
    """ transfer all elements in a record into string data type """
    
    if not isinstance(record, dict):
        return
    for key in record.keys():
        value = record[key]
        record[key] = dump(value)

def string(item):
    for key in item.keys():
        if not isinstance(item[key], str):
            item[key] = str(item[key])        
        
def loadRecord(record):
    """ restore all elements in a record from string data type """
    
    if not isinstance(record, dict):
        return
    for key in record.keys():
        value = record[key]
        if value is not None:
            record[key] = load(value)

def dropTables(tables = None, tdb_name = db_name):
    """ drop tables in database """
    
    tdb = bsdTableDB(filename=tdb_name, dbhome=home_dir, create=1)
    if tables is None:
        tables = tdb.ListTables()
    print "Warn: drop Tables:", tables
    for table in tables:
        tdb.Drop(table)

def setTime(new_time):
    return dump(int(time()))

def friendly_time(old_time):
    curr_time = time()
    diff = int(curr_time - old_time)
    if diff < 1:
        return str(diff) + " sec. ago"
    elif diff < 60:
        return str(diff) + " secs. ago"
    elif diff < 120:
        return "1 min. ago"
    elif diff < 3600:
        return str(int(diff/60)) + " mins. ago"
    elif diff < 7200:
        return "1 hour ago"
    elif diff < 86400:
        return str(int(diff/3600)) + " hours ago"
    elif diff < 172800:
        return "Yesterday"
    elif diff < 259200:
        return str(int(diff/86400)) + " days ago"
    else:
        return ctime(old_time)

class CacheDB:
    """ Singleton Cache BSDDB """
    
    __single = None
    
    def __init__(self):
        if CacheDB.__single:
            raise RuntimeError, "CacheDB is singleton"
        CacheDB.__single = self 
        self.db = bsdTableDB(filename=db_name, dbhome=home_dir, create=1)
                
    def getInstance(*args, **kw):
        if CacheDB.__single is None:
            CacheDB(*args, **kw)
        return CacheDB.__single
    getInstance = staticmethod(getInstance)

class SuperPeerTable:
    
    __single = None
    
    def __init__(self):
        if SuperPeerTable.__single:
            raise RuntimeError, "SuperPeerTable is singleton"
        SuperPeerTable.__single = self 
        self.superpeers_table = 'superpeers'    # BSDDB Table name
        self.superpeers_columns = ['id']
        self.superpeers = CacheDB.getInstance().db    # BSD DB object
        self.peers = PeerTable.getInstance()
        self.createDB()
        
    def getInstance(*args, **kw):
        if SuperPeerTable.__single is None:
            SuperPeerTable(*args, **kw)
        return SuperPeerTable.__single
    getInstance = staticmethod(getInstance)
        
    def createDB(self, db_dir=None):
        """ create bsddb table if it doesn't exist """
        
        try:
            self.superpeers.CreateTable(self.superpeers_table, self.superpeers_columns)
        except TableDBError:
            pass        
            
    def getRecords(self):
        """ list all contents in the peers table """
        records = self.superpeers.Select(self.superpeers_table, 
                                         self.superpeers_columns, 
                                         {self.superpeers_columns[0]:Cond()})
        for record in records:
            loadRecord(record)    # restore the original data type
        return records
        
    def getSuperPeers(self):
        records = self.getRecords()
        superpeers = []
        for record in records:
            peer = self.peers.getPeer(record['id'])
            if peer:
                superpeers.append(peer)
        return superpeers
    
    def addSuperPeerByID(self, id):
        records = self.peers.findPeer(id=id)    # check if this id exists in peer table
        if not records:
            return
        if self.findSuperPeer(id):    # check if this id is already in superpeer table
            return
        record = {}
        record['id'] = id
        dumpRecord(record)
        self.superpeers.Insert(self.superpeers_table, record)

    def addSuperPeerByPeer(self, peer, friend=0, update_time=False):
        id = self.peers.addPeer(peer, friend, update_time)
        self.addSuperPeerByID(id)
    
    def findSuperPeer(self, id):
        res = self.superpeers.Select(self.superpeers_table, self.superpeers_columns, 
                               conditions = {'id':ExactCond(dump(id))})
        return res
        
    def printRecords(self):
        records = self.getRecords()
        print "========== all records in superpeer table=============", len(records)
        for record in records:
            print record

class PeerTable:
    """ List of Peers, e.g. Host Cache """
    
    __single = None
    
    def __init__(self):
        if PeerTable.__single:
            raise RuntimeError, "PeerTable is singleton"
        PeerTable.__single = self 
        self.peers_table = 'peers'    # BSDDB Table name
        self.peers_columns = ['id', 'ip', 'port', 'permid', 'created_time', 'last_seen', 
                              'name', 'friend', 'my_trust', 'sys_trust', 'similarity']
        self.peers = CacheDB.getInstance().db    # BSD DB object
        self.torrents = TorrentTable.getInstance()    # peers:torrents:preferences = 1 : 1 : 1
        self.preferences = PreferenceTable.getInstance()
        self.createDB()    # create or bind to the DB
        
        
    def getInstance(*args, **kw):
        if PeerTable.__single is None:
            PeerTable(*args, **kw)
        return PeerTable.__single
    getInstance = staticmethod(getInstance)
        
    def createDB(self, db_dir=None):
        """ create bsddb table if it doesn't exist """
        
        try:
            self.peers.CreateTable(self.peers_table, self.peers_columns)
        except TableDBError:
            pass        
            
    def getRecords(self):
        """ list all contents in the peers table """
        records = self.peers.Select(self.peers_table, self.peers_columns, {self.peers_columns[0]:Cond()})
        for record in records:
            loadRecord(record)    # restore the original data type
        return records
    
    def printRecords(self):
        records = self.getRecords()
        print "========== all records in peer table=============", len(records)
        for record in records:
            print record
                
    def getMaxID(self):
        max_id = 0
        ids = self.peers.Select(self.peers_table, ['id'], {'id':Cond()})
        for id in ids:
            loadRecord(id)
            if id['id'] >= max_id:
                max_id = int(id['id'])
        return max_id
        
    def addPeer(self, peer, friend=0, update_time=True):
        """ add a peer is it doesn't exist; otherwise update the status of this peer """
        
        if not peer.has_key('permid'):
            peer['permid'] = None
        if not peer.has_key('port'):
            peer['port'] = 0
        if not peer.has_key('ip'):
            peer['ip'] = 'unknown'
        
        records = self.findPeer(peer['permid'])
        if not records:
            current = int(time())
            self.curr_id = self.getMaxID() + 1    # preferably lock/unlock these operations
            if not peer.has_key('name') or not peer['name']:
                name = 'Peer ' + str(self.curr_id)
            else:
                name = peer['name']
            record = {'id':self.curr_id, 'name':name, 'ip':peer['ip'], 'port':peer['port'], 
                      'created_time':current, 'last_seen':current, 'friend':friend,
                      'permid':peer['permid'], 'my_trust':5, 'sys_trust':5, 'similarity':0}
            dumpRecord(record)
            self.peers.Insert(self.peers_table, record)
        else:
            record = records[0]
            self.curr_id = record['id']
            self.updatePeer(self.curr_id, record['ip'], record['port'], update_time)
        if peer.has_key('torrent_hash') and peer['torrent_hash']:
            self.preferences.addPreference(self.curr_id, peer['torrent_hash'])
        return self.curr_id
        
    def addFriend(self, peer_id):
        self.peers.Modify(self.peers_table,
                        conditions={'id':ExactCond(dump(peer_id))},
                        mappings={'friend':lambda x:dump(1)})
        #TODO: update friend layer
                        
    def removeFriend(self, peer_id):
        self.peers.Modify(self.peers_table,
                        conditions={'id':ExactCond(dump(peer_id))},
                        mappings={'friend':lambda x:dump(0)})
        #TODO: update friend layer
                        
    def updatePeer(self, id, ip, port, update_time):
        # if port is 0, the connection is not locally initiated. 
        # Assume normally port will not change even ip changed
        
        if update_time:
            if port:
                self.peers.Modify(self.peers_table,
                                  conditions={'id':ExactCond(dump(id))},
                                  mappings={'last_seen':setTime, 
                                            'ip':lambda x:dump(ip),
                                            'port':lambda x:dump(port)})
            else:
                self.peers.Modify(self.peers_table,
                                  conditions={'id':ExactCond(dump(id))},
                                  mappings={'last_seen':setTime, 
                                            'ip':lambda x:dump(ip)})
        else:
            if port:
                self.peers.Modify(self.peers_table,
                                  conditions={'id':ExactCond(dump(id))},
                                  mappings={'ip':lambda x:dump(ip),
                                            'port':lambda x:dump(port)})
            else:
                self.peers.Modify(self.peers_table,
                                  conditions={'id':ExactCond(dump(id))},
                                  mappings={'ip':lambda x:dump(ip)})
                                        
    def updatePeerTrust(self, peer_id, trust):
        self.peers.Modify(self.peers_table,
                        conditions={'id':ExactCond(dump(peer_id))},
                        mappings={'my_trust':lambda x:dump(trust)})

    def removePeer(self, id=None, permid=None, ip=None):
        """ delete a matched record if id is not None;
        otherwise delete a matched record if permid is not None;
        otherwise delete a matched record if ip is not None;
        """
        
        if id is not None:
            self.peers.Delete(self.peers_table, {'id':ExactCond(dump(id))})
            self.preferences.removePreference(peer_id=id)    # also remove related preferences
        elif permid is not None:
            records = self.findPeer(permid)
            id = records[0]['id']
            self.peers.Delete(self.peers_table, {'permid':ExactCond(dump(permid))})
            self.preferences.removePreference(peer_id=id)
        elif ip is not None:
            records = self.findPeer(ip=ip)
            for record in records:
                id = record['id']
                self.preferences.removePreference(peer_id=id)
            self.peers.Delete(self.peers_table, {'ip':ExactCond(dump(ip))})
        
    def getPeer(self, id):
        peer = self.peers.Select(self.peers_table, self.peers_columns, 
                           conditions = {'id':ExactCond(dump(id))})
        if not peer:
            return None
        loadRecord(peer[0])
        return peer[0]
                              
    def findPeer(self, permid=None, ip=None, id=None):    # find both id and hash
        """ search a record according to its peer_id or ip in the database """
        
        if id:
            res = self.peers.Select(self.peers_table, self.peers_columns, 
                              conditions = {'id':ExactCond(dump(id))})
        elif permid:
            res = self.peers.Select(self.peers_table, self.peers_columns, 
                              conditions = {'permid':ExactCond(dump(permid))})
        elif ip:
            res = self.peers.Select(self.peers_table, self.peers_columns, 
                              conditions = {'ip':ExactCond(dump(ip))})
        else:
            res = []
        for item in res:
            loadRecord(item)
        return res


class TorrentTable:
    """ Database table of torrent files, including my and my friends' torrents, 
    e.g. File cache 
    """
    
    __single = None
    
    def __init__(self):
        if TorrentTable.__single:
            raise RuntimeError, "TorrentTable is singleton"
        TorrentTable.__single = self 
        self.torrents_table= 'torrents'
        self.torrents_columns = ['id', 'torrent_hash', 'torrent_name', 'torrent_path', 
                                 'content_name', 'content_path', 'content_size',
                                 'num_files', 'others', 'created_time', 'last_seen',
                                 'my_rank', 'recommendation', 'have']
        self.peers = PeerTable.getInstance()
        self.torrents = CacheDB.getInstance().db
        self.preferences = PreferenceTable.getInstance()
        self.createDB()
                
    def getInstance(*args, **kw):
        if TorrentTable.__single is None:
            TorrentTable(*args, **kw)
        return TorrentTable.__single
    getInstance = staticmethod(getInstance)
        
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
            current = int(time())
            record = {'created_time':current, 'last_seen':current, 
                      'my_rank':0, 'recommendation':0, 'have':have}
            record.update(torrent)
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
    

class PreferenceTable:
    """ Peer cache * Torrent files """
    
    __single = None
    
    def __init__(self):
        if PreferenceTable.__single:
            raise RuntimeError, "PreferenceTable is singleton"
        PreferenceTable.__single = self 
        self.preferences_table= 'peer_torrent'
        self.preferences_columns = ['peer_id', 'torrent_id', 'created_time']
        self.peers = PeerTable.getInstance()
        self.torrents = TorrentTable.getInstance()
        self.preferences = CacheDB.getInstance().db
        self.createDB()
                
    def getInstance(*args, **kw):
        if PreferenceTable.__single is None:
            PreferenceTable(*args, **kw)
        return PreferenceTable.__single
    getInstance = staticmethod(getInstance)
    
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
            
    def findPrefByPermID(self, permid):
        """ find peer's preferences given permid """
        
        records = self.peers.findPeer(permid)
        if not records:
            return None
        peer_id = records[0]['id']
        return self.findPrefByID(peer_id)
                
    def findPrefByID(self, peer_id):
        preflist = self.findPreference(peer_id)
        torrlist = []
        for pref in preflist:
            torrentid = pref['torrent_id']
            torrent = self.torrents.findTorrent(torrent_id=torrentid)
            if torrent:
                torrent = torrent[0]
                torrlist.append(torrent)
        return torrlist
        
        