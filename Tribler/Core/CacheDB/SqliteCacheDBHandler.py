# Written by Jie Yang
# see LICENSE.txt for license information
# Note for Developers: Please write testsuit in Tribler/Test/test_sqlitecachedbhandler.py 
# for any function you added to database. 
# Please reuse the functions in sqlitecachedb as more as possible

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from unicode import name2unicode,dunno2unicode
from copy import deepcopy,copy
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
from random import randint

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Notifier import Notifier
from Tribler.Core.simpledefs import *

DEBUG = False
SHOW_ERROR = True

def show_permid_shorter(permid):
    if not permid:
        return 'None'
    s = base64.encodestring(permid).replace("\n","")
    return s[-5:]

class BasicDBHandler:
    def __init__(self, db, table_name):
        self._db = db
        self.table_name = table_name
        self.notifier = Notifier.getInstance()
        
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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self,db,'MyInfo')
        # keys: version, torrent_dir
        
    def get(self, key, default_value=None):
        value = self.getOne('value', entry=key)
        if value is not NULL:
            return value
        else:
            if default_value is not None:
                return default_value
            else:
                raise KeyError, key

    def put(self, key, value, commit=True):
        if self.getOne('value', entry=key) is NULL:
            self._db.insert(self.table_name, commit=commit, entry=key, value=value)
        else:
            where = "entry=" + repr(key)
            self._db.update(self.table_name, where, commit=commit, value=value)

class FriendDBHandler(BasicDBHandler):
    
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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Peer')
        
    def setFriendState(self, permid, state=1, commit=True):
        self._db.update(self.table_name,  'permid='+repr(bin2str(permid)), commit=commit, friend=state)
        self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid, 'friend', state)

    def getFriends(self,state=1):
        where = 'friend=%d ' % state
        res = self._db.getAll('Friend', 'permid',where=where)
        return [str2bin(p[0]) for p in res]
        #raise Exception('Use PeerDBHandler getGUIPeers(category = "friend")!')

    def getFriendState(self, permid):
        res = self.getOne('friend', permid=bin2str(permid))
        return res
        
    def deleteFriend(self,permid):
        self.setFriendState(permid,0)
        
    def searchNames(self,kws):
        return doPeerSearchNames(self,'Friend',kws)
        
    def getRanks(self):
        # TODO
        return []
    
    def size(self):
        return self._db.size('Friend')
    
    def addExternalFriend(self, peer):
        peerdb = PeerDBHandler.getInstance()
        peerdb.addPeer(peer['permid'], peer)
        self.setFriendState(peer['permid'])
        
NETW_MIME_TYPE = 'image/jpeg'

class PeerDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()

    gui_value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs', 
                      'connected_times', 'buddycast_times', 'last_connected')
    
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
    
    def __init__(self):
        if PeerDBHandler.__single is not None:
            raise RuntimeError, "PeerDBHandler is singleton"
        PeerDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Peer')
        self.pref_db = PreferenceDBHandler.getInstance()
        self.online_peers = set()


    def __len__(self):
        return self.size()

    def getPeerID(self, permid):
        return self._db.getPeerID(permid)

    def getPeer(self, permid, keys=None):
        if keys is not None:
            res = self.getOne(keys, permid=bin2str(permid))
            return res
        else:
            # return a dictionary
            # make it compatible for calls to old bsddb interface
            value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs', 'num_queries', 
                      'connected_times', 'buddycast_times', 'last_connected', 'last_seen', 'last_buddycast')

            item = self.getOne(value_name, permid=bin2str(permid))
            if not item:
                return None
            peer = dict(zip(value_name, item))
            peer['permid'] = str2bin(peer['permid'])
            return peer
        
    def getPeerSim(self, permid):
        permid_str = bin2str(permid)
        sim = self.getOne('similarity', permid=permid_str)
        if sim is None:
            sim = 0
        return sim
        
    def getPeerList(self, peerids=None):    # get the list of all peers' permid
        if peerids is None:
            permid_strs = self.getAll('permid')
            return [str2bin(permid_str[0]) for permid_str in permid_strs]
        else:
            if not peerids:
                return []
            s = str(peerids).replace('[','(').replace(']',')')
#            if len(peerids) == 1:
#                s = '(' + str(peerids[0]) + ')'    # tuple([1]) = (1,), syntax error for sql
#            else:
#                s = str(tuple(peerids))
            sql = 'select permid from Peer where peer_id in ' + s
            permid_strs = self._db.fetchall(sql)
            return [str2bin(permid_str[0]) for permid_str in permid_strs]
        

    def getPeers(self, peer_list, keys):    # get a list of dictionaries given peer list
        # BUG: keys must contain 2 entries, otherwise the records in all are single values??
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
    
    def addPeer(self, permid, value, update_dns=True, update_connected=False, commit=True):
        # add or update a peer
        # ARNO: AAARGGH a method that silently changes the passed value param!!!
        # Jie: deepcopy(value)?
        
        _permid = _last_seen = _ip = _port = None
        if 'permid' in value:
            _permid = value.pop('permid')
            
        if not update_dns:
            if value.has_key('ip'):
                _ip = value.pop('ip')
            if value.has_key('port'):
                _port = value.pop('port')
                
        if update_connected:
            old_connected = self.getOne('connected_times', permid=bin2str(permid))
            if not old_connected:
                value['connected_times'] = 1
            else:
                value['connected_times'] = old_connected + 1
            
        peer_existed = self._db.insertPeer(permid, commit=commit, **value)
        
        if _permid is not None:
            value['permid'] = permid
        if _last_seen is not None:
            value['last_seen'] = _last_seen
        if _ip is not None:
            value['ip'] = _ip
        if _port is not None:
            value['port'] = _port
        
        if peer_existed:
            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)
        # Jie: only notify the GUI when a peer was connected
        if 'connected_times' in value:
            self.notifier.notify(NTFY_PEERS, NTFY_INSERT, permid)

        #print >>sys.stderr,"sqldbhand: addPeer",`permid`,self._db.getPeerID(permid),`value`
        #print_stack()
            
            
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
    
    def updatePeer(self, permid, commit=True, **argv):
        self._db.update(self.table_name, 'permid='+repr(bin2str(permid)), commit=commit, **argv)
        self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)

        #print >>sys.stderr,"sqldbhand: updatePeer",`permid`,argv
        #print_stack()

    def deletePeer(self, permid=None, peer_id=None, force=False, commit=True):
        # don't delete friend of superpeers, except that force is True
        # to do: add transaction
        #self._db._begin()    # begin a transaction
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return
        deleted = self._db.deletePeer(permid=permid, peer_id=peer_id, force=force, commit=commit)
        if deleted:
            self.pref_db._deletePeer(peer_id=peer_id, commit=commit)
        self.notifier.notify(NTFY_PEERS, NTFY_DELETE, permid)
            
    def updateTimes(self, permid, key, change=1, commit=True):
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
            self._db.execute_write(sql_update_peer, (value, peer_id), commit=commit)
        self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)

    def updatePeerSims(self, sim_list, commit=True):
        sql_update_sims = 'UPDATE Peer SET similarity=? WHERE peer_id=?'
        s = time()
        self._db.executemany(sql_update_sims, sim_list, commit=commit)

    def getPermIDByIP(self,ip):
        permid = self.getOne('permid', ip=ip)
        if permid is not None:
            return str2bin(permid)
        else:
            return None
        
    def getPermid(self, peer_id):
        permid = self.getOne('permid', peer_id=peer_id)
        if permid is not None:
            return str2bin(permid)
        else:
            return None
        
    def getNumberPeers(self, category_name = 'all'):
        # 28/07/08 boudewijn: counting the union from two seperate
        # select statements is faster than using a single select
        # statement with an OR in the WHERE clause. Note that UNION
        # returns a distinct list of peer_id's.
        if category_name == 'friend':
            sql = 'SELECT COUNT(peer_id) FROM Peer WHERE last_connected > 0 AND friend = 1'
        else:
            sql = 'SELECT COUNT(peer_id) FROM (SELECT peer_id FROM Peer WHERE last_connected > 0 UNION SELECT peer_id FROM Peer WHERE friend = 1)'
        res = self._db.fetchone(sql)
        if not res:
            res = 0
        return res
    
    def getGUIPeers(self, category_name = 'all', range = None, sort = None, reverse = False, get_online=False, get_ranks=True):
        #
        # ARNO: WHY DIFF WITH NORMAL getPeers??????
        # load peers for GUI
        #print >> sys.stderr, 'getGUIPeers(%s, %s, %s, %s)' % (category_name, range, sort, reverse)
        """
        db keys: peer_id, permid, name, ip, port, thumbnail, oversion, 
                 similarity, friend, superpeer, last_seen, last_connected, 
                 last_buddycast, connected_times, buddycast_times, num_peers, 
                 num_torrents, num_prefs, num_queries, 
                 
        @in: get_online: boolean: if true, give peers a key 'online' if there is a connection now
        """
        value_name = PeerDBHandler.gui_value_name
        
        where = '(last_connected>0 or friend=1 or friend=2 or friend=3) '
        if category_name in ('friend', 'friends'):
            # Show mutual, I invited and he invited 
            where += 'and (friend=1 or friend=2 or friend=3) '
        if range:
            offset= range[0]
            limit = range[1] - range[0]
        else:
            limit = offset = None
        if sort:
            # Arno, 2008-10-6: buggy: not reverse???
            desc = (reverse) and 'desc' or ''
            if sort in ('name'):
                order_by = ' lower(%s) %s' % (sort, desc)
            else:
                order_by = ' %s %s' % (sort, desc)
        else:
            order_by = None

        # Must come before query
        if get_ranks:
            ranks = self.getRanks()
        ranks = None
            
        res_list = self.getAll(value_name, where, offset= offset, limit=limit, order_by=order_by)
        
        #print >>sys.stderr,"getGUIPeers: where",where,"offset",offset,"limit",limit,"order",order_by
        #print >>sys.stderr,"getGUIPeers: returned len",len(res_list)
        
        peer_list = []
        for item in res_list:
            peer = dict(zip(value_name, item))
            peer['name'] = dunno2unicode(peer['name'])
            peer['simRank'] = ranksfind(ranks,peer['permid'])
            peer['permid'] = str2bin(peer['permid'])
            peer_list.append(peer)
            
        if get_online:
           self.checkOnline(peer_list)
            
        # peer_list consumes about 1.5M for 1400 peers, and this function costs about 0.015 second
        
        return  peer_list

            
    def getRanks(self):
        value_name = 'permid'
        order_by = 'similarity desc'
        rankList_size = 20
        where = '(last_connected>0 or friend=1) '
        res_list = self._db.getAll('Peer', value_name, where=where, limit=rankList_size, order_by=order_by)
        return [a[0] for a in res_list]
        
    def checkOnline(self, peerlist):
        # Add 'online' key in peers when their permid
        # Called by any thread, accesses single online_peers-dict
        # Peers will never be sorted by 'online' because it is not in the db.
        # Do not sort here, because then it would be sorted with a partial select (1 page in the grid)
        self.lock.acquire()
        for peer in peerlist:
            peer['online'] = (peer['permid'] in self.online_peers)
        self.lock.release()
        
        

    def setOnline(self,subject,changeType,permid,*args):
        """Called by callback threads
        with NTFY_CONNECTION, args[0] is boolean: connection opened/closed
        """
        self.lock.acquire()
        if args[0]: # connection made
            self.online_peers.add(permid)
        else: # connection closed
            self.online_peers.remove(permid)
        self.lock.release()
        #print >> sys.stderr, (('#'*50)+'\n')*5+'%d peers online' % len(self.online_peers)

    def registerConnectionUpdater(self, session):
        session.add_observer(self.setOnline, NTFY_PEERS, [NTFY_CONNECTION], None)
    
    def updatePeerIcon(self, permid, icontype, icondata, updateFlag = True):
         # save thumb in db
         self.updatePeer(permid, thumbnail=bin2str(icondata))
         #if self.mm is not None:
         #    self.mm.save_data(permid, icontype, icondata)
    

    def getPeerIcon(self, permid):
        item = self.getOne('thumbnail', permid=bin2str(permid))
        if item:
            return NETW_MIME_TYPE, str2bin(item)
        else:
            return None, None
        #if self.mm is not None:
        #    return self.mm.load_data(permid)
        #3else:
        #    return None


    def searchNames(self,kws):
        return doPeerSearchNames(self,'Peer',kws)



