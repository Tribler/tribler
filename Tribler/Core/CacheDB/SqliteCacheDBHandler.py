# Written by Jie Yang
# see LICENSE.txt for license information
# Note for Developers: Please write testsuit in Tribler/Test/test_sqlitecachedbhandler.py 
# for any function you added to database. 
# Please reuse the functions in sqlitecachedb as more as possible

from sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, sqlite, NULL
from unicode import name2unicode,dunno2unicode
from copy import deepcopy
from sets import Set
from traceback import print_exc, print_stack
from threading import currentThread
from time import time
from sha import sha
import sys
import os
import socket
import threading
import base64

from bencode import bencode, bdecode
#from Notifier import Notifier

SHOW_ERROR = True

def show_permid_shorter(permid):
    if not permid:
        return 'None'
    s = encodestring(permid).replace("\n","")
    return s[-5:]


class BasicDBHandler:
    def __init__(self, table_name):
        self._db = SQLiteCacheDB.getInstance()
        self.table_name = table_name
        
    def __del__(self):
        try:
            self.sync()
        except:
            if SHOW_ERROR:
                print_exc()
        
    def close(self):
        try:
            self._db.close()
        except:
            if SHOW_ERROR:
                print_exc()
        
    def size(self):
        return self._db.size(self.table_name)

    def sync(self):
        self._db.commit()
        
    def commit(self):
        self._db.commit()
            
    def getOne(self, value_name, where=None, conj='and', **kw):
        return self._db.getOne(self.table_name, value_name, where, conj, **kw)
    
    def getAll(self, value_name, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, conj='and', **kw):
        return self._db.getAll(self.table_name, value_name, where, group_by, having, order_by, limit, offset, conj, **kw)
    
            
class MyDBHandler(BasicDBHandler):

    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if MyDBHandler.__single is None:
            MyDBHandler.lock.acquire()   
            try:
                if MyDBHandler.__single is None:
                    MyDBHandler(*args, **kw)
            finally:
                MyDBHandler.lock.release()
        return MyDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if MyDBHandler.__single is not None:
            raise RuntimeError, "MyDBHandler is singleton"
        MyDBHandler.__single = self
        BasicDBHandler.__init__(self, 'MyInfo')
        # keys: version, permid, ip, port, name, torrent_dir
        
    def get(self, key, default_value=None):
        value = self.getOne('value', entry=key)
        if value is not NULL:
            return value
        else:
            if default_value is not None:
                return default_value
            else:
                raise KeyError, key

    def put(self, key, value):
        try:
            self._db.insert(self.table_name, entry=key, value=value)
        except:
            where = "entry=" + repr(key)
            self._db.update(self.table_name, where, value=value)
        


class PeerViewHandler(BasicDBHandler):    
    def __init__(self, table_name, key_name):
        self.key_name = key_name
        BasicDBHandler.__init__(self, table_name)
        self.list = []    #TODO: not thread safe
        
    def getList(self, refresh=True):
        if not refresh and self.list:
            return self.list
        
        permids = self.getAll('permid')
        all = []
        for p in permids:
            all.append(str2bin(p[0]))
        self.list = all
        return self.list
        
    def setPeerStatus(self, permid=None, status=1, peer_id=None):
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
            
        if peer_id is not None:
            where = 'peer_id=%d'%peer_id
            self._db.update('Peer', where, **{self.key_name:status})
        else:
            print >> sys.stderr, self.__class__.__name__,": permid not in db", `permid`

    def addExternalPeer(self, peer, status=1, update=False):
        permid = peer.pop('permid')
        self._db.insertPeer(permid, update=update, **peer)
        self.setPeerStatus(permid, status)
        peer['permid'] = permid

