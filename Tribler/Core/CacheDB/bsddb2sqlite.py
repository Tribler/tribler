import sys
import os
from bsdcachedb import MyDB, PeerDB, TorrentDB, PreferenceDB, MyPreferenceDB, BarterCastDB
from copy import deepcopy
from time import time
from sets import Set
from sha import sha
from base64 import encodestring, decodestring

from Tribler.Core.BitTornado.bencode import bdecode

LIB=0
# 0:  pysqlite, 1: APSW
if LIB == 0:
    try:
        import sqlite
    except:
        try:
            from pysqlite2 import dbapi2 as sqlite
        except:
            from sqlite3 import dbapi2 as sqlite
elif LIB == 1:    
    try:
        import apsw
    except:
        pass

print "SQLite Wrapper:", {0:'PySQLite', 1:'APSW'}[LIB]

def bin2str(bin):
    # Full BASE64-encoded 
#    if bin.replace('+','').replace('/','').replace('=','').isalnum():
#        return bin    # it is already BASE64-encoded
#    else:
        return encodestring(bin).replace("\n","")
    
def str2bin(str):
    try:
        return decodestring(str)
    except:
        return str    # has been decoded


class Bsddb2Sqlite:
    def __init__(self, bsddb_dir, sqlite_dbfile_path, sql_filename):
        self.bsddb_dir = bsddb_dir
        self.sqlite_dbfile_path = sqlite_dbfile_path
        self.sql_filename = sql_filename
        self.sdb = None
        self.commit_begined = 0
        self.permid_id = {}
        self.progress = {}
        self.infohash_id = {}
        self.permid_id = {}
        self.src_table = {'':0, 'BC':1}
        self.icons = Set()
        self.icon_dir = None

    def __del__(self):
        try:
            self._commit()
            self.close()
        except:
            pass
        
    def close(self):
        if self.sdb is not None:
            self.sdb.close()
        
    def _fetchone(self, sql, arg=None):
        find = None
        if LIB==0:
            if arg is None:
                self.cur.execute(sql)
            else:
                self.cur.execute(sql, arg)
            find = self.cur.fetchone()
        else:
            if arg is None:
                for find in self.cur.execute(sql):
                    break
            else:
                for find in self.cur.execute(sql, arg):
                    break
        if find is None:
            return None
        else:
            if len(find)>1:
                return find
            else:
                return find[0]
        
    def _getPeerID(self, peer_permid, bin=True):
        if peer_permid in self.permid_id:
            return self.permid_id[peer_permid]
        if bin:
            peer_permid_str = bin2str(peer_permid)
        else:
            peer_permid_str = peer_permid
        sql_get_peer_id = "SELECT peer_id FROM Peer WHERE permid==?"
        peer_id = self._fetchone(sql_get_peer_id, (peer_permid_str,))
        if peer_id is not None:
            self.permid_id[peer_permid] = peer_id
        
        return peer_id
    
    def _getTorrentID(self, infohash, bin=True):
        if bin:
            infohash = bin2str(infohash)
        sql_get_torrent_id = "SELECT torrent_id FROM Torrent WHERE infohash==?"
        arg = (infohash,)
        return self._fetchone(sql_get_torrent_id, arg)
        