class SuperPeerDBHandler(BasicDBHandler):
    
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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'SuperPeer')
        self.peer_db_handler = PeerDBHandler.getInstance()
        
    def loadSuperPeers(self, config, refresh=False):
        filename = os.path.join(config['install_dir'], config['superpeer_file'])
        superpeer_list = self.readSuperPeerList(filename)
        self.insertSuperPeers(superpeer_list, refresh)

    def readSuperPeerList(self, filename=''):
        """ read (superpeer_ip, superpeer_port, permid [, name]) lines from a text file """
        
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
                          'permid':superpeer_info[2], 'superpeer':1}
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
            permid = superpeer.pop('permid')
            self.peer_db_handler.addPeer(permid, superpeer, commit=False)
        self.peer_db_handler.commit()
    
    def getSuperPeers(self):
        # return list with permids of superpeers
        res_list = self._db.getAll(self.table_name, 'permid')
        return [str2bin(a[0]) for a in res_list]
        
    def addExternalSuperPeer(self, peer):
        _peer = deepcopy(peer)
        permid = _peer.pop('permid')
        _peer['superpeer'] = 1
        self._db.insertPeer(permid, **_peer)


class CrawlerDBHandler:
    """
    The CrawlerDBHandler is not an actual handle to a
    database. Instead it uses a local file (usually crawler.txt) to
    identify crawler processes.
    """
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if CrawlerDBHandler.__single is None:
            CrawlerDBHandler.lock.acquire()   
            try:
                if CrawlerDBHandler.__single is None:
                    CrawlerDBHandler(*args, **kw)
            finally:
                CrawlerDBHandler.lock.release()
        return CrawlerDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if CrawlerDBHandler.__single is not None:
            raise RuntimeError, "CrawlerDBHandler is singleton"
        CrawlerDBHandler.__single = self
        self._crawler_list = []
        
    def loadCrawlers(self, config, refresh=False):
        filename = os.path.join(config['crawler_file'])
        self._crawler_list = self.readCrawlerList(filename)

    def readCrawlerList(self, filename=''):
        """
        read (permid [, name]) lines from a text file
        returns a list containing permids
        """
        
        try:
            filepath = os.path.abspath(filename)
            file = open(filepath, "r")
        except IOError:
            print >> sys.stderr, "crawler: cannot open crawler file", filepath
            return []
            
        crawlers = file.readlines()
        file.close()
        crawlers_info = []
        for crawler in crawlers:
            if crawler.strip().startswith("#"):    # skip commended lines
                continue
            crawler_info = [a.strip() for a in crawler.split(",")]
            try:
                crawler_info[0] = base64.decodestring(crawler_info[0]+'\n')
            except:
                print_exc()
                continue
            crawlers_info.append(str2bin(crawler))
                    
        return crawlers_info

    def temporarilyAddCrawler(self, permid):
        """
        Because of security reasons we will not allow crawlers to be
        added to the crawler.txt list. This temporarilyAddCrawler
        method can be used to add one for the running session. Usefull
        for debugging and testing.
        """
        if not permid in self._crawler_list:
            self._crawler_list.append(permid)

    def getCrawlers(self):
        """
        returns a list with permids of crawlers
        """
        return self._crawler_list


        
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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Preference')
            
    def _getTorrentOwnersID(self, torrent_id):
        sql_get_torrent_owners_id = "SELECT peer_id FROM Preference WHERE torrent_id==?"
        res = self._db.fetchall(sql_get_torrent_owners_id, (torrent_id,))
        return [t[0] for t in res]
    
    def getPrefList(self, permid, return_infohash=False):
        # get a peer's preference list of infohash or torrent_id according to return_infohash
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return []
        
        if not return_infohash:
            sql_get_peer_prefs_id = "SELECT torrent_id FROM Preference WHERE peer_id==?"
            res = self._db.fetchall(sql_get_peer_prefs_id, (peer_id,))
            return [t[0] for t in res]
        else:
            sql_get_infohash = "SELECT infohash FROM Torrent WHERE torrent_id IN (SELECT torrent_id FROM Preference WHERE peer_id==?)"
            res = self._db.fetchall(sql_get_infohash, (peer_id,))
            return [str2bin(t[0]) for t in res]
    
    def _deletePeer(self, permid=None, peer_id=None, commit=True):   # delete a peer from pref_db
        # should only be called by PeerDBHandler
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
            if peer_id is None:
                return
        
        self._db.delete(self.table_name, commit=commit, peer_id=peer_id)

    def addPreference(self, permid, infohash, data={}, commit=True):
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
            self._db.execute_write(sql_insert_peer_torrent, (peer_id, torrent_id), commit=commit)
        except Exception, msg:    # duplicated
            print_exc()

    def addPreferences(self, peer_permid, prefs, is_torrent_id=False, commit=True):
        # peer_permid and prefs are binaries, the peer must have been inserted in Peer table
        peer_id = self._db.getPeerID(peer_permid)
        if peer_id is None:
            print >> sys.stderr, 'PreferenceDBHandler: add preference of a peer which is not existed in Peer table', `peer_permid`
            return
        
        if not is_torrent_id:
            torrent_id_prefs = []
            for infohash in prefs:
                torrent_id = self._db.getTorrentID(infohash)
                if not torrent_id:
                    self._db.insertInfohash(infohash)
                    torrent_id = self._db.getTorrentID(infohash)
                torrent_id_prefs.append((peer_id, torrent_id))
        else:
            torrent_id_prefs = [(peer_id, tid) for tid in prefs]
            
        sql_insert_peer_torrent = "INSERT INTO Preference (peer_id, torrent_id) VALUES (?,?)"        
        if len(prefs) > 0:
            try:
                self._db.executemany(sql_insert_peer_torrent, torrent_id_prefs, commit=commit)
            except Exception, msg:    # duplicated
                print_exc()
                print >> sys.stderr, 'dbhandler: addPreferences:', Exception, msg

    def getRecentPeersPrefs(self, key, num=None):
        # get the recently seen peers' preference. used by buddycast
        sql = "select peer_id,torrent_id from Preference where peer_id in (select peer_id from Peer order by %s desc)"%key
        if num is not None:
             sql = sql[:-1] + " limit %d)"%num
        res = self._db.fetchall(sql)
        return res

        
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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Torrent')
        
        self.mypref_db = MyPreferenceDBHandler.getInstance()
        
        self.status_table = {'good':1, 'unknown':0, 'dead':2}
        self.status_table.update(self._db.getTorrentStatusTable())
        self.id2status = dict([(x,y) for (y,x) in self.status_table.items()]) 
        self.torrent_dir = None
        # 0 - unknown
        # 1 - good
        # 2 - dead
        
        self.category_table  = {'Video':1,
                                'VideoClips':2,
                                'Audio':3,
                                'Compressed':4,
                                'Document':5,
                                'Picture':6,
                                'xxx':7,
                                'other':8,}
        self.category_table.update(self._db.getTorrentCategoryTable())
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
        self.existed_torrents = Set()


        self.value_name = ['C.torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
                      'num_leechers', 'num_seeders', 'length', 
                      'secret', 'insert_time', 'source_id', 'torrent_file_name',
                      'relevance', 'infohash', 'tracker', 'last_check']

    def register(self, category, torrent_dir):
        self.category = category
        self.torrent_dir = torrent_dir

    def getTorrentID(self, infohash):
        return self._db.getTorrentID(infohash)
    
    def getInfohash(self, torrent_id):
        return self._db.getInfohash(torrent_id)

    def hasTorrent(self, infohash):
        if infohash in self.existed_torrents:    #to do: not thread safe
            return True
        infohash_str = bin2str(infohash)
        existed = self._db.getOne('CollectedTorrent', 'torrent_id', infohash=infohash_str)
        if existed is None:
            return False
        else:
            self.existed_torrents.add(infohash)
            return True
    
    def addExternalTorrent(self, filename, source='BC', extra_info={}, metadata=None):
        infohash, torrent = self._readTorrentData(filename, source, extra_info, metadata)
        if infohash is None:
            return torrent
        if not self.hasTorrent(infohash):
            self._addTorrentToDB(infohash, torrent, commit=True)
            self.notifier.notify(NTFY_TORRENTS, NTFY_INSERT, infohash)

        return torrent

    def _readTorrentData(self, filename, source='BC', extra_info={}, metadata=None):
        # prepare data to insert into database
        try:
            if metadata is None:
                f = open(filename, 'rb')
                metadata = f.read()
                f.close()
            
            metainfo = bdecode(metadata)
        except Exception,msg:
            print >> sys.stderr, Exception,msg,`metadata`
            return None,None
        
        namekey = name2unicode(metainfo)  # convert info['name'] to type(unicode)
        info = metainfo['info']
        infohash = sha(bencode(info)).digest()

        torrent = {'infohash': infohash}
        torrent['torrent_file_name'] = os.path.split(filename)[1]
        torrent['name'] = info.get(namekey, '')
        
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
        torrent['length'] = length
        torrent['num_files'] = nf
        torrent['announce'] = metainfo.get('announce', '')
        torrent['announce-list'] = metainfo.get('announce-list', '')
        torrent['creation_date'] = metainfo.get('creation date', 0)
        
        torrent['comment'] = metainfo.get('comment', None)
        
        torrent["ignore_number"] = 0
        torrent["retry_number"] = 0
        torrent["num_seeders"] = extra_info.get('seeder', -1)
        torrent["num_leechers"] = extra_info.get('leecher', -1)
        other_last_check = extra_info.get('last_check_time', -1)
        if other_last_check >= 0:
            torrent["last_check_time"] = int(time()) - other_last_check
        else:
            torrent["last_check_time"] = 0
        torrent["status"] = self._getStatusID(extra_info.get('status', "unknown"))
        
        torrent["source"] = self._getSourceID(source)
        torrent["insert_time"] = long(time())

        torrent['category'] = self._getCategoryID(self.category.calculateCategory(metainfo, torrent['name']))
        torrent['secret'] = 0 # to do: check if torrent is secret
        torrent['relevance'] = 0.0
        thumbnail = 0
        if 'azureus_properties' in metainfo and 'Content' in metainfo['azureus_properties']:
            if metainfo['azureus_properties']['Content'].get('Thumbnail',''):
                thumbnail = 1
        torrent['thumbnail'] = thumbnail
        
        #if (torrent['category'] != []):
        #    print '### one torrent added from MetadataHandler: ' + str(torrent['category']) + ' ' + torrent['torrent_name'] + '###'
        return infohash, torrent
        
    def addInfohash(self, infohash, commit=True):
        if self._db.getTorrentID(infohash) is None:
            self._db.insert('Torrent', commit=commit, infohash=bin2str(infohash))

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
            self.id2src[src_int] = src
        return src_int

    def _addTorrentToDB(self, infohash, data, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:    # not in db
            infohash_str = bin2str(infohash)
            self._db.insert('Torrent', 
                        commit=True,    # must commit to get the torrent id
                        infohash = infohash_str,
                        name = dunno2unicode(data['name']),
                        torrent_file_name = data['torrent_file_name'],
                        length = data['length'], 
                        creation_date = data['creation_date'], 
                        num_files = data['num_files'], 
                        thumbnail = data['thumbnail'],
                        insert_time = data['insert_time'], 
                        secret = data['secret'], 
                        relevance = data['relevance'],
                        source_id = data['source'], 
                        category_id = data['category'], 
                        status_id = data['status'],
                        num_seeders = data['num_seeders'], 
                        num_leechers = data['num_leechers'], 
                        comment = dunno2unicode(data['comment']))
            torrent_id = self._db.getTorrentID(infohash)
        else:    # infohash in db
            where = 'torrent_id = %d'%torrent_id
            self._db.update('Torrent', where = where,
                            commit=False,
                            name = dunno2unicode(data['name']),
                            torrent_file_name = data['torrent_file_name'],
                            length = data['length'], 
                            creation_date = data['creation_date'], 
                            num_files = data['num_files'], 
                            thumbnail = data['thumbnail'],
                            insert_time = data['insert_time'], 
                            secret = data['secret'], 
                            relevance = data['relevance'],
                            source_id = data['source'], 
                            category_id = data['category'], 
                            status_id = data['status'],
                            num_seeders = data['num_seeders'], 
                            num_leechers = data['num_leechers'], 
                            comment = dunno2unicode(data['comment']))
        
        self._addTorrentTracker(torrent_id, data, commit=False)
        if commit:
            self.commit()    
        self._db.show_execute = False
        return torrent_id
    
    def _insertNewSrc(self, src, commit=True):
        desc = ''
        if src.startswith('http') and src.endswith('xml'):
            desc = 'RSS'
        self._db.insert('TorrentSource', commit=commit, name=src, description=desc)
        src_id = self._db.getOne('TorrentSource', 'source_id', name=src)
        return src_id

    def _addTorrentTracker(self, torrent_id, data, add_all=False, commit=True):
        # Set add_all to True if you want to put all multi-trackers into db.
        # In the current version (4.2) only the main tracker is used.
        exist = self._db.getOne('TorrentTracker', 'tracker', torrent_id=torrent_id)
        if exist:
            return
        
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
        # each torrent only has one announce with tier number 1
        tier_num = 2
        trackers = {announce:None}
        if add_all:
            for tier in announce_list:
                for tracker in tier:
                    if tracker in trackers:
                        continue
                    value = (torrent_id, tracker, tier_num, 0, 0, 0)
                    values.append(value)
                    trackers[tracker] = None
                tier_num += 1
            
        self._db.executemany(sql_insert_torrent_tracker, values, commit=commit)
        
    def updateTorrent(self, infohash, commit=True, **kw):    # watch the schema of database
        if 'category' in kw:
            cat_id = self._getCategoryID(kw.pop('category'))
            kw['category_id'] = cat_id
        if 'status' in kw:
            status_id = self._getStatusID(kw.pop('status'))
            kw['status_id'] = status_id
        if 'progress' in kw:
            self.mypref_db.updateProgress(infohash, kw.pop('progress'), commit=False)# commit at end of function
        if 'seeder' in kw:
            kw['num_seeders'] = kw.pop('seeder')
        if 'leecher' in kw:
            kw['num_leechers'] = kw.pop('leecher')
        if 'last_check_time' in kw or 'ignore_number' in kw or 'retry_number' in kw \
          or 'retried_times' in kw or 'ignored_times' in kw:
            self.updateTracker(infohash, kw, commit=False)
        
        for key in kw.keys():
            if key not in self.keys:
                kw.pop(key)
                
        if len(kw) > 0:
            infohash_str = bin2str(infohash)
            where = "infohash='%s'"%infohash_str
            self._db.update(self.table_name, where, commit=False, **kw)
            
        if commit:
            self.commit()
            # to.do: update the torrent panel's number of seeders/leechers 
        self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)
        
    def updateTracker(self, infohash, kw, tier=1, tracker=None, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        update = {}
        assert type(kw) == dict and kw, 'updateTracker error: kw should be filled dict, but is: %s' % kw
        if 'last_check_time' in kw:
            update['last_check'] = kw.pop('last_check_time')
        if 'ignore_number' in kw:
            update['ignored_times'] = kw.pop('ignore_number')
        if 'ignored_times' in kw:
            update['ignored_times'] = kw.pop('ignored_times')
        if 'retry_number' in kw:
            update['retried_times'] = kw.pop('retry_number')
        if 'retried_times' in kw:
            update['retried_times'] = kw.pop('retried_times')
            
        if tracker is None:
            where = 'torrent_id=%d AND announce_tier=%d'%(torrent_id, tier)
        else:
            where = 'torrent_id=%d AND tracker=%s'%(torrent_id, repr(tracker))
        self._db.update('TorrentTracker', where, commit=commit, **update)

    def deleteTorrent(self, infohash, delete_file=False, commit = True):
        if not self.hasTorrent(infohash):
            return False
        
        if self.mypref_db.hasMyPreference(infohash):  # don't remove torrents in my pref
            return False

        if delete_file:
            deleted = self.eraseTorrentFile(infohash)
        else:
            deleted = True
        
        if deleted:
            self._deleteTorrent(infohash, commit=commit)
            
        self.notifier.notify(NTFY_TORRENTS, NTFY_DELETE, infohash)
        return deleted

    def _deleteTorrent(self, infohash, keep_infohash=True, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            if keep_infohash:
                self._db.update(self.table_name, where="torrent_id=%d"%torrent_id, commit=commit, torrent_file_name=None)
            else:
                self._db.delete(self.table_name, commit=commit, torrent_id=torrent_id)
            if infohash in self.existed_torrents:
                self.existed_torrents.remove(infohash)
            self._db.delete('TorrentTracker', commit=commit, torrent_id=torrent_id)
            #print '******* delete torrent', torrent_id, `infohash`, self.hasTorrent(infohash)
            
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
        return self.torrent_dir
    
    
    def getTorrent(self, infohash, keys=None, include_mypref=True):
        # to do: replace keys like source -> source_id and status-> status_id ??
        
        if keys is None:
            keys = deepcopy(self.value_name)
            #('torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
            # 'num_leechers', 'num_seeders',   'length', 
            # 'secret', 'insert_time', 'source_id', 'torrent_file_name',
            # 'relevance', 'infohash', 'torrent_id')
        else:
            keys = list(keys)
        where = 'C.torrent_id = T.torrent_id and announce_tier=1 '
        
        res = self._db.getOne('CollectedTorrent C, TorrentTracker T', keys, where=where, infohash=bin2str(infohash))
        if not res:
            return None
        torrent = dict(zip(keys, res))
        if 'source_id' in torrent:
            torrent['source'] = self.id2src[torrent['source_id']]
            del torrent['source_id']
        if 'category_id' in torrent:
            torrent['category'] = [self.id2category[torrent['category_id']]]
            del torrent['category_id']
        if 'status_id' in torrent:
            torrent['status'] = self.id2status[torrent['status_id']]
            del torrent['status_id']
        torrent['infohash'] = infohash
        if 'last_check' in torrent:
            torrent['last_check_time'] = torrent['last_check']
            del torrent['last_check']
        
        if include_mypref:
            tid = torrent['C.torrent_id']
            stats = self.mypref_db.getMyPrefStats(tid)
            del torrent['C.torrent_id']
            if stats:
                torrent['myDownloadHistory'] = True
                torrent['creation_time'] = stats[tid][0]
                torrent['progress'] = stats[tid][1]
                torrent['destination_path'] = stats[tid][2]
                
        return torrent

    def getNumberTorrents(self, category_name = 'all', library = False):
        table = 'CollectedTorrent'
        value = 'count(torrent_id)'
        where = '1 '

        if category_name != 'all':
            where += ' and category_id= %d' % self.category_table.get(category_name.lower(), -1) # unkown category_name returns no torrents
        if library:
            where += ' and torrent_id in (select torrent_id from MyPreference)'
        else:
            where += ' and status_id=%d ' % self.status_table['good']
            # add familyfilter
            where += self.category.get_family_filter_sql(self._getCategoryID)
        
        number = self._db.getOne(table, value, where)
        if not number:
            number = 0
        return number
    
    def getTorrents(self, category_name = 'all', range = None, library = False, sort = None, reverse = False):
        """
        get Torrents of some category and with alive status (opt. not in family filter)
        
        @return Returns a list of dicts with keys: 
            torrent_id, infohash, name, category, status, creation_date, num_files, num_leechers, num_seeders,
            length, secret, insert_time, source, torrent_filename, relevance, simRank, tracker, last_check
            (if in library: myDownloadHistory, download_started, progress, dest_dir)
            
        """
        
        #print >> sys.stderr, 'getTorrents(%s, %s, %s, %s, %s)' % (category_name, range, library, sort, reverse)
        s = time()
        
        value_name = deepcopy(self.value_name)
            
        where = 'T.torrent_id = C.torrent_id and announce_tier=1 '
        
        if category_name != 'all':
            where += ' and category_id= %d' % self.category_table.get(category_name.lower(), -1) # unkown category_name returns no torrents
        if library:
            if sort in value_name:
                where += ' and C.torrent_id in (select torrent_id from MyPreference)'
            else:
                value_name[0] = 'C.torrent_id'
                where += ' and C.torrent_id = M.torrent_id and announce_tier=1'
        else:
            where += ' and status_id=%d ' % self.status_table['good'] # if not library, show only good files
            # add familyfilter
            where += self.category.get_family_filter_sql(self._getCategoryID)
        if range:
            offset= range[0]
            limit = range[1] - range[0]
        else:
            limit = offset = None
        if sort:
            # Arno, 2008-10-6: buggy: not reverse???
            desc = (reverse) and 'desc' or ''
            if sort in ('name'):
                order_by = ' lower(%s) %s' % (sort, desc)
            else:
                order_by = ' %s %s' % (sort, desc)
        else:
            order_by = None
            
        #print >>sys.stderr,"TorrentDBHandler: GET TORRENTS val",value_name,"where",where,"limit",limit,"offset",offset,"order",order_by
        #print_stack
        
        # Must come before query
        ranks = self.getRanks()

        #self._db.show_execute = True
        if library and sort not in value_name:
            res_list = self._db.getAll('CollectedTorrent C, MyPreference M, TorrentTracker T', value_name, where, limit=limit, offset=offset, order_by=order_by)
        else:
            res_list = self._db.getAll('CollectedTorrent C, TorrentTracker T', value_name, where, limit=limit, offset=offset, order_by=order_by)
        #self._db.show_execute = False
        
        mypref_stats = self.mypref_db.getMyPrefStats()
        
        #print >>sys.stderr,"TorrentDBHandler: GET TORRENTS ###################",len(res_list)
        
        torrent_list = self.valuelist2torrentlist(value_name,res_list,ranks,mypref_stats)
        del res_list
        del mypref_stats
        return torrent_list

    def valuelist2torrentlist(self,value_name,res_list,ranks,mypref_stats):
        
        torrent_list = []
        for item in res_list:
            value_name[0] = 'torrent_id'
            torrent = dict(zip(value_name, item))
            
            try:
                torrent['source'] = self.id2src[torrent['source_id']]
            except:
                print_exc()
                # Arno: RSS subscription and id2src issue
                torrent['source'] = 'http://some/RSS/feed'
            
            torrent['category'] = [self.id2category[torrent['category_id']]]
            torrent['status'] = self.id2status[torrent['status_id']]
            torrent['simRank'] = ranksfind(ranks,torrent['infohash'])
            torrent['infohash'] = str2bin(torrent['infohash'])
            #torrent['num_swarm'] = torrent['num_seeders'] + torrent['num_leechers']
            torrent['last_check_time'] = torrent['last_check']
            del torrent['last_check']
            del torrent['source_id']
            del torrent['category_id']
            del torrent['status_id']
            torrent_id = torrent['torrent_id']
            if mypref_stats is not None and torrent_id in mypref_stats:
                # add extra info for torrent in mypref
                torrent['myDownloadHistory'] = True
                data = mypref_stats[torrent_id]  #(create_time,progress,destdir)
                torrent['download_started'] = data[0]
                torrent['progress'] = data[1]
                torrent['destdir'] = data[2]
            
            #print >>sys.stderr,"TorrentDBHandler: GET TORRENTS",`torrent`
                
            torrent_list.append(torrent)
        return  torrent_list
        
    def getRanks(self,):
        value_name = 'infohash'
        order_by = 'relevance desc'
        rankList_size = 20
        where = 'status_id=%d ' % self.status_table['good']
        res_list = self._db.getAll('Torrent', value_name, where = where, limit=rankList_size, order_by=order_by)
        return [a[0] for a in res_list]

    def getNumberCollectedTorrents(self): 
        #return self._db.size('CollectedTorrent')
        return self._db.getOne('CollectedTorrent', 'count(torrent_id)')

    def freeSpace(self, torrents2del):
#        if torrents2del > 100:  # only delete so many torrents each time
#            torrents2del = 100
        sql = """
            select torrent_file_name, torrent_id, infohash, relevance,
                min(relevance,2500) +  min(500,num_leechers) + 4*min(500,num_seeders) - (max(0,min(500,(%d-creation_date)/86400)) ) as weight
            from CollectedTorrent
            where  torrent_id not in (select torrent_id from MyPreference)
            order by weight  
            limit %d  
        """ % (int(time()), torrents2del)
        res_list = self._db.fetchall(sql)
        if len(res_list) == 0: 
            return False
        
        # delete torrents from db
        sql_del_torrent = "delete from Torrent where torrent_id=?"
        sql_del_tracker = "delete from TorrentTracker where torrent_id=?"
        sql_del_pref = "delete from Preference where torrent_id=?"
        tids = [(torrent_id,) for torrent_file_name, torrent_id, infohash, relevance, weight in res_list]

        self._db.executemany(sql_del_torrent, tids, commit=False)
        self._db.executemany(sql_del_tracker, tids, commit=False)
        self._db.executemany(sql_del_pref, tids, commit=False)
        
        self._db.commit()
        
        # but keep the infohash in db to maintain consistence with preference db
        #torrent_id_infohashes = [(torrent_id,infohash_str,relevance) for torrent_file_name, torrent_id, infohash_str, relevance, weight in res_list]
        #sql_insert =  "insert into Torrent (torrent_id, infohash, relevance) values (?,?,?)"
        #self._db.executemany(sql_insert, torrent_id_infohashes, commit=True)
        
        torrent_dir = self.getTorrentDir()
        deleted = 0 # deleted any file?
        for torrent_file_name, torrent_id, infohash, relevance, weight in res_list:
            torrent_path = os.path.join(torrent_dir, torrent_file_name)
            try:
                os.remove(torrent_path)
                print >> sys.stderr, "Erase torrent:", os.path.basename(torrent_path)
                deleted += 1
            except Exception, msg:
                #print >> sys.stderr, "Error in erase torrent", Exception, msg
                pass
        
        self.notifier.notify(NTFY_TORRENTS, NTFY_DELETE, str2bin(infohash)) # refresh gui
        
        return deleted

    def hasMetaData(self, infohash):
        return self.hasTorrent(infohash)
    
    def getTorrentRelevances(self, tids):
        sql = 'SELECT torrent_id, relevance from Torrent WHERE torrent_id in ' + str(tuple(tids))
        return self._db.fetchall(sql)
    
    def updateTorrentRelevance(self, infohash, relevance):
        self.updateTorrent(infohash, relevance=relevance)

    def updateTorrentRelevances(self, tid_rel_pairs, commit=True):
        if len(tid_rel_pairs) > 0:
            sql_update_sims = 'UPDATE Torrent SET relevance=? WHERE torrent_id=?'
            self._db.executemany(sql_update_sims, tid_rel_pairs, commit=commit)
        
    def searchNames(self,kws):
        """ Get all torrents (good and bad) that have the specified keywords in 
        their name.  Return a list of dictionaries. Each dict is in the 
        NEWDBSTANDARD format.
        @param kws A list of keyword strings
        @return A list of dictionaries.
        """ 
        
        mypref_stats = self.mypref_db.getMyPrefStats()

        where = 'C.torrent_id = T.torrent_id and announce_tier=1'        
        for i in range(len(kws)):
            kw = kws[i]
            where += ' and name like "%'+kw+'%"'

        value_name = copy(self.value_name)
        if 'torrent_id' in value_name:
            index = value_name.index('torrent_id')
            value_name.remove('torrent_id')
            value_name.insert(index, 'C.torrent_id')
            
        #print >>sys.stderr,"torrent_db: searchNames: where",where
        res_list = self._db.getAll('CollectedTorrent C, TorrentTracker T', value_name, where)
        #print >>sys.stderr,"torrent_db: searchNames: res",`res_list`
        
        torrent_list = self.valuelist2torrentlist(value_name,res_list,None,mypref_stats)
        del res_list
        del mypref_stats
        
        return torrent_list
            

    def selectTorrentToCollect(self, permid, candidate_list=None):
        """ select a torrent to collect from a given candidate list
        If candidate_list is not present or None, all torrents of 
        this peer will be used for sampling.
        Return: the infohashed of selected torrent
        """
        
        if candidate_list is None:
            sql = """
                select infohash 
                from Torrent,Peer,Preference 
                where Peer.permid==?
                      and Peer.peer_id==Preference.peer_id 
                      and Torrent.torrent_id==Preference.torrent_id 
                      and torrent_file_name is NULL 
                order by relevance desc 
            """
            permid_str = bin2str(permid)
            res = self._db.fetchone(sql, (permid_str,))
        else:
            cand_str = [bin2str(infohash) for infohash in candidate_list]
            s = repr(cand_str).replace('[','(').replace(']',')')
            sql = 'select infohash from Torrent where torrent_file_name is NULL and infohash in ' + s
            sql += ' order by relevance desc'
            res = self._db.fetchone(sql)
        if res is None:
            return None
        return str2bin(res)
        
    def selectTorrentToCheck(self, policy='random', infohash=None, return_value=None):    # for tracker checking
        """ select a torrent to update tracker info (number of seeders and leechers)
        based on the torrent checking policy.
        RETURN: a dictionary containing all useful info.

        Policy 1: Random [policy='random']
           Randomly select a torrent to collect (last_check < 5 min ago)
        
        Policy 2: Oldest (unknown) first [policy='oldest']
           Select the non-dead torrent which was not been checked for the longest time (last_check < 5 min ago)
        
        Policy 3: Popular first [policy='popular']
           Select the non-dead most popular (3*num_seeders+num_leechers) one which has not been checked in last N seconds 
           (The default N = 4 hours, so at most 4h/torrentchecking_interval popular peers)
        """
        
        #import threading
        #print >> sys.stderr, "****** selectTorrentToCheck", threading.currentThread().getName()
        
        if infohash is None:
            # create a view?
            sql = """select T.torrent_id, ignored_times, retried_times, torrent_file_name, infohash, status_id, num_seeders, num_leechers, last_check 
                     from CollectedTorrent T, TorrentTracker TT
                     where TT.torrent_id=T.torrent_id and announce_tier=1 """
            if policy.lower() == 'random':
                ntorrents = self.getNumberCollectedTorrents()
                if ntorrents == 0:
                    rand_pos = 0
                else:                    
                    rand_pos = randint(0, ntorrents-1)
                last_check_threshold = int(time()) - 300
                sql += """and last_check < %d 
                        limit 1 offset %d """%(last_check_threshold, rand_pos)
            elif policy.lower() == 'oldest':
                last_check_threshold = int(time()) - 300
                sql += """ and last_check < %d and status_id <> 2
                         order by last_check
                         limit 1 """%last_check_threshold
            elif policy.lower() == 'popular':
                last_check_threshold = int(time()) - 4*60*60
                sql += """ and last_check < %d and status_id <> 2 
                         order by 3*num_seeders+num_leechers desc
                         limit 1 """%last_check_threshold
            res = self._db.fetchone(sql)
        else:
            sql = """select T.torrent_id, ignored_times, retried_times, torrent_file_name, infohash, status_id, num_seeders, num_leechers, last_check 
                     from CollectedTorrent T, TorrentTracker TT
                     where TT.torrent_id=T.torrent_id and announce_tier=1
                     and infohash=? 
                  """
            infohash_str = bin2str(infohash)
            res = self._db.fetchone(sql, (infohash_str,))
        
        if res:
            torrent_file_name = res[3]
            torrent_dir = self.getTorrentDir()
            torrent_path = os.path.join(torrent_dir, torrent_file_name)
            if res is not None:
                res = {'torrent_id':res[0], 
                       'ignored_times':res[1], 
                       'retried_times':res[2], 
                       'torrent_path':torrent_path,
                       'infohash':str2bin(res[4])
                      }
            return_value['torrent'] = res
        return_value['event'].set()


    def getTorrentsFromSource(self,source):
        """ Get all torrents from the specified Subscription source. 
        Return a list of dictionaries. Each dict is in the NEWDBSTANDARD format.
        """
        id = self._getSourceID(source)

        where = 'C.source_id = %d and C.torrent_id = T.torrent_id and announce_tier=1' % (id)
        # add familyfilter
        where += self.category.get_family_filter_sql(self._getCategoryID)
        
        value_name = deepcopy(self.value_name)

        res_list = self._db.getAll('Torrent C, TorrentTracker T', value_name, where)
        
        torrent_list = self.valuelist2torrentlist(value_name,res_list,None,None)
        del res_list
        
        return torrent_list

        
    def setSecret(self,infohash,secret):
        kw = {'secret': secret}
        self.updateTorrent(infohash, updateFlag=True, **kw)
        

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
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'MyPreference')

        self.status_table = {'good':1, 'unknown':0, 'dead':2}
        self.status_table.update(self._db.getTorrentStatusTable())
        self.status_good = self.status_table['good']
        self.recent_preflist = None
        self.rlock = threading.RLock()
        
    def loadData(self):
        self.rlock.acquire()
        try:
            self.recent_preflist = self._getRecentLivePrefList()
        finally:
            self.rlock.release()
                
    def getMyPrefList(self, order_by=None):
        res = self.getAll('torrent_id', order_by=order_by)
        return [p[0] for p in res]

    def getMyPrefListInfohash(self):
        sql = 'select infohash from Torrent where torrent_id in (select torrent_id from MyPreference)'
        res = self._db.fetchall(sql)
        return [str2bin(p[0]) for p in res]
    
    def getMyPrefStats(self, torrent_id=None):
        # get the full {torrent_id:(create_time,progress,destdir)}
        value_name = ('torrent_id','creation_time','progress','destination_path')
        if torrent_id is not None:
            where = 'torrent_id=%s' % torrent_id
        else:
            where = None
        res = self.getAll(value_name, where)
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
        
    def getRecentLivePrefList(self, num=0):
        if self.recent_preflist is None:
            self.rlock.acquire()
            try:
                if self.recent_preflist is None:
                    self.recent_preflist = self._getRecentLivePrefList()
            finally:
                self.rlock.release()
        if num > 0:
            return self.recent_preflist[:num]
        else:
            return self.recent_preflist
        
    def _getRecentLivePrefList(self, num=0):    # num = 0: all files
        # get recent and live torrents
        sql = """
        select infohash from MyPreference m, Torrent t 
        where m.torrent_id == t.torrent_id 
        and status_id == %d
        order by creation_time desc
        """ % self.status_good

        recent_preflist = self._db.fetchall(sql)
        if recent_preflist is None:
            recent_preflist = []
        else:
            recent_preflist = [str2bin(t[0]) for t in recent_preflist]

        if num != 0:
            return recent_preflist[:num]
        else:
            return recent_preflist

    def hasMyPreference(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return False
        res = self.getOne('torrent_id', torrent_id=torrent_id)
        if res is not None:
            return True
        else:
            return False
            
    def addMyPreference(self, infohash, data, commit=True):
        # keys in data: destination_path, progress, creation_time, torrent_id
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None or self.hasMyPreference(infohash):
            return False
        d = {}
        d['destination_path'] = data.get('destination_path')
        d['progress'] = data.get('progress', 0)
        d['creation_time'] = data.get('creation_time', int(time()))
        d['torrent_id'] = torrent_id
        self._db.insert(self.table_name, commit=commit, **d)
        self.notifier.notify(NTFY_MYPREFERENCES, NTFY_INSERT, infohash)
        self.rlock.acquire()
        try:
            if self.recent_preflist is None:
                self.recent_preflist = self._getRecentLivePrefList()
            else:
                self.recent_preflist.insert(0, infohash)
        finally:
            self.rlock.release()
        return True

    def deletePreference(self, infohash, commit=True):
        # Arno: when deleting a preference, you may also need to do
        # some stuff in BuddyCast: see delMyPref()
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.delete(self.table_name, commit=commit, **{'torrent_id':torrent_id})
        self.notifier.notify(NTFY_MYPREFERENCES, NTFY_DELETE, infohash)
        self.rlock.acquire()
        try:
            if self.recent_preflist is not None and infohash in self.recent_preflist:
                self.recent_preflist.remove(infohash)
        finally:
            self.rlock.release()
            
            
    def updateProgress(self, infohash, progress, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.update(self.table_name, 'torrent_id=%d'%torrent_id, commit=commit, progress=progress)
        #print >> sys.stderr, '********* update progress', `infohash`, progress, commit

#    def getAllTorrentCoccurrence(self):
#        # should be placed in PreferenceDBHandler, but put here to be convenient for TorrentCollecting
#        sql = """select torrent_id, count(torrent_id) as coocurrency from Preference where peer_id in
#            (select peer_id from Preference where torrent_id in 
#            (select torrent_id from MyPreference)) and torrent_id not in 
#            (select torrent_id from MyPreference)
#            group by torrent_id
#            """
#        coccurrence = dict(self._db.fetchall(sql))
#        return coccurrence

        
class BarterCastDBHandler(BasicDBHandler):

    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        
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
        BarterCastDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'BarterCast')
        self.peer_db = PeerDBHandler.getInstance()
           
        if DEBUG:
            print >> sys.stderr, "bartercastdb: MyPermid is ", self.my_permid

        
    def registerSession(self, session):
        self.session = session

        # Retrieve MyPermid
        self.my_permid = session.get_permid()

        # Keep administration of total upload and download
        # (to include in BarterCast message)
        my_peerid = self.getPeerID(self.my_permid)
        
        if my_peerid != None:
            where = "peer_id_from=%s" % (my_peerid)
            item = self.getOne(('sum(uploaded)', 'sum(downloaded)'), where=where)
        else:
            item = None
        
        if item != None and len(item) == 2:
            self.total_up = int(item[0])
            self.total_down = int(item[1])
        else:
            self.total_up = 0
            self.total_down = 0

    
    def getTotals(self):
        return (self.total_up, self.total_down)
                        
    def getName(self, permid):

        if permid == 'non-tribler':
            return "non-tribler"
        elif permid == self.my_permid:
            return "local_tribler"

        name = self.peer_db.getPeer(permid, 'name')
        
        if name == None or name == '':
            return 'peer %s' % show_permid_shorter(permid) 
        else:
            return name

    def getNameByID(self, peer_id):
        permid = self.getPermid(peer_id)
        return self.getName(permid)


    def getPermid(self, peer_id):

        # by convention '-1' is the id of non-tribler peers
        if peer_id == -1:
            return 'non-tribler'
        else:
            return self.peer_db.getPermid(peer_id)


    def getPeerID(self, permid):
        
        # by convention '-1' is the id of non-tribler peers
        if permid == "non-tribler":
            return -1
        else:
            return self.peer_db.getPeerID(permid)

    def getItem(self, (permid_from, permid_to), default=False):

        # ARNODB: now converting back to dbid! just did reverse in getItemList
        peer_id1 = self.getPeerID(permid_from)
        peer_id2 = self.getPeerID(permid_to)
        
        if peer_id1 is None:
            self._db.insertPeer(permid_from) # ARNODB: database write
            peer_id1 = self.getPeerID(permid_from) # ARNODB: database write
        
        if peer_id2 is None:
            self._db.insertPeer(permid_to)
            peer_id2 = self.getPeerID(permid_to)
            
        return self.getItemByIDs((peer_id1,peer_id2),default=default)


    def getItemByIDs(self, (peer_id_from, peer_id_to), default=False):
        if peer_id_from is not None and peer_id_to is not None:
            
            where = "peer_id_from=%s and peer_id_to=%s" % (peer_id_from, peer_id_to)
            item = self.getOne(('downloaded', 'uploaded', 'last_seen'), where=where)
        
            if item is None:
                return None
        
            if len(item) != 3:
                return None
            
            itemdict = {}
            itemdict['downloaded'] = item[0]
            itemdict['uploaded'] = item[1]
            itemdict['last_seen'] = item[2]
            itemdict['peer_id_from'] = peer_id_from
            itemdict['peer_id_to'] = peer_id_to

            return itemdict

        else:
            return None


    def getItemList(self):    # get the list of all peers' permid
        
        keys = self.getAll(('peer_id_from','peer_id_to'))
        # ARNODB: this dbid -> permid translation is more efficiently done
        # on the final top-N list.
        keys = map(lambda (id_from, id_to): (self.getPermid(id_from), self.getPermid(id_to)), keys)
        return keys


    def addItem(self, (permid_from, permid_to), item, commit=True):

#        if value.has_key('last_seen'):    # get the latest last_seen
#            old_last_seen = 0
#            old_data = self.getPeer(permid)
#            if old_data:
#                old_last_seen = old_data.get('last_seen', 0)
#            last_seen = value['last_seen']
#            value['last_seen'] = max(last_seen, old_last_seen)

        # get peer ids
        peer_id1 = self.getPeerID(permid_from)
        peer_id2 = self.getPeerID(permid_to)
                
        # check if they already exist in database; if not: add
        if peer_id1 is None:
            self._db.insertPeer(permid_from)
            peer_id1 = self.getPeerID(permid_from)
        if peer_id2 is None:
            self._db.insertPeer(permid_to)
            peer_id2 = self.getPeerID(permid_to)
            
        item['peer_id_from'] = peer_id1
        item['peer_id_to'] = peer_id2    
            
        self._db.insert(self.table_name, commit=commit, **item)

    def updateItem(self, (permid_from, permid_to), key, value, commit=True):
        
        if DEBUG:
            print >> sys.stderr, "bartercastdb: update (%s, %s) [%s] += %s" % (self.getName(permid_from), self.getName(permid_to), key, str(value))

        itemdict = self.getItem((permid_from, permid_to))

        # if item doesn't exist: add it
        if itemdict == None:
            self.addItem((permid_from, permid_to), {'uploaded':0, 'downloaded': 0, 'last_seen': int(time())}, commit=True)
            itemdict = self.getItem((permid_from, permid_to))

        # get peer ids
        peer_id1 = itemdict['peer_id_from']
        peer_id2 = itemdict['peer_id_to']

        if key in itemdict.keys():
            
            where = "peer_id_from=%s and peer_id_to=%s" % (peer_id1, peer_id2)
            item = {key: value}
            self._db.update(self.table_name, where = where, commit=commit, **item)            

    def incrementItem(self, (permid_from, permid_to), key, value, commit=True):
        if DEBUG:
            print >> sys.stderr, "bartercastdb: increment (%s, %s) [%s] += %s" % (self.getName(permid_from), self.getName(permid_to), key, str(value))

        # adjust total_up and total_down
        if permid_from == self.my_permid:
            if key == 'uploaded':
                self.total_up += int(value)
            if key == 'downloaded':
                self.total_down += int(value)
    
        itemdict = self.getItem((permid_from, permid_to))

        # if item doesn't exist: add it
        if itemdict == None:
            self.addItem((permid_from, permid_to), {'uploaded':0, 'downloaded': 0, 'last_seen': int(time())}, commit=True)
            itemdict = self.getItem((permid_from, permid_to))
            
        # get peer ids
        peer_id1 = itemdict['peer_id_from']
        peer_id2 = itemdict['peer_id_to']

        if key in itemdict.keys():
            old_value = itemdict[key]
            new_value = old_value + value
            
            where = "peer_id_from=%s and peer_id_to=%s" % (peer_id1, peer_id2)

            item = {key: new_value}
            self._db.update(self.table_name, where = where, commit=commit, **item)            
            return new_value

        return None

    def addPeersBatch(self,permids):
        """ Add unknown permids as batch -> single transaction """
        if DEBUG:
            print >> sys.stderr, "bartercastdb: addPeersBatch: n=",len(permids)
        
        for permid in permids:
            peer_id = self.getPeerID(permid)
            # check if they already exist in database; if not: add
            if peer_id is None:
                self._db.insertPeer(permid,commit=False)
        self._db.commit()

    def updateULDL(self, (permid_from, permid_to), ul, dl, commit=True):
        """ Add ul/dl record to database as a single write """
        
        if DEBUG:
            print >> sys.stderr, "bartercastdb: updateULDL (%s, %s) ['ul'] += %s ['dl'] += %s" % (self.getName(permid_from), self.getName(permid_to), str(ul), str(dl))

        itemdict = self.getItem((permid_from, permid_to))

        # if item doesn't exist: add it
        if itemdict == None:
            itemdict =  {'uploaded':ul, 'downloaded': dl, 'last_seen': int(time())}
            self.addItem((permid_from, permid_to), itemdict, commit=commit)
            return

        # get peer ids
        peer_id1 = itemdict['peer_id_from']
        peer_id2 = itemdict['peer_id_to']

        if 'uploaded' in itemdict.keys() and 'downloaded' in itemdict.keys():
            where = "peer_id_from=%s and peer_id_to=%s" % (peer_id1, peer_id2)
            item = {'uploaded': ul, 'downloaded':dl}
            self._db.update(self.table_name, where = where, commit=commit, **item)            



    def getPeerIDPairs(self):
        
        keys = self.getAll(('peer_id_from','peer_id_to'))
        return keys

    # Return (sorted) list of the top N peers with the highest (combined) values for the given keys    
    def getTopNPeers(self, n, local_only = False):
        """ getTopNPeers that uses peer_ids in calculation
        @return a dict containing a 'top' key with a list of (permid,up,down) 
        tuples, a 'total_up', 'total_down', 'tribler_up', 'tribler_down' field. 
        Sizes are in kilobytes.
        """
        if DEBUG:
            print >> sys.stderr, "bartercastdb: getTopNPeers: local = ", local_only
        
        n = max(1, n)
        keys = self.getPeerIDPairs()
        
        my_peer_id = self.getPeerID(self.my_permid)
        if local_only:
            # get only items of my local dealings
            keys = filter(lambda (peer_id_from, peer_id_to): peer_id_to == my_peer_id or peer_id_from == my_peer_id, keys)

        total_up = {}
        total_down = {}

        processed = []

        for (peer_id_from, peer_id_to) in keys:
            
            if (not (peer_id_to, peer_id_from) in processed) and (not peer_id_to == peer_id_from):

                item = self.getItemByIDs((peer_id_from, peer_id_to))
                
                if item is not None:

                    up = item['uploaded'] *1024 # make into bytes
                    down = item['downloaded'] *1024

                    if DEBUG:
                        print >> sys.stderr, "bartercastdb: NUgetTopNPeers: DB entry: (%s, %s) up = %d down = %d" % (self.getNameByID(peer_id_from), self.getNameByID(peer_id_to), up, down)

                    processed.append((peer_id_from, peer_id_to))

                    # fix for multiple my_permids
                    if peer_id_from == -1: # 'non-tribler':
                        peer_id_to = my_peer_id
                    if peer_id_to == -1: # 'non-tribler':
                        peer_id_from = my_peer_id

                    # process peer_id_from
                    total_up[peer_id_from] = total_up.get(peer_id_from, 0) + up
                    total_down[peer_id_from] = total_down.get(peer_id_from, 0) + down

                    # process peer_id_to
                    total_up[peer_id_to] = total_up.get(peer_id_to, 0) + down
                    total_down[peer_id_to] = total_down.get(peer_id_to, 0) +  up

                    
        # create top N peers
        top = []
        min = 0

        for peer_id in total_up.keys():

            up = total_up[peer_id]
            down = total_down[peer_id]

            if DEBUG:
                print >> sys.stderr, "bartercastdb: NUgetTopNPeers: total of %s: up = %d down = %d" % (self.getName(peer_id), up, down)

            # we know rank on total upload?
            value = up

            # check if peer belongs to current top N
            if peer_id != -1 and peer_id != my_peer_id and (len(top) < n or value > min):

                top.append((peer_id, up, down))

                # sort based on value
                top.sort(cmp = lambda (p1, u1, d1), (p2, u2, d2): cmp(u2, u1))

                # if list contains more than N elements: remove the last (=lowest value)
                if len(top) > n:
                    del top[-1]

                # determine new minimum of values    
                min = top[-1][1]

        # Now convert to permid
        permidtop = []
        for peer_id,up,down in top:
            permid = self.getPermid(peer_id)
            permidtop.append((permid,up,down))

        result = {}

        result['top'] = permidtop

        # My total up and download, including interaction with non-tribler peers
        result['total_up'] = total_up.get(my_peer_id, 0)
        result['total_down'] = total_down.get(my_peer_id, 0)

        # My up and download with tribler peers only
        result['tribler_up'] = result['total_up'] - total_down.get(-1, 0) # -1 = 'non-tribler'
        result['tribler_down'] = result['total_down'] - total_up.get(-1, 0) # -1 = 'non-tribler'

        if DEBUG:
            print >> sys.stderr, result

        return result

            

class GUIDBHandler:
    """ All the functions of this class are only (or mostly) used by GUI.
        It is not associated with any db table, but will use any of them
    """
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if GUIDBHandler.__single is None:
            GUIDBHandler.lock.acquire()   
            try:
                if GUIDBHandler.__single is None:
                    GUIDBHandler(*args, **kw)
            finally:
                GUIDBHandler.lock.release()
        return GUIDBHandler.__single
    
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if GUIDBHandler.__single is not None:
            raise RuntimeError, "GUIDBHandler is singleton"
        self._db = SQLiteCacheDB.getInstance()
        self.notifier = Notifier.getInstance()
        GUIDBHandler.__single = self
        
    def getCommonFiles(self, permid):
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return []
        
        sql_get_common_files = """select name from CollectedTorrent where torrent_id in (
                                    select torrent_id from Preference where peer_id=?
                                      and torrent_id in (select torrent_id from MyPreference)
                                    ) and status_id <> 2
                               """ + self.get_family_filter_sql()
        res = self._db.fetchall(sql_get_common_files, (peer_id,))
        return [t[0] for t in res]
        
    def getOtherFiles(self, permid):
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return []
        
        sql_get_other_files = """select infohash,name from CollectedTorrent where torrent_id in (
                                    select torrent_id from Preference where peer_id=?
                                      and torrent_id not in (select torrent_id from MyPreference)
                                    ) and status_id <> 2
                              """ + self.get_family_filter_sql()
        res = self._db.fetchall(sql_get_other_files, (peer_id,))
        return [(str2bin(t[0]),t[1]) for t in res]
    
    def getSimItems(self, infohash, limit):
        # recommendation based on collaborative filtering
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return []
        
        sql_get_sim_files = """
            select infohash, name, status_id, count(P2.torrent_id) c 
             from Preference as P1, Preference as P2, CollectedTorrent as T
             where P1.peer_id=P2.peer_id and T.torrent_id=P2.torrent_id 
             and P2.torrent_id <> P1.torrent_id
             and P1.torrent_id=?
             and P2.torrent_id not in (select torrent_id from MyPreference)
             %s
             group by P2.torrent_id
             order by c desc
             limit ?    
        """ % self.get_family_filter_sql('T')
         
        res = self._db.fetchall(sql_get_sim_files, (torrent_id,limit))
        return [(str2bin(t[0]),t[1], t[2], t[3]) for t in res]
        
    def getSimilarTitles(self, name, limit, infohash, prefix_len=5):
        # recommendation based on similar titles
        name = name.replace("'","`")
        sql_get_sim_files = """
            select infohash, name, status_id from Torrent 
            where name like '%s%%'
             and infohash <> '%s'
             and torrent_id not in (select torrent_id from MyPreference)
             %s
            order by name
             limit ?    
        """ % (name[:prefix_len], bin2str(infohash), self.get_family_filter_sql())
        
        res = self._db.fetchall(sql_get_sim_files, (limit,))
        return [(str2bin(t[0]),t[1], t[2]) for t in res]

    def _how_many_prefix(self):
        """ test how long the prefix is enough to find similar titles """
        # Jie: I found 5 is the best value.
        
        sql = "select name from Torrent where name is not NULL order by name"
        names = self._db.fetchall(sql)
        
        for top in range(3, 10):
            sta = {}
            for line in names:
                prefix = line[0][:top]
                if prefix not in sta:
                    sta[prefix] = 1
                else:
                    sta[prefix] += 1
            
            res = [(v,k) for k,v in sta.items()]
            res.sort()
            res.reverse()
        
            print >> sys.stderr, '------------', top, '-------------'
            for k in res[:10]:
                print >> sys.stderr, k
         
    def get_family_filter_sql(self, table_name=''):
        torrent_db_handler = TorrentDBHandler.getInstance()
        return torrent_db_handler.category.get_family_filter_sql(torrent_db_handler._getCategoryID, table_name=table_name)

    
def doPeerSearchNames(self,dbname,kws):
    """ Get all peers that have the specified keywords in their name. 
    Return a list of dictionaries. Each dict is in the NEWDBSTANDARD format.
    """
    if dbname == 'Peer':
        where = '(Peer.last_connected>0 or Peer.friend=1) and '
    elif dbname == 'Friend':
        where  = ''
    else:
        raise Exception('unknown dbname: %s' % dbname)
    
    # Must come before query
    ranks = self.getRanks()

    for i in range(len(kws)):
        kw = kws[i]
        where += ' name like "%'+kw+'%"'
        if (i+1) != len(kws):
            where += ' and'
            
    # See getGUIPeers()
    value_name = PeerDBHandler.gui_value_name
    
    #print >>sys.stderr,"peer_db: searchNames: sql",where
    res_list = self._db.getAll(dbname, value_name, where)
    #print >>sys.stderr,"peer_db: searchNames: res",res_list
    
    peer_list = []
    for item in res_list:
        #print >>sys.stderr,"peer_db: searchNames: Got Record",`item`
        peer = dict(zip(value_name, item))
        peer['name'] = dunno2unicode(peer['name'])
        peer['simRank'] = ranksfind(ranks,peer['permid'])
        peer['permid'] = str2bin(peer['permid'])
        peer_list.append(peer)
    return peer_list

def ranksfind(ranks,key):
    if ranks is None:
        return -1
    try:
        return ranks.index(key)
    except:
        return -1
    