class SuperPeerDBHandler(PeerViewHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if SuperPeerDBHandler.__single is None:
            SuperPeerDBHandler.lock.acquire()   
            try:
                if SuperPeerDBHandler.__single is None:
                    SuperPeerDBHandler(*args, **kw)
            finally:
                SuperPeerDBHandler.lock.release()
        return SuperPeerDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if SuperPeerDBHandler.__single is not None:
            raise RuntimeError, "SuperPeerDBHandler is singleton"
        SuperPeerDBHandler.__single = self
        PeerViewHandler.__init__(self, 'SuperPeer', 'superpeer')
        
    def loadSuperPeers(self, config, refresh=False):
        filename = os.path.join(config['install_dir'], config['superpeer_file'])
        superpeer_list = self.readSuperPeerList(filename)
        self.insertSuperPeers(superpeer_list, refresh)

    def readSuperPeerList(self, filename=''):
        """ read (name, permid, superpeer_ip, superpeer_port) lines from a text file """
        
        try:
            filepath = os.path.abspath(filename)
            file = open(filepath, "r")
        except IOError:
            print >> sys.stderr, "superpeer: cannot open superpeer file", filepath
            return []
            
        superpeers = file.readlines()
        file.close()
        superpeers_info = []
        for superpeer in superpeers:
            if superpeer.strip().startswith("#"):    # skip commended lines
                continue
            superpeer_line = superpeer.split(',')
            superpeer_info = [a.strip() for a in superpeer_line]
            try:
                superpeer_info[2] = base64.decodestring(superpeer_info[2]+'\n' )
            except:
                print_exc()
                continue
            try:
                ip = socket.gethostbyname(superpeer_info[0])
                superpeer = {'ip':ip, 'port':superpeer_info[1], 
                          'permid':superpeer_info[2]}
                if len(superpeer_info) > 3:
                    superpeer['name'] = superpeer_info[3]
                superpeers_info.append(superpeer)
            except:
                pass
                    
        return superpeers_info

    def insertSuperPeers(self, superpeer_list, refresh=False):
        for superpeer in superpeer_list:
            superpeer = deepcopy(superpeer)
            if not isinstance(superpeer, dict) or 'permid' not in superpeer:
                continue
            self.addExternalSuperPeer(superpeer, refresh)
        self.commit()
        
    def getSuperPeerList(self, refresh=False):
        return self.getList(refresh)
    
    def getSuperPeers(self, refresh=False):
        return self.getList(refresh)
        
    def addExternalSuperPeer(self, peer, refresh=False):
        permid = peer['permid']
        if not self.isSuperPeer(permid, refresh):
            self.addExternalPeer(peer, 1)
            self.list.append(permid)
            
    def isSuperPeer(self, permid, refresh=False):
        return permid in self.getSuperPeerList(refresh)

class FriendDBHandler(PeerViewHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if FriendDBHandler.__single is None:
            FriendDBHandler.lock.acquire()   
            try:
                if FriendDBHandler.__single is None:
                    FriendDBHandler(*args, **kw)
            finally:
                FriendDBHandler.lock.release()
        return FriendDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if FriendDBHandler.__single is not None:
            raise RuntimeError, "FriendDBHandler is singleton"
        FriendDBHandler.__single = self
        PeerViewHandler.__init__(self, 'Friend', 'friend')
        
    def getFriendList(self, refresh=False):
        return self.getList(refresh)
        
    def addExternalFriend(self, peer):
        self.addExternalPeer(peer, 1)

    def addFriend(self, permid):
        if not self.isFriend(permid):
            self.setPeerStatus(permid, 1)
            self.list.append(permid)

    def getFriends(self):
        """returns a list of peer infos including permid"""
        value_name = ('permid', 'ip', 'port', 'name')
        friends = []
        peers = self.getAll(value_name)
        for p in peers:
            peer = dict(zip(value_name, p))
            friends.append(peer)
        return friends
    
    def isFriend(self, permid):
        return permid in self.getFriendList()
            
    def deleteFriend(self,permid):
        if self.isFriend(permid):
            self.setPeerStatus(permid, 0)
            self.list.remove(permid)
        
class PeerDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if PeerDBHandler.__single is None:
            PeerDBHandler.lock.acquire()   
            try:
                if PeerDBHandler.__single is None:
                    PeerDBHandler(*args, **kw)
            finally:
                PeerDBHandler.lock.release()
        return PeerDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self, config=None):
        if PeerDBHandler.__single is not None:
            raise RuntimeError, "PeerDBHandler is singleton"
        PeerDBHandler.__single = self
        BasicDBHandler.__init__(self, 'Peer')
        
        #self.notifier = Notifier.getInstance()
        self.pref_db = PreferenceDBHandler.getInstance()

    def __len__(self):
        return self.size()

    def getPeerID(self, permid):
        return self._db.getPeerID()

    def getPeer(self, permid, keys=None):
        if keys is not None:
            res = self.getOne(keys, permid=bin2str(permid))
            return res
        else:
            # return a dictionary
            # make it compatible for calls to old bsddb interface
            # Jie TODO: ugly codes. should focus on single task. move these codes to modules
            value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs', 'num_queries', 
                      'connected_times', 'buddycast_times', 'last_connected', 'last_seen')
            key_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'npeers', 'ntorrents', 'nprefs', 'nqueries',
                      'connected_times', 'buddycast_times', 'last_connected', 'last_seen')
            
            item = self.getOne(value_name, permid=bin2str(permid))
            if not item:
                return None
            peer = dict(zip(key_name, item))
            peer['permid'] = str2bin(peer['permid'])
            return peer
        
    def getPeerSim(self, permid):
        permid_str = bin2str(permid)
        sim = self.getOne('similarity', permid=permid_str)
        if sim is None:
            sim = 0
        return sim
        
    def getPeerList(self):    # get the list of all peers' permid
        permid_strs = self.getAll('permid')
        return [str2bin(permid_str[0]) for permid_str in permid_strs]
        
    def getPeers(self, peer_list, keys):    # get a list of dictionaries given peer list
        value_names = ",".join(keys)
        sql = 'select %s from Peer where permid=?;'%value_names
        all = []
        for permid in peer_list:
            permid_str = bin2str(permid)
            p = self._db.fetchone(sql, (permid_str,))
            all.append(p)
        
        peers = []
        for i in range(len(all)):
            p = all[i]
            peer = dict(zip(keys,p))
            peer['permid'] = peer_list[i]
            peers.append(peer)
        
        return peers
    
    def addPeer(self, permid, value, update_dns=True, update_lastseen=True):
        # add or update a peer
        # ARNO: AAARGGH a method that silently changes the passed value param!!!
        
        #print >>sys.stderr,"sqldbhand: addPeer",`permid`,`value`
        
        _permid = _last_seen = _ip = _port = None
        if 'permid' in value:
            _permid = value.pop('permid')
            
        if 'last_seen' in value:
            if not update_lastseen :
                _last_seen = value.pop('last_seen')
            else:    # get the latest last_seen
                old_last_seen = self.getOne('last_seen', permid=bin2str(permid))
                last_seen = value['last_seen']
                now = int(time())
                value['last_seen'] = min(now, max(last_seen, old_last_seen))
            
        if not update_dns:
            if value.has_key('ip'):
                _ip = value.pop('ip')
            if value.has_key('port'):
                _port = value.pop('port')
            
        self._db.insertPeer(permid, **value)
        
        if _permid is not None:
            value['permid'] = permid
        if _permid is not None:
            value['last_seen'] = _last_seen
        if _permid is not None:
            value['ip'] = _ip
        if _permid is not None:
            value['port'] = _port
            
    def hasPeer(self, permid):
        return self._db.hasPeer(permid)

    def findPeers(self, key, value):    
        # only used by Connecter
        if key == 'permid':
            value = bin2str(value)
        res = self.getAll('permid', **{key:value})
        if not res:
            return []
        ret = []
        for p in res:
            ret.append({'permid':str2bin(p[0])})
        return ret
    
    def updatePeer(self, permid, **argv):
        self._db.update(self.table_name,  'permid='+repr(bin2str(permid)), **argv)

    def deletePeer(self, permid=None, peer_id=None, force=False):
        # don't delete friend of superpeers, except that force is True
        # TODO: add transaction
        #self._db._begin()    # begin a transaction
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return
        deleted = self._db.deletePeer(permid=permid, peer_id=peer_id, force=force)
        if deleted:
            self.pref_db._deletePeer(peer_id=peer_id)
        #self._db._commit()
            
    def updateTimes(self, permid, key, change=1):
        permid_str = bin2str(permid)
        sql = "SELECT peer_id,%s FROM Peer WHERE permid==?"%key
        find = self._db.fetchone(sql, (permid_str,))
        if find:
            peer_id,value = find
            if value is None:
                value = 1
            else:
                value += change
            sql_update_peer = "UPDATE Peer SET %s=? WHERE peer_id=?"%key
            self._db.execute(sql_update_peer, (value, peer_id))
        
    def getPermIDByIP(self,ip):
        permid = self.getOne('permid', ip=ip)
        if permid is not None:
            return str2bin(permid)
        else:
            return None
        
    def updatePeerIcon(self, permid, icontype, icondata, updateFlag = True):
         return