#===============================================================================
#    def _insertInfohash(self, infohash, bin=True):
#        if bin:
#            infohash = bin2str(infohash)
#        sql_insert_torrent = "INSERT INTO Infohash (infohash) VALUES (?)"
#        self.cur.execute(sql_insert_torrent, (infohash,))
#===============================================================================
    
    def _begin(self):
        if LIB == 1:
            self.commit_begined = 1
            self.cur.execute('BEGIN')

    def _commit(self):
        if LIB == 0:
            if self.sdb:
                self.sdb.commit()
        else:
            if self.commit_begined == 1:
                if self.cur:
                    self.cur.execute("COMMIT")
                    self.commit_begined = 0
        
    def convert_PeerDB(self, limit=0):
        print >>sys.stderr, "convert_PeerDB"
        peer_db = PeerDB.getInstance(self.bsddb_dir)
        npeers = 0
        for permid,db_data in peer_db._data.iteritems():
            data = {
            'ip':None,
            'port':None,
            'name':None,
            'last_seen':0,
            'similarity':0,
            'connected_times':0,
            'oversion':0,   # overlay version
            'buddycast_times':0,
            'last_buddycast_time':0,
            'thumbnail':None,
            'npeers':0,
            'ntorrents':0,
            'nprefs':0,
            'nqueries':0,
            'last_connected':0,
            'friend':0,
            'superpeer':0,
            }   
            data.update(db_data)
            iconfilename = sha(permid).hexdigest()
            if iconfilename in self.icons:
                icon_str = self.readIcon(iconfilename)
                data['thumbnail'] = icon_str
            self._addPeerToDB(permid, data)
            npeers += 1
            self.permid_id[permid] = npeers
            if limit and npeers >= limit:
                break
        #nconnpeers = self._fetchone('select count(*) from Peer where connected_times>0;')
        #print "npeers", npeers, nconnpeers
            
        self._commit()
        # delete peer icons
        for iconfilename in self.icons:
            icon_path = os.path.join(self.icon_dir, iconfilename + '.jpg')
            if os.path.isfile(icon_path):
                print >> sys.stderr, 'remove', icon_path
                os.remove(icon_path)
        
    def readIcon(self, iconfilename):
        # read a peer icon file and return the encoded string
        icon_path = os.path.join(self.icon_dir, iconfilename + '.jpg')
        data = None
        try:
            try:
                f = open(icon_path, 'rb')
                data = f.read()
                data = encodestring(data).replace("\n","")
            except:
                data = None
        finally:
            f.close()
        return data
        
    def _addPeerToDB(self, permid, data=None, bin=True):
        sql_insert_peer = """
        INSERT INTO Peer 
        (permid, name, ip, port, thumbnail,
         oversion, similarity, friend, superpeer,       
         last_seen, last_connected, last_buddycast,  
         connected_times, buddycast_times, 
         num_peers, num_torrents, num_prefs, num_queries     
        ) 
        VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?, ?,?,?,?)
        """
        if bin:
            permid = bin2str(permid)
        if data is None:
            sql_insert_peer = 'INSERT INTO Peer (permid) VALUES (?)'
            self.cur.execute(sql_insert_peer,(permid,))
        else:
            self.cur.execute(sql_insert_peer,
                 (permid, data['name'], data['ip'], data['port'], data['thumbnail'],
                  data['oversion'], data['similarity'], data['friend'], data['superpeer'],
                  data['last_seen'],  data['last_connected'], data['last_buddycast_time'],
                  data['connected_times'], data['buddycast_times'],
                  data['npeers'], data['ntorrents'], data['nprefs'], data['nqueries'])
         )

    def convert_torrent_data(self, db_data):
        data = {
            'torrent_name':None,   # name of the torrent
            'leecher': -1,
            'seeder': -1,
            'ignore_number': 0,
            'retry_number': 0,
            'last_check_time': 0,
            'status': 0,    # status table: unknown, good, dead
            
            'category': 0,    # category table
            'source': 0,    # source table, from buddycast, rss or others
            'thumbnail':None,    # 1 - the torrent has a thumbnail
            'relevance':0,
            
            'inserttime': 0, # when the torrent file is written to the disk
            'progress': 0.0,    # download progress
            'secret':0, # download secretly
            
            'name':None,
            'length':0,
            'creation_date':0,
            'comment':None,
            'num_files':0,
            
            'ignore_number':0,
            'retry_number':0,
            'last_check_time':0,
        }
        
        if 'info' in db_data:
            info = db_data.pop('info')
            data['name'] = info.get('name', None)
            data['length'] = info.get('length', 0)
            data['num_files'] = info.get('num_files', 0)
            data['creation_date'] = info.get('creation date', 0)
            data['announce'] = info.get('announce', '')
            data['announce-list'] = info.get('announce-list', [])
            
        # change torrent dir
        torrent_dir = db_data.get('torrent_dir',None)
            
        # change status
        status = db_data.get('status', 'unknown')
        status_table = {'unknown':0, 'good':1, 'dead':2}
        db_data['status'] = status_table[status]
        
        # change category
        category_list = db_data.get('category', [])
        category_table = {'Picture':6, 'Document':5, 'xxx':7, 'VideoClips':2, 'other':8, 'Video':1, 'Compressed':4, 'Audio':3}
        if len(category_list) > 0:
            category = category_list[0]
            cat_int = category_table[category]
        else:
            cat_int = 0
        db_data['category'] = cat_int
        
        # change source
        src = db_data.get('source', '')
        if src in self.src_table:
            src_int = self.src_table[src]
        else:
            src_int = self.insertNewSrc(src)    # add a new src, e.g., a RSS feed
            self.src_table[src] = src_int
        db_data['source'] = src_int
        data.update(db_data)
        return data            

    def convert_TorrentDB(self, limit=0):
        print >>sys.stderr, "convert_TorrentDB"
        torrent_db = TorrentDB.getInstance(self.bsddb_dir)
        ntorrents = 0
        
        for infohash, db_data in torrent_db._data.iteritems():
            data = self.convert_torrent_data(db_data)
            self._addTorrentToDB(infohash, data)
            ntorrents += 1
            if limit and ntorrents >= limit:
                break
            
        self._commit()
        #self.cur.execute('select count(*) from torrent')
        #print 'add torrents', self.cur.fetchone()[0]
        #print "ntorrents", ntorrents
            
    def insertNewSrc(self, src):
        insert_src_sql = """
        INSERT INTO TorrentSource (name, description)
        VALUES (?,?)
        """
        desc = ''
        if src.startswith('http') and src.endswith('xml'):
            desc = 'RSS'
        self.cur.execute(insert_src_sql, (src,desc))
        get_src_id_sql = """
        SELECT source_id FROM TorrentSource WHERE name=?
        """
        src_id = self._fetchone(get_src_id_sql, (src,))
        assert src_id>1, src_id
        return src_id
        
    def _addTorrentToDB(self, infohash, data=None):