#        self.mm.save_data(permid, icontype, icondata)
#        if updateFlag:
#            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid, 'icon')
#    
    def getNumberPeers(self, category_name = 'all'):
        table = 'Peer'
        value = 'count(*)'
        where = '(buddycast_times>0 or friend=1)'
        if category_name == 'friend':
            where += ' and friend=1'
        
        return self._db.getOne(table, value, where)
    
    def getGUIPeers(self, category_name = 'all', range = None, sort = None, reverse = False):
        # load peers for GUI
        print >> sys.stderr, 'getGUIPeers(%s, %s, %s, %s)' % (category_name, range, sort, reverse)
        """
        old keys: 'content_name', 'simTop', 'name', 'last_connected', 'ip', 'port', 
                  'similarity', 'ntorrents', 'nprefs', 'permid', 
                  'connected_times', 'npeers', 'friend', 'buddycast_times'
                  
        db keys: peer_id, permid, name, ip, port, thumbnail, oversion, 
                 similarity, friend, superpeer, last_seen, last_connected, 
                 last_buddycast, connected_times, buddycast_times, num_peers, 
                 num_torrents, num_prefs, num_queries, 
        """
        value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs', 
                      'connected_times', 'buddycast_times', 'last_connected')
        key_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'npeers', 'ntorrents', 'nprefs', 
                      'connected_times', 'buddycast_times', 'last_connected')
        where = '(buddycast_times>0 or friend=1) '
        if category_name == 'friend':
            where += 'and friend=1'
        if range:
            offset= range[0]
            limit = range[1] - range[0]
        else:
            limit = offset = None
        if sort:
            desc = (not reverse) and 'desc' or ''
            if sort in ('name'):
                order_by = ' lower(%s) %s' % (sort, desc)
            else:
                order_by = ' %s %s' % (sort, desc)
        else:
            order_by = None
            
        res_list = self.getAll(value_name, where, offset= offset, limit=limit, order_by=order_by)
        peer_list = []
        for item in res_list:
            peer = dict(zip(key_name, item))
            peer['content_name'] = dunno2unicode(peer['name'])
            peer['permid'] = str2bin(peer['permid'])
            peer_list.append(peer)
        # peer_list consumes about 1.5M for 1400 peers, and this function costs about 0.015 second
        
        return  peer_list

        
class PreferenceDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if PreferenceDBHandler.__single is None:
            PreferenceDBHandler.lock.acquire()   
            try:
                if PreferenceDBHandler.__single is None:
                    PreferenceDBHandler(*args, **kw)
            finally:
                PreferenceDBHandler.lock.release()
        return PreferenceDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if PreferenceDBHandler.__single is not None:
            raise RuntimeError, "PreferenceDBHandler is singleton"
        PreferenceDBHandler.__single = self
        BasicDBHandler.__init__(self, 'Preference')
            
    def _getPeerPrefsID(self, peer_id):
        sql_get_peer_prefs_id = "SELECT torrent_id FROM Preference WHERE peer_id==?"
        res = self._db.fetchall(sql_get_peer_prefs_id, (peer_id,))
        return [t[0] for t in res]
    
    def getPrefList(self, permid, num=None):
        # get a peer's preference list
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return []
        
        torrent_ids = self._getPeerPrefsID(peer_id)
        prefs = []
        for torrent_id in torrent_ids:
            infohash = self._db.getInfohash(torrent_id)
            if infohash:
                prefs.append(infohash)
        
        return prefs
    
    def _deletePeer(self, permid=None, peer_id=None):   # delete a peer from pref_db
        # should only be called by PeerDBHandler
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
            if peer_id is None:
                return
        
        self._db.delete(self.table_name, peer_id=peer_id)

    def addPreference(self, permid, infohash, data={}):
        # This function should be replaced by addPeerPreferences 
        # peer_permid and prefs are binaries, the peer must have been inserted in Peer table
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            print >> sys.stderr, 'PreferenceDBHandler: add preference of a peer which is not existed in Peer table', `permid`
            return
        
        sql_insert_peer_torrent = "INSERT INTO Preference (peer_id, torrent_id) VALUES (?,?)"        
        torrent_id = self._db.getTorrentID(infohash)
        if not torrent_id:
            self._db.insertInfohash(infohash)
            torrent_id = self._db.getTorrentID(infohash)
        try:
            self._db.execute(sql_insert_peer_torrent, (peer_id, torrent_id))
        except sqlite.IntegrityError, msg:    # duplicated
            pass

    def addPreferences(self, peer_permid, prefs):
        # peer_permid and prefs are binaries, the peer must have been inserted in Peer table
        peer_id = self._db.getPeerID(peer_permid)
        if peer_id is None:
            print >> sys.stderr, 'PreferenceDBHandler: add preference of a peer which is not existed in Peer table', `permid`
            return
        
        torrent_id_prefs = []
        for infohash in prefs:
            torrent_id = self._db.getTorrentID(infohash)
            if not torrent_id:
                self._db.insertInfohash(infohash)
                torrent_id = self._db.getTorrentID(infohash)
            torrent_id_prefs.append((peer_id, torrent_id))
            
        sql_insert_peer_torrent = "INSERT INTO Preference (peer_id, torrent_id) VALUES (?,?)"        
        if len(prefs) > 0:
            try:
                self._db.executemany(sql_insert_peer_torrent, torrent_id_prefs)
            except sqlite.IntegrityError, msg:    # duplicated
                pass

        
class TorrentDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if TorrentDBHandler.__single is None:
            TorrentDBHandler.lock.acquire()   
            try:
                if TorrentDBHandler.__single is None:
                    TorrentDBHandler(*args, **kw)
            finally:
                TorrentDBHandler.lock.release()
        return TorrentDBHandler.__single
    
    getInstance = staticmethod(getInstance)

    def __init__(self):
        if TorrentDBHandler.__single is not None:
            raise RuntimeError, "TorrentDBHandler is singleton"
        TorrentDBHandler.__single = self
        BasicDBHandler.__init__(self, 'Torrent')
        
        self.mypref_db = MyPreferenceDBHandler.getInstance()
        
        self.status_table = self._db.getTorrentStatusTable()
        self.id2status = dict([(x,y) for (y,x) in self.status_table.items()]) 
        # 0 - unknown
        # 1 - good
        # 2 - dead
        
        self.category_table = self._db.getTorrentCategoryTable()
        self.category_table['unknown'] = 0 
        self.id2category = dict([(x,y) for (y,x) in self.category_table.items()])
        # 1 - Video
        # 2 - VideoClips
        # 3 - Audio
        # 4 - Compressed
        # 5 - Document
        # 6 - Picture
        # 7 - xxx
        # 8 - other
        
        self.src_table = self._db.getTorrentSourceTable()
        self.id2src = dict([(x,y) for (y,x) in self.src_table.items()])
        # 0 - ''    # local added
        # 1 - BC
        # 2,3,4... - URL of RSS feed
        
        self.keys = ['torrent_id', 'name', 'torrent_file_name',
                'length', 'creation_date', 'num_files', 'thumbnail',
                'insert_time', 'secret', 'relevance',
                'source_id', 'category_id', 'status_id',
                'num_seeders', 'num_leechers', 'comment']

    def getTorrentID(self, infohash):
        return self._db.getTorrentID(infohash)
    
    def getInfohash(self, torrent_id):
        return self._db.getInfohash(torrent_id)

    def hasTorrent(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:    # already added
            return False
        existed = self.getOne('torrent_id', torrent_id=torrent_id)        
        if existed is None:
            return False
        else:
            return True
    
    def addExternalTorrent(self, filename, source='BC', extra_info={}, metadata=None):
        infohash, torrent = self.readTorrentData(filename, source, extra_info, metadata)
        self.addTorrent(infohash, torrent)
        self.commit()
        
    def readTorrentData(self, filename, source='BC', extra_info={}, metadata=None):

        if metadata is None:
            f = open(filename, 'rb')
            metadata = f.read()
            f.close()
            
        try:
            metainfo = bdecode(metadata)
        except Exception,msg:
            print >> sys.stderr, `metadata`
            raise Exception,msg
        namekey = name2unicode(metainfo)  # convert info['name'] to type(unicode)
        info = metainfo['info']
        infohash = sha(bencode(info)).digest()

        torrent = {}
        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(filename)
        
        torrent_info = {}
        torrent_info['name'] = info.get(namekey, '')
        
        torrent['category'] = ['other']
        
        length = 0
        nf = 0
        if info.has_key('length'):
            length = info.get('length', 0)
            nf = 1
        elif info.has_key('files'):
            for li in info['files']:
                nf += 1
                if li.has_key('length'):
                    length += li['length']
        torrent_info['length'] = length
        torrent_info['num_files'] = nf
        torrent_info['announce'] = metainfo.get('announce', '')
        torrent_info['announce-list'] = metainfo.get('announce-list', '')
        torrent_info['creation date'] = metainfo.get('creation date', 0)
        torrent['info'] = torrent_info
        torrent['comment'] = metainfo.get('comment', None)
        
        torrent["ignore_number"] = 0
        torrent["retry_number"] = 0
        torrent["seeder"] = extra_info.get('seeder', -1)
        torrent["leecher"] = extra_info.get('leecher', -1)
        other_last_check = extra_info.get('last_check_time', -1)
        if other_last_check >= 0:
            torrent["last_check_time"] = int(time()) - other_last_check
        else:
            torrent["last_check_time"] = 0
        torrent["status"] = extra_info.get('status', "unknown")
        
        torrent["source"] = source
        torrent["inserttime"] = long(time())

        #if (torrent['category'] != []):
        #    print '### one torrent added from MetadataHandler: ' + str(torrent['category']) + ' ' + torrent['torrent_name'] + '###'
        return infohash, torrent
        
    def addTorrent(self, infohash, db_data={}, new_metadata=False):
        if self.hasTorrent(infohash):    # already added
            return
        
        #print >>sys.stderr,"sqldbhand: addTorrent",currentThread().getName()
        data = self._prepareData(db_data)
        self._addTorrentToDB(infohash, data)

    def _prepareData(self, db_data):
        # prepare data to insert into torrent table
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
        status_id = self._getStatusID(status)
        db_data['status'] = status_id
        
        # change category
        category_list = db_data.get('category', [])
        cat_int = self._getCategoryID(category_list)
        db_data['category'] = cat_int
        
        # change source
        src = db_data.get('source', '')
        src_int = self._getSourceID(src)
        db_data['source'] = src_int
        data.update(db_data)
        return data
    
    def _getStatusID(self, status):
        return self.status_table.get(status.lower(), 0)

    def _getCategoryID(self, category_list):
        if len(category_list) > 0:
            category = category_list[0].lower()
            cat_int = self.category_table[category]
        else:
            cat_int = 0
        return cat_int

    def _getSourceID(self, src):
        if src in self.src_table:
            src_int = self.src_table[src]
        else:
            src_int = self._insertNewSrc(src)    # add a new src, e.g., a RSS feed
            self.src_table[src] = src_int
        return src_int

    def _addTorrentToDB(self, infohash, data):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            self._db.insertInfohash(infohash)
            torrent_id = self._db.getTorrentID(infohash)

        sql_insert_torrent = """
        INSERT INTO Torrent 
        (torrent_id, name, torrent_file_name,
        length, creation_date, num_files, thumbnail,
        insert_time, secret, relevance,
        source_id, category_id, status_id,
        num_seeders, num_leechers, comment) 
        VALUES (?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?)
        """
        try:
            self._db.execute(sql_insert_torrent,
             (torrent_id, data['name'], data['torrent_name'], 
              data['length'], data['creation_date'], data['num_files'], data['thumbnail'], 
              data['inserttime'], data['secret'], data['relevance'],
              data['source'], data['category'], data['status'], 
              data['seeder'], data['leecher'], data['comment'])
             )
        except Exception, msg:
            print >> sys.stderr, "error input for addTorrentToDB:", Exception, msg, data
        
        self._addTorrentTracker(torrent_id, data)
            
        return torrent_id
    
    def _insertNewSrc(self, src):
        desc = ''
        if src.startswith('http') and src.endswith('xml'):
            desc = 'RSS'
        self._db.insert('TorrentSource', name=src, description=desc)
        src_id = self._db.getOne('TorrentSource', 'source_id', name=src)
        return src_id

    def _addTorrentTracker(self, torrent_id, data):
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
        self._db.executemany(sql_insert_torrent_tracker, values)
        
    def updateTorrent(self, infohash, **kw):    # watch the schema of database
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        
        if 'category' in kw:
            cat_id = self._getCategoryID(kw.pop('category'))
            kw['category_id'] = cat_id
        if 'status' in kw:
            status_id = self._getStatusID(kw.pop('status'))
            kw['status_id'] = status_id
        if 'progress' in kw:
            self.mypref_db.updateProgress(infohash, kw.pop('progress'))    # TODO: should be changed
        if 'seeder' in kw:
            kw['num_seeders'] = kw.pop('seeder')
        if 'leecher' in kw:
            kw['num_leechers'] = kw.pop('leecher')
        if 'last_check_time' in kw or 'ignore_number' in kw or 'retry_number' in kw:
            self.updateTracker(infohash, kw)
        
        for key in kw.keys():
            if key not in self.keys:
                kw.pop(key)
                
        if len(kw) > 0:
            self._db.update(self.table_name, 'torrent_id=%d'%torrent_id, **kw)
        
    def updateTracker(self, infohash, kw, tier=1, tracker=None):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        update = {}
        if 'last_check_time' in kw:
            update['last_check'] = kw.pop('last_check_time')
        if 'ignore_number' in kw:
            update['ignored_times'] = kw.pop('ignore_number')
        if 'retry_number' in kw:
            update['retried_times'] = kw.pop('retry_number')
        if tracker is None:
            where = 'torrent_id=%d AND announce_tier=%d'%(torrent_id, tier)
        else:
            where = 'torrent_id=%d AND tracker=%s'%(torrent_id, repr(tracker))
        self._db.update('TorrentTracker', where, **update)
        
    def deleteTorrent(self, infohash, delete_file=False):
        if not self.hasTorrent(infohash):
            return False
        
        if self.mypref_db.hasMyPreference(infohash):  # don't remove torrents in my pref
            return False

        if delete_file:
            deleted = self.eraseTorrentFile(infohash)
        else:
            deleted = True
        
        if deleted:
            self._deleteTorrent(infohash)
        
        return deleted

    def _deleteTorrent(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            self._db.delete(self.table_name, torrent_id=torrent_id)
            self._db.delete('TorrentTracker', torrent_id=torrent_id)
            
    def eraseTorrentFile(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            torrent_dir = self.getTorrentDir()
            torrent_name = self.getOne('torrent_file_name', torrent_id=torrent_id)
            src = os.path.join(torrent_dir, torrent_name)
            if not os.path.exists(src):    # already removed
                return True
            
            try:
                os.remove(src)
            except Exception, msg:
                print >> sys.stderr, "cachedbhandler: failed to erase torrent", src, Exception, msg
                return False
        
        return True
            
    def getTracker(self, infohash, tier=0):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            sql = "SELECT tracker, announce_tier FROM TorrentTracker WHERE torrent_id==%d"%torrent_id
            if tier > 0:
                sql += " AND announce_tier<=%d"%tier
            return self._db.fetchall(sql)
    
    def getTorrentDir(self):
        return MyDBHandler.getInstance().get('torrent_dir')
    
    def getTorrent(self, infohash, keys=None):
        table_name = ('Torrent', 'Infohash')
        where = 'Torrent.torrent_id = Infohash.torrent_id'
        if keys is not None:
            res = self._db.getOne(table_name, keys, where, infohash=bin2str(infohash))
            return res
        else:
            # return a dictionary
            # make it compatible for calls to old bsddb interface
            # Jie TODO: ugly codes. should focus on single task. move these codes to modules
            value_name = ('category_id', 'status_id', 'name', 'creation_date', 'num_files',
                      'num_leechers', 'num_seeders',   'length', 
                      'secret', 'insert_time', 'source_id', 'torrent_file_name',
                      'relevance', 'infohash')
            key_name = ('category', 'status', 'name', 'date', 'num_files', 
                       'leecher', 'seeder',  'length', 
                       'secret', 'inserttime', 'source', 'torrent_name',
                       'relevance', 'infohash')
            item = self._db.getOne(table_name, value_name, where, infohash=bin2str(infohash))
            if not item:
                return None
            torrent = dict(zip(key_name, item))
            torrent['source'] = self.id2src[torrent['source']]
            torrent['category'] = [self.id2category[torrent['category']]]
            torrent['status'] = self.id2status[torrent['status']]
            torrent['infohash'] = str2bin(torrent['infohash'])
            return torrent

#===============================================================================
#    # this func is much slower than getTorrent
#    def getTorrent2(self, infohash, keys):
#        torrent_id = self._db.getTorrentID(infohash)
#        if torrent_id is not None:
#            return self.getOne(keys, torrent_id=torrent_id)
#        
#===============================================================================
     
    def getAllTorrents(self):
        # Return a list of infohashes
        sql = 'select infohash from Torrent,Infohash where Torrent.torrent_id=Infohash.torrent_id and status_id>=0'
        res = self._db.execute(sql)
        return [str2bin(p[0]) for p in res]
        
#    def getAllTorrents2(self):
#        # This func is slower than getAllTorrents
#        sql = 'select infohash from Infohash where torrent_id in (select torrent_id from Torrent)'
#        res = self._db.execute(sql)
#        return [str2bin(p[0]) for p in res]
#    

    def getNumberTorrents(self, category_name = 'all', library = False):
        table = 'Torrent'
        value = 'count(*)'
        where = 'status_id=%d ' % self.status_table['good']
        if category_name != 'all':
            where += ' and category_id= %d' % self.category_table.get(category_name.lower(), -1) # unkown category_name returns no torrents
        if library:
            where += ' and Torrent.torrent_id in (select torrent_id from MyPreference)'
        
        return self._db.getOne(table, value, where)
        
    def getTorrents(self, category_name = 'all', range = None, library = False, sort = None, reverse = False):
        
        """
        get Torrents of some category and with alive status.
        
        @return Returns a list of dicts with keys: 
            torrent_id, infohash, name, category, status, creation_date, num_files, num_leechers, num_seeders,
            length, secret, insert_time, source, torrent_filename, relevance, 
            (if in library: myDownloadHistory, download_started, progress, dest_dir)
        
        """
        
        #print >> sys.stderr, 'getTorrents(%s, %s, %s, %s, %s)' % (category_name, range, library, sort, reverse)
        s = time()
        value_name = ['Torrent.torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
                      'num_leechers', 'num_seeders', 'length', 
                      'secret', 'insert_time', 'source_id', 'torrent_file_name',
                      'relevance', 'infohash']
        
        table_name = ('Torrent', 'Infohash')
        where = 'Torrent.torrent_id = Infohash.torrent_id and status_id=%d ' % self.status_table['good']
        if category_name != 'all':
            where += ' and category_id= %d' % self.category_table.get(category_name.lower(), -1) # unkown category_name returns no torrents
        if library:
            where += ' and Torrent.torrent_id in (select torrent_id from MyPreference)'
        if range:
            offset= range[0]
            limit = range[1] - range[0]
        else:
            limit = offset = None
        if sort:
            desc = (not reverse) and 'desc' or ''
            if sort in ('name'):
                order_by = ' lower(%s) %s' % (sort, desc)
            else:
                order_by = ' %s %s' % (sort, desc)
        else:
            order_by = None
        res_list = self._db.getAll(table_name, value_name, where, limit=limit, offset=offset, order_by=order_by)
        
        if library:
            mypref_stats = self.mypref_db.getMyPrefStats()
        
        torrent_list = []
        for item in res_list:
            value_name[0] = 'torrent_id'
            torrent = dict(zip(value_name, item))
            torrent['source'] = self.id2src[torrent['source_id']]
            torrent['category'] = [self.id2category[torrent['category_id']]]
            torrent['status'] = self.id2status[torrent['status_id']]
            torrent['infohash'] = str2bin(torrent['infohash'])
            #torrent['num_swarm'] = torrent['num_seeders'] + torrent['num_leechers'] 
            del torrent['source_id']
            del torrent['category_id']
            del torrent['status_id']
            torrent_id = torrent['torrent_id']
            if library and torrent_id in mypref_stats:
                # add extra info for torrent in mypref
                torrent['myDownloadHistory'] = True
                data = mypref_stats[torrent_id]  #(create_time,progress,destdir)
                torrent['download_started'] = data[0]
                torrent['progress'] = data[1]
                torrent['destdir'] = data[2]
            torrent_list.append(torrent)
        del res_list
        if library:
            del mypref_stats
        # torrent_list consumes about 2MB for 4836 torrents, and this function costs about 0.15 second
        #print time()-s
        return  torrent_list
        
    def getCollectedTorrentHashes(self): 
        """ get infohashes of torrents on disk, used by torrent checking, 
            and metadata handler
        """
        sql = "select infohash from Infohash where torrent_id in (select torrent_id from Torrent)"
        res = self._db.fetchall(sql)
        return [t[0] for t in res]
        
    def hasMetaData(self, infohash):
        return self.hasTorrent(infohash)
    
    def updateTorrentRelevance(self, infohash, relevance):
        self.updateTorrent(infohash, relevance=relevance)

    def searchNames(self,kws):
        """ Get all good torrents that have the specified keywords in their name. 
        Return a list of dictionaries. Each dict is in the NEWDBSTANDARD format.
        """
        sql = 'select Infohash.infohash,Torrent.* from Torrent INNER JOIN Infohash ON Torrent.torrent_id = Infohash.torrent_id where Torrent.status_id = 1 and' 
        
        for i in range(len(kws)):
            kw = kws[i]
            sql += ' name like "%'+kw+'%"'
            if (i+1) != len(kws):
                sql += ' and'  
        #print >>sys.stderr,"torrent_db: searchNames: sql",sql
        res = self._db.execute(sql)
        #print >>sys.stderr,"torrent_db: searchNames: res",`res`
        
        all = []
        for flist in res:
            #print >>sys.stderr,"torrent_db: searchNames: Got Record",`flist`
            infohash = str2bin(flist[0])
            d = self._selectStar2dict(flist[1:])
            # Extra field
            d['infohash'] = infohash
            all.append(d)
        return all
            
    def _selectStar2dict(self,flist):
        """ CAUTION: keys must contain the names of the fields as they appear in the
        Torrent table. I.e. the order of the fields when you do SELECT * from Torrent.
        NEWDBSTANDARD
        """
        keys = ['torrent_id','name','torrent_file_name','length','creation_date','num_files','thumbnail','insert_time','secret','relevance','source_id','category_id','status_id','num_seeders','num_leechers','comment']
        torrent = dict(zip(keys,flist))
        torrent['source'] = self.id2src[torrent['source_id']]
        del torrent['source_id']
        torrent['category'] = [self.id2category[torrent['category_id']]]
        del torrent['category_id']
        return torrent


class MyPreferenceDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if MyPreferenceDBHandler.__single is None:
            MyPreferenceDBHandler.lock.acquire()   
            try:
                if MyPreferenceDBHandler.__single is None:
                    MyPreferenceDBHandler(*args, **kw)
            finally:
                MyPreferenceDBHandler.lock.release()
        return MyPreferenceDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if MyPreferenceDBHandler.__single is not None:
            raise RuntimeError, "MyPreferenceDBHandler is singleton"
        MyPreferenceDBHandler.__single = self
        BasicDBHandler.__init__(self, 'MyPreference')

        self.status_table = self._db.getTorrentStatusTable()
        self.status_good = self.status_table['good']
        self.recent_preflist = None
        self.coccurrence = None
        self.last_get_preflist = 0
        self.cache_preflist_timeout = 24*60*60    # re-get my recent preflist every one day
        
    def loadData(self):
        self.getRecentLivePrefList()
        self.getAllTorrentCoccurrence()
    
    def getMyPrefList(self, order_by=None):
        res = self.getAll('torrent_id', order_by=order_by)
        return [p[0] for p in res]

    def getMyPrefListInfohash(self):
        sql = 'select infohash from Infohash where torrent_id in (select torrent_id from MyPreference)'
        res = self._db.execute(sql)
        return [str2bin(p[0]) for p in res]
    
    def getMyPrefStats(self):
        # get the full {torrent_id:(create_time,progress,destdir)}
        value_name = ('torrent_id','creation_time','progress','destination_path')
        res = self.getAll(value_name)
        mypref_stats = {}
        for pref in res:
            torrent_id,creation_time,progress,destination_path = pref
            mypref_stats[torrent_id] = (creation_time,progress,destination_path)
        return mypref_stats
        
    def getCreationTime(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            ct = self.getOne('creation_time', torrent_id=torrent_id)
            return ct
        else:
            return None
        
    def getRecentLivePrefList(self, num=0):    # num = 0: all files
        # get recent and live torrents
        if self.recent_preflist is None or time()-self.last_get_preflist>self.cache_preflist_timeout:
            sql = """
            select m.torrent_id from MyPreference m, Torrent t 
            where m.torrent_id == t.torrent_id 
            and status_id == %d
            order by creation_time desc
            """ % self.status_good

            torrent_ids = self._db.fetchall(sql)
            if not torrent_ids:
                self.recent_preflist = []
            else:
                self.recent_preflist = [self._db.getInfohash(t[0]) for t in torrent_ids]
            self.last_get_preflist = time()

        if num != 0:
            return self.recent_preflist[:num]
        else:
            return self.recent_preflist

    def hasMyPreference(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return False
        res = self.getOne('torrent_id', torrent_id=torrent_id)
        if res is not None:
            return True
        else:
            return False
            
    def addMyPreference(self, infohash, data):
        # keys in data: destination_path, progress, creation_time, torrent_id
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None or self.hasMyPreference(infohash):
            return False
        d = {}
        d['destination_path'] = data.get('destination_path')
        d['progress'] = data.get('progress', 0)
        d['creation_time'] = data.get('creation_time', int(time()))
        d['torrent_id'] = torrent_id
        self._db.insert(self.table_name, **d)
        self.commit()
        if self.recent_preflist is None:
            self.getRecentLivePrefList()
        self.recent_preflist.insert(0, infohash)
        self.getAllTorrentCoccurrence()
        return True

    def deletePreference(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.delete(self.table_name, **{'torrent_id':torrent_id})
        if infohash in self.recent_preflist:
            self.recent_preflist.remove(infohash)
        
    def updateProgress(self, infohash, progress):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.update(self.table_name, 'torrent_id=%d'%torrent_id, progress=progress)

    def getInfohashRelevance(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        return self.coccurrence.get(torrent_id, 0)

    def getAllTorrentCoccurrence(self):
        # should be placed in PreferenceDBHandler, but put here to be convenient for TorrentCollecting
        sql = """select torrent_id, count(torrent_id) as coocurrency from Preference where peer_id in
            (select peer_id from Preference where torrent_id in 
            (select torrent_id from MyPreference)) and torrent_id not in 
            (select torrent_id from MyPreference)
            group by torrent_id
            """
        self.coccurrence = dict(self._db.fetchall(sql))

        
class BarterCastDBHandler(BasicDBHandler):

    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        return None
        if BarterCastDBHandler.__single is None:
            BarterCastDBHandler.lock.acquire()   
            try:
                if BarterCastDBHandler.__single is None:
                    BarterCastDBHandler(*args, **kw)
            finally:
                BarterCastDBHandler.lock.release()
        return BarterCastDBHandler.__single
    
    getInstance = staticmethod(getInstance)

    def __init__(self):
        BasicDBHandler.__init__(self, 'BarterCast')
        raise NotImplementedError
        