#        self._insertInfohash(infohash)
#        torrent_id = self._getTorrentID(infohash)
        infohash_str = bin2str(infohash)
        if not data:
            sql_insert_torrent = "INSERT INTO Torrent (infohash) VALUES (?)"
            self.cur.execute(sql_insert_torrent, (infohash_str,))
        else:
            if data['progress'] > 0:
                self.progress[infohash] = data['progress']

            sql_insert_torrent = """
            INSERT INTO Torrent 
            (infohash, name, torrent_file_name,
            length, creation_date, num_files, thumbnail,
            insert_time, secret, relevance,
            source_id, category_id, status_id,
            num_seeders, num_leechers, comment) 
            VALUES (?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?)
            """
            try:
                self.cur.execute(sql_insert_torrent,
                 (infohash_str, data['name'], data['torrent_name'], 
                  data['length'], data['creation_date'], data['num_files'], data['thumbnail'], 
                  data['inserttime'], data['secret'], data['relevance'],
                  data['source'], data['category'], data['status'], 
                  data['seeder'], data['leecher'], data['comment'])
                 )
            except Exception, msg:
                print >> sys.stderr, "error input for _addTorrentToDB:", data, Exception, msg
                #sys.exit(1)
            
        torrent_id = self._getTorrentID(infohash_str, False)
        self.infohash_id[infohash] = torrent_id
        if data:
            self.addTorrentTracker(torrent_id, data)
            
        return torrent_id

    def addTorrentTracker(self, torrent_id, data):
        announce = data['announce']
        ignore_number = data['ignore_number']
        retry_number = data['retry_number']
        last_check_time = data['last_check_time']
        
        announce_list = data['announce-list']
        
        sql_insert_torrent_tracker = """
        INSERT INTO TorrentTracker
        (torrent_id, tracker, announce_tier, 
        ignored_times, retried_times, last_check)
        VALUES (?,?,?, ?,?,?)
        """
        
        values = [(torrent_id, announce, 1, ignore_number, retry_number, last_check_time)]
        tier_num = 2
        trackers = {announce:None}
        for tier in announce_list:
            for tracker in tier:
                if tracker in trackers:
                    continue
                value = (torrent_id, tracker, tier_num, 0, 0, 0)
                values.append(value)
                trackers[tracker] = None
            tier_num += 1
        try:
            self.cur.executemany(sql_insert_torrent_tracker, values)
        except Exception, msg:
            print >> sys.stderr, "error input for addTorrentTracker", data, values, Exception, msg
        

    def convert_PreferenceDB(self):
        print >>sys.stderr, "convert_PreferenceDB"
        #print len(self.permid_id), len(self.infohash_id)
        pref_db = PreferenceDB.getInstance(self.bsddb_dir)
        nprefs = 0
        npeers = 0
        for permid,prefs in pref_db._data.iteritems():
            if not prefs:
                continue
            if permid in self.permid_id:
                pid = self.permid_id[permid]
            else:
                continue
            for infohash in prefs:
                if infohash not in self.infohash_id:
                    self._addTorrentToDB(infohash)
                    tid = self._getTorrentID(infohash)
                    self.infohash_id[infohash] = tid
                else:
                    tid = self.infohash_id[infohash]
                self._addPeerPreference(pid, tid)
                nprefs += 1
            npeers += 1
        self._commit()
        #print "nprefs", nprefs, "npeers", npeers
                
    def _addPeerPreference(self, peer_id, torrent_id):
        sql_insert_peer_torrent = "INSERT INTO Preference (peer_id, torrent_id) VALUES (?,?)"
        try:
            self.cur.execute(sql_insert_peer_torrent, (peer_id, torrent_id))
        except sqlite.IntegrityError, msg:    # duplicated
            #print Exception, msg
            pass

    def convert_MyPreferenceDB(self):
        print >>sys.stderr, "convert_MyPreferenceDB"
        
        mypref_db = MyPreferenceDB.getInstance(self.bsddb_dir)
        nprefs = 0
        """ CREATE TABLE MyPreference (torrent_id INTEGER PRIMARY KEY, 
        download_name TEXT NOT NULL, download_dir TEXT NOT NULL, 
        progress NUMERIC DEFAULT 0, creation_time INTEGER NOT NULL, 
        rank INTEGER, last_access NUMERIC NOT NULL);"""
        sql =  """
                 insert into MyPreference (torrent_id, destination_path, progress, creation_time)
                                   values (?,?,?,?)
               """
        
        for infohash, data in mypref_db._data.iteritems():
            torrent_id = self._getTorrentID(infohash)
            if not torrent_id:    # not found in torrent db, insert it to torrent db first
                torrent_id = self._addTorrentToDB(infohash)
            download_name = data.get('content_name', '')
            download_dir = data.get('content_dir', '')
            dest_path = os.path.join(download_dir, download_name)
            creation_time = data.get('created_time', 0)
            prog = self.progress.get(infohash, 0)    
            self.cur.execute(sql, (torrent_id, dest_path, prog, creation_time)
            )
        #self.cur.execute('select count(*) from MyPreference')
        #print 'add MyPreferenceDB', self.cur.fetchone()[0]
        
    def addFriend(self, permid):
        peer_id = self._getPeerID(permid)
        if not peer_id:
            self._addPeerToDB(permid)
            peer_id = self._getPeerID(permid)
        sql = 'update Peer set friend=1 where peer_id=%d'%peer_id
        self.cur.execute(sql)
        
    def addSuperPeer(self, permid):
        peer_id = self._getPeerID(permid)
        if not peer_id:
            self._addPeerToDB(permid)
            peer_id = self._getPeerID(permid)
        sql = 'update Peer set superpeer=1 where peer_id=%d'%peer_id
        self.cur.execute(sql)
        
    def convert_MyDB(self, torrent_dir=None):
        print >>sys.stderr, "convert MyDB to MyInfo"
        
        mydb = MyDB.getInstance(self.bsddb_dir)

        desired_keys = ['permid', 'ip', 'port', 'name']#, 'version', 'torrent_path'] according to Jelle's plan, all these keys will not be included in db
        for key in desired_keys:
            value = mydb._data[key]
#            if key == 'permid' and value:
#                value = bin2str(value)
            self.cur.execute("insert into MyInfo (entry,value) values (?,?)", (key,value))
            
        if torrent_dir is not None:
            sql = "insert into MyInfo (entry,value) values ('torrent_dir', ?)"
            self.cur.execute(sql, (torrent_dir,))
            
        friends = mydb.getFriends()
        for permid in friends:
            self.addFriend(permid)
        
        superpeers = mydb.getSuperPeers()
        for permid in superpeers:
            self.addSuperPeer(permid)
            
        self._commit()
        
        #self.cur.execute('select count(*) from peer where friend==1')
        #print 'add friends', self.cur.fetchone()[0]
        #self.cur.execute('select count(*) from peer where superpeer==1')
        #print 'add superpeers', self.cur.fetchone()[0]

    def create_sqlite(self, file_path, sql_file, autocommit=0):
        if os.path.exists(file_path):
            print >>sys.stderr, "sqlite db already exists", os.path.abspath(file_path)
            return False
        db_dir = os.path.dirname(os.path.abspath(file_path))
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        self.sdb = sqlite.connect(file_path, isolation_level=None)    # auto-commit
        self.cur = self.sdb.cursor()
        
        f = open(sql_file)
        sql_create_tables = f.read()
        f.close()
        
        sql_statements = sql_create_tables.split(';')
        for sql in sql_statements:
            self.cur.execute(sql)
        
        self._commit()
        self.sdb.close()
        
        self.sdb = sqlite.connect(file_path)    # auto-commit
        self.cur = self.sdb.cursor()
        
        return True
    
    def convert_BartercastDB(self):
        print >>sys.stderr, "convert_BartercastDB"
        
        db_path = os.path.join(self.bsddb_dir, 'bartercast.bsd')
        if not os.path.isfile(db_path):
            return
        bc_db = BarterCastDB.getInstance(self.bsddb_dir)
        insert_bc_sql = """
        INSERT INTO BarterCast
        (peer_id_from, peer_id_to, downloaded, uploaded, last_seen, value)
        VALUES (?,?,?,?,?,?)
        """
        values = []
        for key,db_data in bc_db._data.iteritems():
            try:
                permid_from, permid_to = bdecode(key)
                permid_id_from = self._getPeerID(permid_from)
                if permid_id_from is None:
                    self._addPeerToDB(permid_from)
                    permid_id_from = self._getPeerID(permid_from)
                permid_id_to = self._getPeerID(permid_to)
                if permid_id_to is None:
                    self._addPeerToDB(permid_to)
                    permid_id_to = self._getPeerID(permid_to)
                downloaded = db_data.get('downloaded', 0)
                uploaded = db_data.get('uploaded', 0)
                last_seen = db_data.get('last_seen', 0)
                value = db_data.get('value', 0)
                values.append((permid_id_from, permid_id_to, downloaded, uploaded, last_seen, value))
            except Exception, msg:
                print >> sys.stderr, "error input for convert_BartercastDB:", key, db_data, Exception, msg
        self.cur.executemany(insert_bc_sql, values)
        self._commit()
        #print "converted bartercast db", len(values)

    def scan_PeerIcons(self, icon_dir):
        print >>sys.stderr, "scan_PeerIcons", icon_dir
        if not icon_dir or not os.path.isdir(icon_dir):
            return
        self.icon_dir = icon_dir
        for file_name in os.listdir(icon_dir):
            if file_name.endswith('.jpg') and len(file_name)==44:
                self.icons.add(file_name[:-4])
    
    def run(self, peer_limit=0, torrent_limit=0, torrent_dir=None, icon_dir=None):
        if self.create_sqlite(self.sqlite_dbfile_path, self.sql_filename):
            self.scan_PeerIcons(icon_dir)
            
            MyDB.getInstance(None, self.bsddb_dir)
            self.convert_PeerDB(peer_limit)
            #self.convert_MyDB(torrent_dir)    # should not be called
            self.convert_BartercastDB()

            self.convert_TorrentDB(torrent_limit)
            self.convert_MyPreferenceDB()
            self.convert_PreferenceDB()
            
            self.sdb.close()
            #self.remove_bsddb()
            
            return True
        else:
            if self.sdb:
                self.sdb.close()
            return False
        
    def remove_bsddb(self):
        print >> sys.stderr, self.bsddb_dir
        for filename in os.listdir(self.bsddb_dir):
            if filename.endswith('.bsd'):
                db_path = os.path.abspath(os.path.join(self.bsddb_dir,filename))
                if os.path.isfile(db_path):
                    print >> sys.stderr, "delete", db_path
                    os.remove(db_path)
            

if __name__ == '__main__':
    bsddb_dir = sys.argv[1]
    bsddb2sqlite = Bsddb2Sqlite(bsddb_dir, 'tribler.sdb', '../../tribler_sdb_v1.sql')
    start = time()
    peer_limit = torrent_limit = 0
    if len(sys.argv)>2:
        peer_limit = int(sys.argv[2])
    if len(sys.argv)>3:
        torrent_limit = int(sys.argv[3])
    print "limit", peer_limit, torrent_limit
    bsddb2sqlite.run(peer_limit, torrent_limit)
    print "cost time", time()-start
    
    
    