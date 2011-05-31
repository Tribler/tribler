# Written by Jie Yang
# Modified by George Milescu
# see LICENSE.txt for license information
# Note for Developers: Please write a unittest in Tribler/Test/test_sqlitecachedbhandler.py 
# for any function you add to database. 
# Please reuse the functions in sqlitecachedb as much as possible

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from copy import deepcopy,copy
from traceback import print_exc
from time import time
from binascii import hexlify
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.TorrentDef import TorrentDef
import sys
import os
import socket
import threading
import base64
import urllib
from random import randint, sample
import math
import re
from sets import Set

from maxflow import Network
from math import atan, pi

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Notifier import Notifier
from Tribler.Core.simpledefs import *
from Tribler.Core.BuddyCast.moderationcast_util import *
from Tribler.Core.Overlay.permid import sign_data, verify_data, permid_for_user
from Tribler.Core.Search.SearchManager import split_into_keywords
from Tribler.Core.Utilities.unicode import name2unicode, dunno2unicode
from Tribler.Category.Category import Category
from Tribler.Core.defaults import DEFAULTPORT

# maxflow constants
MAXFLOW_DISTANCE = 2
ALPHA = float(1)/30000

DEBUG = False
SHOW_ERROR = False

MAX_KEYWORDS_STORED = 5
MAX_KEYWORD_LENGTH = 50

#Rahim:
MAX_POPULARITY_REC_PER_TORRENT = 5 # maximum number of records in popularity table for each torrent
MAX_POPULARITY_REC_PER_TORRENT_PEER = 3 # maximum number of records per each combination of torrent and peer

from Tribler.Core.Search.SearchManager import split_into_keywords

def show_permid_shorter(permid):
    if not permid:
        return 'None'
    s = base64.encodestring(permid).replace("\n","")
    return s[-5:]

class BasicDBHandler:
    def __init__(self,db, table_name): ## self, table_name
        self._db = db ## SQLiteCacheDB.getInstance()
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
        return self._db.getOne(self.table_name, value_name, where=where, conj=conj, **kw)
    
    def getAll(self, value_name, where=None, group_by=None, having=None, order_by=None, limit=None, offset=None, conj='and', **kw):
        return self._db.getAll(self.table_name, value_name, where=where, group_by=group_by, having=having, order_by=order_by, limit=limit, offset=offset, conj=conj, **kw)
    
            
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
        BasicDBHandler.__init__(self,db,'MyInfo') ## self,db,'MyInfo'
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
        BasicDBHandler.__init__(self,db, 'Peer') ## self,db,'Peer'
        
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
                      'connected_times', 'buddycast_times', 'last_connected',
                      'is_local', 'services')
    
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
        BasicDBHandler.__init__(self, db,'Peer') ## self, db ,'Peer'
        self.pref_db = PreferenceDBHandler.getInstance()
        self.online_peers = set()


    def __len__(self):
        return self.size()

    def getPeerID(self, permid):
        return self._db.getPeerID(permid)
    
    def addOrGetPeerID(self, permid):
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            self.addPeer(permid, {})
            peer_id = self._db.getPeerID(permid)

        return peer_id

    def getPeer(self, permid, keys=None):
        if keys is not None:
            res = self.getOne(keys, permid=bin2str(permid))
            return res
        else:
            # return a dictionary
            # make it compatible for calls to old bsddb interface
            value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs', 'num_queries', 
                      'connected_times', 'buddycast_times', 'last_connected', 'last_seen', 'last_buddycast', 'services')

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
        
    # ProxyService_
    #
    def getPeerServices(self, permid):
        permid_str = bin2str(permid)
        services = self.getOne('services', permid=permid_str)
        if services is None:
            services = 0
        return services
    #
    # _ProxyService
        
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
    
    def getLocalPeerList(self, max_peers,minoversion=None): # return a list of peer_ids
        """Return a list of peerids for local nodes, friends first, then random local nodes"""
        
        sql = 'select permid from Peer where is_local=1 '
        if minoversion is not None:
            sql += 'and oversion >= '+str(minoversion)+' '
        sql += 'ORDER BY friend DESC, random() limit %d'%max_peers
        list = []
        for row in self._db.fetchall(sql):
            list.append(base64.b64decode(row[0]))
        return list


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

    def setPeerLocalFlag(self, permid, is_local, commit=True):
        # argv = {"is_local":int(is_local)}
        # updated = self._db.update(self.table_name, 'permid='+repr(bin2str(permid)), **argv)
        # if commit:
        #     self.commit()
        # return updated
        self._db.update(self.table_name, 'permid='+repr(bin2str(permid)), commit=commit, is_local=int(is_local))
    
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
                 num_torrents, num_prefs, num_queries, is_local, services
                 
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
        # Arno, 2008-10-23: Someone disabled ranking of people, why?
            
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
            # Arno, 2010-01-28: Disabled this. Maybe something wrong with setOnline
            # observer.
            #self.checkOnline(peer_list)
            raise ValueError("getGUIPeers get_online parameter currently disabled")
            
            
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
        # Arno, 2010-01-28: Disabled this. Maybe something wrong with setOnline
        # observer. ThreadPool may somehow not be executing the calls to setOnline
        # session.add_observer(self.setOnline, NTFY_PEERS, [NTFY_CONNECTION], None)
        pass
    
    def updatePeerIcon(self, permid, icontype, icondata, commit = True):
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

    def readSuperPeerList(self, filename=u''):
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
                print_exc()
                
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
        BasicDBHandler.__init__(self,db, 'Preference') ## self,db,'Preference'
        
        self.popularity_db = PopularityDBHandler.getInstance()
        
            
    def _getTorrentOwnersID(self, torrent_id):
        sql_get_torrent_owners_id = u"SELECT peer_id FROM Preference WHERE torrent_id==?"
        res = self._db.fetchall(sql_get_torrent_owners_id, (torrent_id,))
        return [t[0] for t in res]
    
    def getPrefList(self, permid, return_infohash=False):
        # get a peer's preference list of infohash or torrent_id according to return_infohash
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return []
        
        if not return_infohash:
            sql_get_peer_prefs_id = u"SELECT torrent_id FROM Preference WHERE peer_id==?"
            res = self._db.fetchall(sql_get_peer_prefs_id, (peer_id,))
            return [t[0] for t in res]
        else:
            sql_get_infohash = u"SELECT infohash FROM Torrent WHERE torrent_id IN (SELECT torrent_id FROM Preference WHERE peer_id==?)"
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
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        # This function should be replaced by addPeerPreferences 
        # peer_permid and prefs are binaries, the peer must have been inserted in Peer table
        # Nicolas: did not change this function as it seems addPreference*s* is getting called
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            print >> sys.stderr, 'PreferenceDBHandler: add preference of a peer which is not existed in Peer table', `permid`
            return
        
        sql_insert_peer_torrent = u"INSERT INTO Preference (peer_id, torrent_id) VALUES (?,?)"        
        torrent_id = self._db.getTorrentID(infohash)
        if not torrent_id:
            self._db.insertInfohash(infohash)
            torrent_id = self._db.getTorrentID(infohash)
        try:
            self._db.execute_write(sql_insert_peer_torrent, (peer_id, torrent_id), commit=commit)
        except Exception, msg:    # duplicated
            print_exc()
            
            

    def addPreferences(self, peer_permid, prefs, recvTime=0.0, is_torrent_id=False, commit=True):
        # peer_permid and prefs are binaries, the peer must have been inserted in Peer table
        # boudewijn: for buddycast version >= OLPROTO_VER_EIGTH the
        # prefs list may contain both strings (indicating an infohash)
        # or dictionaries (indicating an infohash with metadata)
        peer_id = self._db.getPeerID(peer_permid)
        if peer_id is None:
            print >> sys.stderr, 'PreferenceDBHandler: add preference of a peer which is not existed in Peer table', `peer_permid`
            return

        prefs = [type(pref) is str and {"infohash":pref} or pref
                 for pref
                 in prefs]

        if __debug__:
            for pref in prefs:
                assert isinstance(pref["infohash"], str), "INFOHASH has invalid type: %s" % type(pref["infohash"])
                assert len(pref["infohash"]) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(pref["infohash"])

        torrent_id_swarm_size =[]
        torrent_id_prefs =[]
        if is_torrent_id:
            for pref in prefs:
                torrent_id_prefs.append((peer_id, 
                                 pref['torrent_id'], 
                                 pref.get('position', -1), 
                                 pref.get('reranking_strategy', -1)) 
                                )
                #Rahim : Since overlay version 11 swarm size information is 
                # appended and should be added to the database . The code below 
                # does this. torrent_id, recv_time, calc_age, num_seeders, 
                # num_leechers, num_sources
                #
                #torrent_id_swarm_size =[]
                if pref.get('calc_age') is not None:
                    tempAge= pref.get('calc_age')
                    tempSeeders = pref.get('num_seeders')
                    tempLeechers = pref.get('num_leechers') 
                    if tempAge > 0 and tempSeeders >= 0 and tempLeechers >= 0:
                        torrent_id_swarm_size.append([pref['torrent_id'],
                                         recvTime, 
                                         tempAge,  
                                         tempSeeders, 
                                         tempLeechers,
                                         pref.get('num_sources_seen', -1)])# -1 means invalud value 
        else:
            # Nicolas: do not know why this would be called, but let's handle 
            # it smoothly
            torrent_id_prefs = []
            #Rahim: I also don't know when this part is run, I just follow the 
            # way that Nicolas has done.
            #torrent_id_swarm_size = []
            for pref in prefs:
                infohash = pref["infohash"]
                torrent_id = self._db.getTorrentID(infohash)
                if not torrent_id:
                    self._db.insertInfohash(infohash)
                    torrent_id = self._db.getTorrentID(infohash)
                torrent_id_prefs.append((peer_id, torrent_id, -1, -1))
                #Rahim: Amended for handling and adding swarm size info.
                #torrent_id_swarm_size.append((torrent_id, recvTime,0, -1, -1, -1))
                
            
        sql_insert_peer_torrent = u"INSERT INTO Preference (peer_id, torrent_id, click_position, reranking_strategy) VALUES (?,?,?,?)"        
        if len(prefs) > 0:
            try:
                self._db.executemany(sql_insert_peer_torrent, torrent_id_prefs, commit=commit)
                popularity_db = PopularityDBHandler.getInstance()
                if len(torrent_id_swarm_size) > 0:
                    popularity_db.storePeerPopularity(peer_id, torrent_id_swarm_size, commit=commit)
            except Exception, msg:    # duplicated
                print_exc()
                print >> sys.stderr, 'dbhandler: addPreferences:', Exception, msg
                
        # now, store search terms
        
        # Nicolas: if maximum number of search terms is exceeded, abort storing them.
        # Although this may seem a bit strict, this means that something different than a genuine Tribler client
        # is on the other side, so we might rather err on the side of caution here and simply let clicklog go.
        nums_of_search_terms = [len(pref.get('search_terms',[])) for pref in prefs]
        if max(nums_of_search_terms)>MAX_KEYWORDS_STORED:
            if DEBUG:
                print >>sys.stderr, "peer %d exceeds max number %d of keywords per torrent, aborting storing keywords"  % \
                                    (peer_id, MAX_KEYWORDS_STORED)
            return  
        
        all_terms_unclean = set()
        for pref in prefs:
            newterms = set(pref.get('search_terms',[]))
            all_terms_unclean = all_terms_unclean.union(newterms)        
            
        all_terms = [] 
        for term in all_terms_unclean:
            cleanterm = ''
            for i in range(0,len(term)):
                c = term[i]
                if c.isalnum():
                    cleanterm += c
            if len(cleanterm)>0:
                all_terms.append(cleanterm)
        # maybe we haven't received a single key word, no need to loop again over prefs then
        if len(all_terms)==0:
            return
           
        termdb = TermDBHandler.getInstance()
        searchdb = SearchDBHandler.getInstance()
                
        # insert all unknown terms NOW so we can rebuild the index at once
        termdb.bulkInsertTerms(all_terms)         
        
        # get local term ids for terms.
        foreign2local = dict([(str(foreign_term), termdb.getTermID(foreign_term))
                              for foreign_term
                              in all_terms])        
        
        # process torrent data
        for pref in prefs:
            torrent_id = pref.get('torrent_id', None)
            search_terms = pref.get('search_terms', [])
            
            if search_terms==[]:
                continue
            if not torrent_id:
                if DEBUG:
                    print >> sys.stderr, "torrent_id not set, retrieving manually!"
                torrent_id = TorrentDBHandler.getInstance().getTorrentID(infohash)
                
            term_ids = [foreign2local[str(foreign)] for foreign in search_terms if str(foreign) in foreign2local]
            searchdb.storeKeywordsByID(peer_id, torrent_id, term_ids, commit=False)
        if commit:
            searchdb.commit()
    
    def getAllEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("rowid, peer_id, torrent_id, click_position,reranking_strategy", order_by="peer_id, torrent_id")


    def getRecentPeersPrefs(self, key, num=None):
        # get the recently seen peers' preference. used by buddycast
        sql = "select peer_id,torrent_id from Preference where peer_id in (select peer_id from Peer order by %s desc)"%key
        if num is not None:
            sql = sql[:-1] + " limit %d)"%num
        res = self._db.fetchall(sql)
        return res
    
    def getPositionScore(self, torrent_id, keywords):
        """returns a tuple (num, positionScore) stating how many times the torrent id was found in preferences,
           and the average position score, where each click at position i receives 1-(1/i) points"""
           
        if not keywords:
            return (0,0)
           
        term_db = TermDBHandler.getInstance()
        term_ids = [term_db.getTermID(keyword) for keyword in keywords]
        s_term_ids = str(term_ids).replace("[","(").replace("]",")").replace("L","")
        
        # we're not really interested in the peer_id here,
        # just make sure we don't count twice if we hit more than one keyword in a search
        # ... one might treat keywords a bit more strictly here anyway (AND instead of OR)
        sql = """
SELECT DISTINCT Preference.peer_id, Preference.click_position 
FROM Preference 
INNER JOIN ClicklogSearch 
ON 
    Preference.torrent_id = ClicklogSearch.torrent_id 
  AND 
    Preference.peer_id = ClicklogSearch.peer_id 
WHERE 
    ClicklogSearch.term_id IN %s 
  AND
    ClicklogSearch.torrent_id = %s""" % (s_term_ids, torrent_id)
        res = self._db.fetchall(sql)
        scores = [1.0-1.0/float(click_position+1) 
                  for (peer_id, click_position) 
                  in res 
                  if click_position>-1]
        if len(scores)==0:
            return (0,0)
        score = float(sum(scores))/len(scores)
        return (len(scores), score)

        
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
        BasicDBHandler.__init__(self,db, 'Torrent') ## self,db,torrent
        
        self.mypref_db = MyPreferenceDBHandler.getInstance()
        self.votecast_db = VoteCastDBHandler.getInstance()
        
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
        self.existed_torrents = set()


        self.value_name = ['C.torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
                      'num_leechers', 'num_seeders', 'length', 
                      'secret', 'insert_time', 'source_id', 'torrent_file_name',
                      'relevance', 'infohash', 'tracker', 'last_check']

        self.value_name_for_channel = ['C.torrent_id', 'infohash', 'name', 'torrent_file_name', 'length', 'creation_date', 'num_files', 'thumbnail', 'insert_time', 'secret', 'relevance', 'source_id', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'comment'] 
        

    def register(self, category, torrent_dir):
        self.category = category
        self.torrent_dir = torrent_dir
        
    def getTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        return self._db.getTorrentID(infohash)
    
    def getTorrentIDS(self, infohashes):
        for infohash in infohashes:
            assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
            assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        return self._db.getTorrentIDS(infohashes)
    
    def getInfohash(self, torrent_id):
        return self._db.getInfohash(torrent_id)

    def hasTorrent(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if infohash in self.existed_torrents:    #to do: not thread safe
            return True
        infohash_str = bin2str(infohash)
        existed = self._db.getOne('CollectedTorrent', 'torrent_id', infohash=infohash_str)
        if existed is None:
            return False
        else:
            self.existed_torrents.add(infohash)
            return True
    
    def addExternalTorrent(self, torrentdef, source="BC", extra_info={}, commit=True):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        assert torrentdef.is_finalized(), "TORRENTDEF is not finalized"
        if torrentdef.is_finalized():
            infohash = torrentdef.get_infohash()
            if not self.hasTorrent(infohash):
                self._addTorrentToDB(torrentdef, source, extra_info, commit)
                self.notifier.notify(NTFY_TORRENTS, NTFY_INSERT, infohash)
        
    def addInfohash(self, infohash, commit=True):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if self._db.getTorrentID(infohash) is None:
            self._db.insert('Torrent', commit=commit, infohash=bin2str(infohash))
            
    def addOrGetTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            self._db.insert('Torrent', commit=True, infohash=bin2str(infohash), status_id = self._getStatusID("good"))
            torrent_id = self._db.getTorrentID(infohash)
        return torrent_id

    def addOrGetTorrentIDS(self, infohashes):
        if len(infohashes) == 1:
            return [self.addOrGetTorrentID(infohashes[0])]
        
        to_be_inserted = []
        torrent_ids = self._db.getTorrentIDS(infohashes)
        for i in range(len(torrent_ids)):
            torrent_id = torrent_ids[i]
            if torrent_id is None:
                to_be_inserted.append(infohashes[i])
        
        status_id = self._getStatusID("good")
        sql = "INSERT OR IGNORE INTO Torrent (infohash, status_id) VALUES (?, ?)"
        self._db.executemany(sql, [(bin2str(infohash), status_id) for infohash in to_be_inserted])
        return self._db.getTorrentIDS(infohashes)

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

    def _get_database_dict(self, torrentdef, source="BC", extra_info={}):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        assert torrentdef.is_finalized(), "TORRENTDEF is not finalized"
        mime, thumb = torrentdef.get_thumbnail()

        return {"infohash":bin2str(torrentdef.get_infohash()),
                "name":torrentdef.get_name_as_unicode(),
                "torrent_file_name":extra_info.get("filename", None),
                "length":torrentdef.get_length(),
                "creation_date":torrentdef.get_creation_date(),
                "num_files":len(torrentdef.get_files()),
                "thumbnail":bool(thumb),
                "insert_time":long(time()),
                "secret":0, # todo: check if torrent is secret
                "relevance":0.0,
                "source_id":self._getSourceID(source),
                # todo: the category_id is calculated directly from
                # torrentdef.metainfo, the category checker should use
                # the proper torrentdef api
                "category_id":self._getCategoryID(self.category.calculateCategory(torrentdef.metainfo, torrentdef.get_name_as_unicode())),
                "status_id":self._getStatusID(extra_info.get("status", "unknown")),
                "num_seeders":extra_info.get("seeder", -1),
                "num_leechers":extra_info.get("leecher", -1),
                "comment":torrentdef.get_comment_as_unicode()}
    
    def _addTorrentToDB(self, torrentdef, source, extra_info, commit):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        assert torrentdef.is_finalized(), "TORRENTDEF is not finalized"

        # ARNO: protect against injection attacks
        # 27/01/10 Boudewijn: all inserts are done using '?' in the
        # sql query.  The sqlite database will ensure that the values
        # are properly escaped.

        infohash = torrentdef.get_infohash()
        torrent_name = torrentdef.get_name_as_unicode()
        database_dict = self._get_database_dict(torrentdef, source, extra_info)
        
        # see if there is already a torrent in the database with this
        # infohash
        torrent_id = self._db.getTorrentID(infohash)

        if torrent_id is None:  # not in database
            self._db.insert("Torrent", commit=True, **database_dict)
            torrent_id = self._db.getTorrentID(infohash)

        else:    # infohash in db
            where = 'torrent_id = %d' % torrent_id
            self._db.update('Torrent', where=where, commit=False, **database_dict)
        
        # boudewijn: we are using a Set to ensure that all keywords
        # are unique.  no use having the database layer figuring this
        # out when we can do it now, in memory
        keywords = set(split_into_keywords(torrent_name))

        # search through the .torrent file for potential keywords in
        # the filenames, but only add the 50 most used
        filedict = {}
        for filename in torrentdef.get_files_as_unicode():
            for keyword in split_into_keywords(filename):
                filedict[keyword] = filedict.get(keyword, 0) + 1
        
        file_keywords = filedict.keys()
        if len(file_keywords) > 50:
            def popSort(a, b):
                return filedict[a] - filedict[b]
            file_keywords.sort(cmp = popSort, reverse = True)
            file_keywords = file_keywords[:50]
        
        keywords.update(file_keywords)
        #only insert keywords with length 3 or higher (results in a reduction of +/- 18%)
        keywords = [keyword for keyword in keywords if len(keyword) > 2]
        
        # store the keywords in the InvertedIndex table in the database
        if len(keywords) > 0:
            values = [(keyword, torrent_id) for keyword in keywords]
            self._db.executemany(u"INSERT OR IGNORE INTO InvertedIndex VALUES(?, ?)", values, commit=False)
            if DEBUG:
                print >> sys.stderr, "torrentdb: Extending the InvertedIndex table with", len(values), "new keywords for", torrent_name
        
        # vliegendhart: extract terms and bi-term phrase from Torrent and store it
        nb = NetworkBuzzDBHandler.getInstance()
        nb.addTorrent(torrent_id, torrent_name, commit)
        
        self._addTorrentTracker(torrent_id, torrentdef, extra_info, commit=False)
        if commit:
            self.commit()    
        return torrent_id

    def getInfohashFromTorrentName(self, name): ##
        sql = "select infohash from Torrent where name='" + str2bin(name) + "'"
        infohash = self._db.fetchone(sql)
        return infohash

    def _insertNewSrc(self, src, commit=True):
        desc = ''
        if src.startswith('http') and src.endswith('xml'):
            desc = 'RSS'
        self._db.insert('TorrentSource', commit=commit, name=src, description=desc)
        src_id = self._db.getOne('TorrentSource', 'source_id', name=src)
        return src_id

    def _addTorrentTracker(self, torrent_id, torrentdef, extra_info={}, add_all=False, commit=True):
        # Set add_all to True if you want to put all multi-trackers into db.
        # In the current version (4.2) only the main tracker is used.

        announce = torrentdef.get_tracker()
        announce_list = torrentdef.get_tracker_hierarchy()
        self._addTorrentTrackerList(torrent_id, announce, announce_list, extra_info, add_all, commit)
        
    def _addTorrentTrackerList(self, torrent_id, announce, announce_list, extra_info={}, add_all=False, commit=True):
        exist = self._db.getOne('TorrentTracker', 'tracker', torrent_id=torrent_id)
        if exist:
            return
        
        ignore_number = 0
        retry_number = 0
        last_check_time = 0
        if "last_check_time" in extra_info:
            last_check_time = int(time() - extra_info["last_check_time"])
        
        sql_insert_torrent_tracker = """
        INSERT INTO TorrentTracker
        (torrent_id, tracker, announce_tier, 
        ignored_times, retried_times, last_check)
        VALUES (?,?,?, ?,?,?)
        """
        
        values = []
        if announce != None:
            values.append((torrent_id, announce, 1, ignore_number, retry_number, last_check_time))
        
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
        
        if len(values) > 0:
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
                # vliegendhart: synch bi-term phrase table
                nb = NetworkBuzzDBHandler.getInstance()
                nb.deleteTorrent(torrent_id, commit)
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
        
    def getSwarmInfo(self, torrent_id):
        """
        returns info about swarm size from Torrent and TorrentTracker tables.
        @author: Rahim
        @param torrentId: The index of the torrent.
        @return: A list of the form: [torrent_id, num_seeders, num_leechers, last_check, num_sources_seen, sizeInfo]
        """
        if torrent_id is not None:
            dict = self.getSwarmInfos([torrent_id])
            if torrent_id in dict:
                return dict[torrent_id]
    
    def getSwarmInfos(self, torrent_id_list):
        """
        returns infos about swarm size from Torrent and TorrentTracker tables.
        @author: Niels
        @param torrent_id_list: a list containing torrent_ids
        @return: A dictionary of lists of the form: torrent_id => [torrent_id, num_seeders, num_leechers, last_check, num_sources_seen, sizeInfo]
        """
        torrent_id_list = [torrent_id for torrent_id in torrent_id_list if torrent_id]
        
        results = {}
        sql = "SELECT t.torrent_id, t.num_seeders, t.num_leechers, max(last_check) FROM Torrent t, TorrentTracker tr WHERE t.torrent_id in ("
        sql += ','.join(map(str,torrent_id_list))
        sql +=") AND t.torrent_id = tr.torrent_id GROUP BY t.torrent_id"
        
        rows = self._db.fetchall(sql)
        for row in rows:
            torrent_id = row[0]
            num_seeders  = row[1]
            num_leechers = row[2]
            last_check = row[3]
            results[torrent_id] = [torrent_id, num_seeders, num_leechers, last_check, -1, row]
        
        if len(results.keys()) > 0:
            sql= "SELECT torrent_id, COUNT(*) FROM Preference WHERE torrent_id in ("
            sql += ','.join(map(str,results.keys()))
            sql +=") GROUP BY torrent_id"
            
            rows = self._db.fetchall(sql)
            for row in rows:
                results[row[0]][4] = row[1]
        return results
    
    def getLargestSourcesSeen(self, torrent_id, timeNow, freshness=-1):
        """
        Returns the largest number of the sources that have seen the torrent.
        @author: Rahim
        @param torrent_id: the id of the torrent.
        @param freshness: A parameter that filters old records. The assumption is that those popularity reports that are
        older than a rate are not reliable
        @return: The largest number of the torrents that have seen the torrent.
        """
        
        if freshness == -1:
            sql2 = """SELECT MAX(num_of_sources) FROM Popularity WHERE torrent_id=%d"""%torrent_id
        else:
            latestValidTime = timeNow - freshness
            sql2 = """SELECT MAX(num_of_sources) FROM Popularity WHERE torrent_id=%d AND msg_receive_time > %d"""%(torrent_id, latestValidTime) 
        
        othersSeenSources = self._db.fetchone(sql2)
        if othersSeenSources is None:
            othersSeenSources =0
        return othersSeenSources 
        
    def getTorrentDir(self):
        return self.torrent_dir
    
    def updateTorrentDir(self, torrent_dir):
        sql = "SELECT torrent_id, torrent_file_name FROM Torrent WHERE torrent_file_name not NULL"
        results = self._db.fetchall(sql)
        
        updates = []
        for result in results:
            head, tail = os.path.split(result[1])
            new_file_name = os.path.join(torrent_dir, tail)
            
            updates.append((new_file_name, result[0]))
        sql = "UPDATE TORRENT SET torrent_file_name = ? WHERE torrent_id = ?"
        self._db.executemany(sql, updates)
        
        self.torrent_dir = torrent_dir
    
    def getTorrent(self, infohash, keys=None, include_mypref=True):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
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
            where += ' and torrent_id in (select torrent_id from MyPreference where destination_path != "")'
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
        
        niels 25-10-2010: changed behaviour to left join TorrentTracker, due to magnet links
        """
        
        #print >> sys.stderr, 'TorrentDBHandler: getTorrents(%s, %s, %s, %s, %s)' % (category_name, range, library, sort, reverse)
        s = time()
        
        value_name = deepcopy(self.value_name)
        
        
        sql = 'Select '+','.join(value_name)
        sql += ' From CollectedTorrent C Left Join TorrentTracker T ON C.torrent_id = T.torrent_id'
        
        where = ''
        if category_name != 'all':
            where += 'category_id = %d AND' % self.category_table.get(category_name.lower(), -1) # unkown category_name returns no torrents
            
        if library:
            where += 'C.torrent_id in (select torrent_id from MyPreference where destination_path != "")'
        else:
            where += 'status_id=%d ' % self.status_table['good'] # if not library, show only good files
            # add familyfilter
            where += self.category.get_family_filter_sql(self._getCategoryID)
        
        sql += ' Where '+where
        
        if range:
            offset= range[0]
            limit = range[1] - range[0]
            sql += ' Limit %d Offset %d'%(limit, offset)
            
        if sort:
            # Arno, 2008-10-6: buggy: not reverse???
            desc = (reverse) and 'desc' or ''
            if sort in ('name'):
                sql += ' Order By lower(%s) %s' % (sort, desc)
            else:
                sql += ' Order By %s %s' % (sort, desc)
            
        #print >>sys.stderr,"TorrentDBHandler: GET TORRENTS val",value_name,"where",where,"limit",limit,"offset",offset,"order",order_by
        #print_stack
        
        # Must come before query
        ranks = self.getRanks()
        
        res_list = self._db.fetchall(sql)
        
        mypref_stats = self.mypref_db.getMyPrefStats()
        
        #print >>sys.stderr,"TorrentDBHandler: getTorrents: getAll returned ###################",len(res_list)
        
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
        
    def getRanks(self):
        value_name = 'infohash'
        order_by = 'relevance desc'
        rankList_size = 20
        where = 'status_id=%d ' % self.status_table['good']
        res_list = self._db.getAll('Torrent', value_name, where = where, limit=rankList_size, order_by=order_by)
        return [a[0] for a in res_list]

    def getNumberCollectedTorrents(self): 
        #return self._db.size('CollectedTorrent')
        return self._db.getOne('CollectedTorrent', 'count(torrent_id)')
    
    def getTorrentsStats(self):
        return self._db.getOne('CollectedTorrent', ['count(torrent_id)','sum(length)','sum(num_files)'])

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
    
    def searchNames(self,kws,local=True):
        t1 = time()
        value_name = ['torrent_id',
                      'infohash',
                      'name',
                       'torrent_file_name',                        
                       'length', 
                       'creation_date', 
                       'num_files',
                       'thumbnail',                       
                      'insert_time', 
                      'secret', 
                      'relevance',  
                      'source_id', 
                      'category_id', 
                       'status_id',
                       'num_seeders',
                      'num_leechers', 
                      'comment',
                      'channel_permid',
                      'channel_name']        
        
        sql = ""
        count = 0
        for word in kws:
            word = word.lower()
            count += 1
            sql += " select torrent_id from InvertedIndex where word='" + word + "' "
            if count < len(kws):
                sql += " intersect "
        
        #TODO: channel remote search?
        mainsql = """select T.*, '' as channel_permid, '' as channel_name 
                     from Torrent T
                     where T.torrent_id in (%s) order by T.num_seeders desc """ % (sql)
        if not local:
            mainsql += " limit 20"
            
        results = self._db.fetchall(mainsql)
        
        t2 = time()
        votes = self.votecast_db.getAllPosNegVotes()
        t3 = time()
        
        torrents_dict = {}
        for result in results:
            a = time()
            torrent = dict(zip(value_name,result))
            
            #bug fix: If channel_permid and/or channel_name is None, it cannot bencode
            #bencode(None) is an Error
            if torrent['channel_permid'] is None:
                torrent['channel_permid'] = ""
            if torrent['channel_name'] is None:
                torrent['channel_name'] = ""
                            
            # check if this torrent belongs to more than one channel
            if torrent['infohash'] in torrents_dict:
                old_record = torrents_dict[torrent['infohash']]
                # check if this channel has votes and if so, is it better than previous channel
                if torrent['channel_permid'] in votes:
                    numsubscriptions, negvotes = votes[torrent['channel_permid']] 
                    if numsubscriptions-negvotes > old_record['subscriptions'] - old_record['neg_votes']:
                        #print >> sys.stderr, "overridden", torrent['channel_name'], old_record['channel_name']
                        old_record['channel_permid'] = torrent['channel_permid']
                        old_record['channel_name'] = torrent['channel_name']
                        old_record['subscriptions'] = numsubscriptions
                        old_record['neg_votes'] = negvotes
                else:
                    if old_record['subscriptions'] - old_record['neg_votes'] < 0: # SPAM cutoff
                        old_record['channel_permid'] = torrent['channel_permid']
                        old_record['channel_name'] = torrent['channel_name']
                        old_record['subscriptions'] = 0
                        old_record['neg_votes'] = 0
                continue
            
            torrents_dict[torrent['infohash']] = torrent
            try:
                torrent['source'] = self.id2src[torrent['source_id']]
            except:
                print_exc()
                # Arno: RSS subscription and id2src issue
                torrent['source'] = 'http://some/RSS/feed'
            
            torrent['category'] = [self.id2category[torrent['category_id']]]
            torrent['status'] = self.id2status[torrent['status_id']]
            torrent['simRank'] = ranksfind(None,torrent['infohash'])
            torrent['infohash'] = str2bin(torrent['infohash'])
            #torrent['num_swarm'] = torrent['num_seeders'] + torrent['num_leechers']
            torrent['last_check_time'] = 0 #torrent['last_check']
            #del torrent['last_check']
            del torrent['source_id']
            del torrent['category_id']
            del torrent['status_id']
            torrent_id = torrent['torrent_id']
            
            torrent['neg_votes']=0
            torrent['subscriptions']=0
            if torrent['channel_permid'] in votes:
                sum, count = votes[torrent['channel_permid']]
                numsubscriptions = (sum + count)/3
                negvotes = (2*count-sum)/3                
                torrent['neg_votes']=negvotes
                torrent['subscriptions']=numsubscriptions
            
            #print >> sys.stderr, "hello.. %.3f,%.3f" %((time()-a), time())
        def compare(a,b):
            return -1*cmp(a['num_seeders'], b['num_seeders'])
        torrent_list = torrents_dict.values()
        torrent_list.sort(compare)
        #print >> sys.stderr, "# hits:%d; search time:%.3f,%.3f,%.3f" % (len(torrent_list),t2-t1, t3-t2, time()-t1 )
        return torrent_list


    def selectTorrentsToCollect(self, permid, candidate_list=None, similarity_list_size=50, list_size=1):
        """ 
        select a torrent to collect from a given candidate list
        If candidate_list is not present or None, all torrents of 
        this peer will be used for sampling.
        Return: the infohashed of selected torrent
        """
        
        if candidate_list is None:
            sql = """SELECT similarity, infohash FROM Peer, Preference, Torrent
                     WHERE Peer.peer_id = Preference.peer_id
                     AND Torrent.torrent_id = Preference.torrent_id
                     AND Peer.peer_id IN(Select peer_id from Peer WHERE similarity > 0 ORDER By similarity DESC,last_connected DESC Limit ?)
                     AND Preference.torrent_id IN(Select torrent_id from Peer, Preference WHERE Peer.peer_id = Preference.peer_id AND Peer.permid = ?)
                     AND torrent_file_name is NULL
                  """
            permid_str = bin2str(permid)
            results = self._db.fetchall(sql, (similarity_list_size, permid_str))
        else:
            #print >>sys.stderr,"torrentdb: selectTorrentToCollect: cands",`candidate_list`
            
            cand_str = [bin2str(infohash) for infohash in candidate_list]
            s = repr(cand_str).replace('[','(').replace(']',')')
            sql = """SELECT similarity, infohash FROM Peer, Preference, Torrent
                     WHERE Peer.peer_id = Preference.peer_id
                     AND Torrent.torrent_id = Preference.torrent_id
                     AND Peer.peer_id IN(Select peer_id from Peer WHERE similarity > 0 ORDER By similarity DESC Limit ?)
                     AND infohash in """+s+"""
                     AND torrent_file_name is NULL
                  """
            results = self._db.fetchall(sql, (similarity_list_size,))
        
        #convert top-x similarities into item recommendations
        infohashes = {}
        for sim, infohash in results:
            infohashes[infohash] = infohashes.get(infohash,0) + sim
        
        res = []
        keys = infohashes.keys()
        if len(keys) > 0:
            keys.sort(lambda a,b: cmp(infohashes[b], infohashes[a]))
            
            #add all items with highest relevance to candidate_list
            candidate_list = []
            for infohash in keys:
                if infohashes[infohash] == infohashes[keys[0]]:
                    candidate_list.append(str2bin(infohash))

            #if only 1 candidate use that as result
            if len(candidate_list) <= list_size:
                res = filter(lambda x: not x is None, keys[:list_size])
                candidate_list = None

        #No torrent found with relevance, fallback to most downloaded torrent
        if len(res) < list_size:
            if candidate_list is None or len(candidate_list) == 0:
                sql = """SELECT infohash FROM Torrent, Peer, Preference
                         WHERE Peer.permid == ?  
                         AND Peer.peer_id == Preference.peer_id 
                         AND Torrent.torrent_id == Preference.torrent_id
                         AND torrent_file_name is NULL
                         GROUP BY Preference.torrent_id
                         ORDER BY Count(Preference.torrent_id) DESC
                         LIMIT ?"""
                permid_str = bin2str(permid)
                res.extend([infohash for infohash, in self._db.fetchall(sql, (permid_str, list_size - len(res)))])
            else:
                cand_str = [bin2str(infohash) for infohash in candidate_list]
                s = repr(cand_str).replace('[','(').replace(']',')')
                sql = """SELECT infohash FROM Torrent, Preference
                         WHERE Torrent.torrent_id == Preference.torrent_id
                         AND torrent_file_name is NULL
                         AND infohash IN """ + s + """
                         GROUP BY Preference.torrent_id
                         ORDER BY Count(Preference.torrent_id) DESC
                         LIMIT ?"""
                res.extend([infohash for infohash, in self._db.fetchall(sql, (list_size - len(res),))])

        return [str2bin(infohash) for infohash in res if not infohash is None]
        
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
    
    def getTorrentFiles(self, torrent_id):
        sql = "SELECT path, length FROM TorrentFiles WHERE torrent_id = ?"
        return self._db.fetchall(sql, (torrent_id, ))

    def getTorrentCollecting(self, torrent_id):
        sql = "SELECT source FROM TorrentCollecting WHERE torrent_id = ?"
        return self._db.fetchall(sql, (torrent_id, ))
        
    def setSecret(self,infohash,secret):
        kw = {'secret': secret}
        self.updateTorrent(infohash, commit=True, **kw)
        

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
        BasicDBHandler.__init__(self,db, 'MyPreference') ## self,db,'MyPreference'

        self.status_table = {'good':1, 'unknown':0, 'dead':2}
        self.status_table.update(self._db.getTorrentStatusTable())
        self.status_good = self.status_table['good']
        # Arno, 2010-02-04: ARNOCOMMENT ARNOTODO Get rid of this g*dd*mn caching
        # or keep it consistent with the DB!
        self.recent_preflist = None
        self.recent_preflist_with_clicklog = None
        self.recent_preflist_with_swarmsize = None
        self.rlock = threading.RLock()
        
        self.popularity_db = PopularityDBHandler.getInstance()
        
        
    def loadData(self):
        """ Arno, 2010-02-04: Brute force update method for the self.recent_
        caches, because people don't seem to understand that caches need
        to be kept consistent with the database. Caches are evil in the first place.
        """
        self.rlock.acquire()
        try:
            self.recent_preflist = self._getRecentLivePrefList()
            self.recent_preflist_with_clicklog = self._getRecentLivePrefListWithClicklog()
            self.recent_preflist_with_swarmsize = self._getRecentLivePrefListOL11()
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

    def getRecentLivePrefListWithClicklog(self, num=0):
        """returns OL 8 style preference list: a list of lists, with each of the inner lists
           containing infohash, search terms, click position, and reranking strategy"""
           
        if self.recent_preflist_with_clicklog is None:
            self.rlock.acquire()
            try:
                if self.recent_preflist_with_clicklog is None:
                    self.recent_preflist_with_clicklog = self._getRecentLivePrefListWithClicklog()
            finally:
                self.rlock.release()
        if num > 0:
            return self.recent_preflist_with_clicklog[:num]
        else:
            return self.recent_preflist_with_clicklog  

    def getRecentLivePrefListOL11(self, num=0):
        """
        Returns OL 11 style preference list. It contains all info from previous 
        versions like clickLog info and some additional info related to swarm size.
        @author: Rahim
        @param num: if num be equal to zero the lenghth of the return list is unlimited, otherwise it's maximum lenght will be num.
        @return: a list of lists. Each inner list is like:
        [previous info , num_seeders, num_leechers, swarm_size_calc_age, number_of_sources]
        """
        if self.recent_preflist_with_swarmsize is None:
            self.rlock.acquire()
            try:
                #if self.recent_preflist_with_swarmsize is None:
                self.recent_preflist_with_swarmsize = self._getRecentLivePrefListOL11()
            finally:
                self.rlock.release()
        if num > 0:
            return self.recent_preflist_with_swarmsize[:num]
        else:
            return self.recent_preflist_with_swarmsize  
        
        
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


        
    def addClicklogToMyPreference(self, infohash, clicklog_data, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        clicklog_already_stored = False # equivalent to hasMyPreference TODO
        if torrent_id is None or clicklog_already_stored:
            return False

        d = {}
        # copy those elements of the clicklog data which are used in the update command
        for clicklog_key in ["click_position", "reranking_strategy"]: 
            if clicklog_key in clicklog_data: 
                d[clicklog_key] = clicklog_data[clicklog_key]
                                
        if d=={}:
            if DEBUG:
                print >> sys.stderr, "no updatable information given to addClicklogToMyPreference"
        else:
            if DEBUG:
                print >> sys.stderr, "addClicklogToMyPreference: updatable clicklog data: %s" % d
            self._db.update(self.table_name, 'torrent_id=%d' % torrent_id, commit=commit, **d)
                
        # have keywords stored by SearchDBHandler
        if 'keywords' in clicklog_data:
            if not clicklog_data['keywords']==[]:
                searchdb = SearchDBHandler.getInstance() 
                searchdb.storeKeywords(peer_id=0, 
                                       torrent_id=torrent_id, 
                                       terms=clicklog_data['keywords'], 
                                       commit=commit)   
 
                    
        
    def _getRecentLivePrefListWithClicklog(self, num=0):
        """returns a list containing a list for each torrent: [infohash, [seach terms], click position, reranking strategy]"""
        
        sql = """
        select infohash, click_position, reranking_strategy, m.torrent_id from MyPreference m, Torrent t 
        where m.torrent_id == t.torrent_id 
        and status_id == %d
        order by creation_time desc
        """ % self.status_good
        
        recent_preflist_with_clicklog = self._db.fetchall(sql)
        if recent_preflist_with_clicklog is None:
            recent_preflist_with_clicklog = []
        else:
            recent_preflist_with_clicklog = [[str2bin(t[0]),
                                              t[3],   # insert search terms in next step, only for those actually required, store torrent id for now
                                              t[1], # click position
                                              t[2]]  # reranking strategy
                                             for t in recent_preflist_with_clicklog]

        if num != 0:
            recent_preflist_with_clicklog = recent_preflist_with_clicklog[:num]

        # now that we only have those torrents left in which we are actually interested, 
        # replace torrent id by user's search terms for torrent id
        termdb = TermDBHandler.getInstance()
        searchdb = SearchDBHandler.getInstance()
        for pref in recent_preflist_with_clicklog:
            torrent_id = pref[1]
            search_terms = [term.encode("UTF-8") for term, in searchdb.getMyTorrentSearchTermsStr(torrent_id)]

            # Arno, 2010-02-02: Explicit encoding
            pref[1] = search_terms

        return recent_preflist_with_clicklog

    def searchterms2utf8pref(self,termdb,search_terms):            
        terms = [termdb.getTerm(search_term) for search_term in search_terms]
        eterms = []
        for term in terms:
            eterms.append(term.encode("UTF-8"))
        return eterms
    
    
    def _getRecentLivePrefListOL11(self, num=0): 
        """
        first calls the previous method to get a list of torrents and related info from MyPreference db 
        (_getRecentLivePrefListWithClicklog) and then appendes it with swarm size info or ( num_seeders, num_leechers, calc_age, num_seeders).
        @author: Rahim
        @param num: if num=0 it returns all items otherwise it restricts the return result to num.
        @return: a list that each item conatins below info:
        [infohash, [seach terms], click position, reranking strategy, num_seeders, num_leechers, calc_age, num_of_sources] 
        """
        
        sql = """
        select infohash, click_position, reranking_strategy, m.torrent_id from MyPreference m, Torrent t 
        where m.torrent_id == t.torrent_id 
        and status_id == %d
        order by creation_time desc
        """ % self.status_good
        
        recent_preflist_with_swarmsize = self._db.fetchall(sql)
        if recent_preflist_with_swarmsize is None:
            recent_preflist_with_swarmsize = []
        else:
            recent_preflist_with_swarmsize = [[str2bin(t[0]),
                                              t[3],   # insert search terms in next step, only for those actually required, store torrent id for now
                                              t[1], # click position
                                              t[2]]  # reranking strategy
                                             for t in recent_preflist_with_swarmsize]

        if num != 0:
            recent_preflist_with_swarmsize = recent_preflist_with_swarmsize[:num]

        # now that we only have those torrents left in which we are actually interested, 
        # replace torrent id by user's search terms for torrent id
        termdb = TermDBHandler.getInstance()
        searchdb = SearchDBHandler.getInstance()
        tempTorrentList = []
        for pref in recent_preflist_with_swarmsize:
            torrent_id = pref[1]
            tempTorrentList.append(torrent_id)
            
            # Arno, 2010-02-02: Explicit encoding
            search_terms = [term.encode("UTF-8") for term, in searchdb.getMyTorrentSearchTermsStr(torrent_id)]
            pref[1] = search_terms
        
        #Step 3: appending swarm size info to the end of the inner lists
        swarmSizeInfoList= self.popularity_db.calculateSwarmSize(tempTorrentList, 'TorrentIds', toBC=True) # returns a list of items [torrent_id, num_seeders, num_leechers, num_sources_seen]

        index = 0
        for  index in range(0,len(swarmSizeInfoList)):
            recent_preflist_with_swarmsize[index].append(swarmSizeInfoList[index][1]) # number of seeders
            recent_preflist_with_swarmsize[index].append(swarmSizeInfoList[index][2])# number of leechers
            recent_preflist_with_swarmsize[index].append(swarmSizeInfoList[index][3])  # age of the report 
            recent_preflist_with_swarmsize[index].append(swarmSizeInfoList[index][4]) # number of sources seen this torrent 
        return recent_preflist_with_swarmsize
        
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
            # Arno, 2009-03-09: Torrent already exists in myrefs.
            # Hack for hiding from lib while keeping in myprefs.
            # see standardOverview.removeTorrentFromLibrary()
            #
            self.updateDestDir(infohash,data.get('destination_path'),commit=commit)
            self.notifier.notify(NTFY_MYPREFERENCES, NTFY_UPDATE, infohash)
            return False
        d = {}
        d['destination_path'] = data.get('destination_path')
        d['progress'] = data.get('progress', 0)
        d['creation_time'] = data.get('creation_time', int(time()))
        d['torrent_id'] = torrent_id

        self._db.insert(self.table_name, commit=commit, **d)
        self.notifier.notify(NTFY_MYPREFERENCES, NTFY_INSERT, infohash)
        
        # Arno, 2010-02-04: Update self.recent_ caches :-(
        self.loadData()

        return True

    def deletePreference(self, infohash, commit=True):
        # Arno: when deleting a preference, you may also need to do
        # some stuff in BuddyCast: see delMyPref()
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.delete(self.table_name, commit=commit, **{'torrent_id':torrent_id})
        self.notifier.notify(NTFY_MYPREFERENCES, NTFY_DELETE, infohash)

        # Arno, 2010-02-04: Update self.recent_ caches :-(
        self.loadData()
            
            
    def updateProgress(self, infohash, progress, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.update(self.table_name, 'torrent_id=%d'%torrent_id, commit=commit, progress=progress)
        #print >> sys.stderr, '********* update progress', `infohash`, progress, commit

    def getAllEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("torrent_id, click_position, reranking_strategy", order_by="torrent_id")

    def updateDestDir(self, infohash, destdir, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        self._db.update(self.table_name, 'torrent_id=%d'%torrent_id, commit=commit, destination_path=destdir)
    

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
        BasicDBHandler.__init__(self, db,'BarterCast') ## self,db,'BarterCast'
        self.peer_db = PeerDBHandler.getInstance()
        
        # create the maxflow network
        self.network = Network({})
        self.update_network()
                   
        if DEBUG:
            print >> sys.stderr, "bartercastdb:"

        
    ##def registerSession(self, session):
    ##    self.session = session

        # Retrieve MyPermid
    ##    self.my_permid = session.get_permid()


    def registerSession(self, session):
        self.session = session

        # Retrieve MyPermid
        self.my_permid = session.get_permid()

        if DEBUG:
            print >> sys.stderr, "bartercastdb: MyPermid is ", `self.my_permid`

        if self.my_permid is None:
            raise ValueError('Cannot get permid from Session')

        # Keep administration of total upload and download
        # (to include in BarterCast message)
        self.my_peerid = self.getPeerID(self.my_permid)
        
        if self.my_peerid != None:
            where = "peer_id_from=%s" % (self.my_peerid)
            item = self.getOne(('sum(uploaded)', 'sum(downloaded)'), where=where)
        else:
            item = None
        
        if item != None and len(item) == 2 and item[0] != None and item[1] != None:
            self.total_up = int(item[0])
            self.total_down = int(item[1])
        else:
            self.total_up = 0
            self.total_down = 0
            
#         if DEBUG:
#             print >> sys.stderr, "My reputation: ", self.getMyReputation()
            
    
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
        
    def getTopNPeers(self, n, local_only = False):
        """
        Return (sorted) list of the top N peers with the highest (combined) 
        values for the given keys. This version uses batched reads and peer_ids
        in calculation
        @return a dict containing a 'top' key with a list of (permid,up,down) 
        tuples, a 'total_up', 'total_down', 'tribler_up', 'tribler_down' field. 
        Sizes are in kilobytes.
        """
        
        # TODO: this won't scale to many interactions, as the size of the DB
        # is NxN
        
        if DEBUG:
            print >> sys.stderr, "bartercastdb: getTopNPeers: local = ", local_only
            #print_stack()
        
        n = max(1, n)
        my_peer_id = self.getPeerID(self.my_permid)
        total_up = {}
        total_down = {}
        # Arno, 2008-10-30: I speculate this is to count transfers only once,
        # i.e. the DB stored (a,b) and (b,a) and we want to count just one.
        
        processed =  set()
        

        value_name = '*'
        increment = 500
        
        nrecs = self.size()
        #print >>sys.stderr,"NEXTtopN: size is",nrecs
        
        for offset in range(0,nrecs,increment):
            if offset+increment > nrecs:
                limit = nrecs-offset
            else:
                limit = increment
            #print >>sys.stderr,"NEXTtopN: get",offset,limit
        
            reslist = self.getAll(value_name, offset=offset, limit=limit)
            #print >>sys.stderr,"NEXTtopN: res len is",len(reslist),`reslist`
            for res in reslist:
                (peer_id_from,peer_id_to,downloaded,uploaded,last_seen,value) = res
            
                if local_only:
                    if not (peer_id_to == my_peer_id or peer_id_from == my_peer_id):
                        # get only items of my local dealings
                        continue
                        
                if (not (peer_id_to, peer_id_from) in processed) and (not peer_id_to == peer_id_from):
                #if (not peer_id_to == peer_id_from):
        
                    up = uploaded *1024 # make into bytes
                    down = downloaded *1024
    
                    if DEBUG:
                        print >> sys.stderr, "bartercastdb: getTopNPeers: DB entry: (%s, %s) up = %d down = %d" % (self.getNameByID(peer_id_from), self.getNameByID(peer_id_to), up, down)
    
                    processed.add((peer_id_from, peer_id_to))
    
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
                print >> sys.stderr, "bartercastdb: getTopNPeers: total of %s: up = %d down = %d" % (self.getName(peer_id), up, down)

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
        
        
    ################################
    def update_network(self):


        keys = self.getPeerIDPairs() #getItemList()


    ################################
    def getMyReputation(self, alpha = ALPHA):

        rep = atan((self.total_up - self.total_down) * alpha)/(0.5 * pi)
        return rep   


class VoteCastDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        
        if VoteCastDBHandler.__single is None:
            VoteCastDBHandler.lock.acquire()   
            try:
                if VoteCastDBHandler.__single is None:
                    VoteCastDBHandler(*args, **kw)
            finally:
                VoteCastDBHandler.lock.release()
        return VoteCastDBHandler.__single
    
    getInstance = staticmethod(getInstance)

    def __init__(self):
        VoteCastDBHandler.__single = self
        try:
            db = SQLiteCacheDB.getInstance()
            BasicDBHandler.__init__(self,db,'VoteCast')
            if DEBUG: print >> sys.stderr, "votecast: DB made" 
        except: 
            print >> sys.stderr, "votecast: couldn't make the table"
        
        self.peer_db = PeerDBHandler.getInstance()
        self.channelcast_db = ChannelCastDBHandler.getInstance()
        
        if DEBUG:
            print >> sys.stderr, "votecast: "
    
    def registerSession(self, session):
        self.session = session
        
    def on_vote_from_dispersy(self, channel_id, voter_id, dispersy_id, vote, timestamp):
        insert_vote = "INSERT OR REPLACE INTO ChannelVotes (channel_id, voter_id, dispersy_id, vote, time_stamp) VALUES (?,?,?,?,?)"
        self._db.execute_write(insert_vote, (channel_id, voter_id, dispersy_id, vote, timestamp))

    def getPosNegVotes(self, channel_id):
        sql = 'select nr_favorite, nr_spam from Channels where id = ?'
        result = self._db.fetchone(sql, (channel_id,))
        if result:
            return result
        return 0,0 

    def getAllPosNegVotes(self):
        votes = {}
        
        sql = 'select id, nr_favorite, nr_spam from Channels'
        records = self._db.fetchall(sql)
        for channel_id, nr_favorite, nr_spam in records:
            votes[channel_id] = (nr_favorite, nr_spam)
            
        return votes

    def addVote(self, vote):
        sql = "INSERT OR IGNORE INTO ChannelVotes (channel_id, voter_id, vote, time_stamp) VALUES (?,?,?,?)"
        self._db.execute_write(sql, vote)
        self._updateVotes(vote[0])
        
    def addVotes(self, votes):
        sql = "INSERT OR IGNORE INTO ChannelVotes (channel_id, voter_id, vote, time_stamp) VALUES (?,?,?,?)"
        self._db.executemany(sql, votes)
        
        channels = set()
        for vote in votes:
            channels.add(vote[0])
        for channel in channels:
            self._updateVotes(channel)
        
    def removeVote(self, channel_id, voter_id):
        if voter_id:
            sql = "DELETE FROM ChannelVotes WHERE channel_id = ? AND voter_id = ?"
            sql._db.execute_write(sql, (channel_id, voter_id))
        else:
            sql = "DELETE FROM ChannelVotes WHERE channel_id = ? AND voter_id ISNULL"
            sql._db.execute_write(sql, (channel_id, ))
        
        self._updateVotes(channel_id)
            
    def _updateVotes(self, channel_id):
        nr_favorites = self._db.fetchone("SELECT count(*) FROM ChannelVotes WHERE vote == 2 AND channel_id = ?", (channel_id, ))
        nr_spam = self._db.fetchone("SELECT count(*) FROM ChannelVotes WHERE vote == -1 AND channel_id = ?", (channel_id, ))
        self._db.execute_write("UPDATE Channels SET nr_favorite = ?, nr_spam = ? WHERE id = ?", (nr_favorites, nr_spam, channel_id))
    
    def subscribe(self, channel_id):
        """insert/change the vote status to 2"""
        self.addVote((channel_id, None, 2, now()))
        self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)
    
    def unsubscribe(self, channel_id): ###
        """ change the vote status to 0"""
        self.removeVote(channel_id, None)
        self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)
    
    def spam(self, channel_id):
        """ insert/change the vote status to -1"""
        self.addVote((channel_id, None, -1, now()))
        self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

    def getVote(self, channel_id, voter_id):
        """ return the vote status if such record exists, otherwise None  """
        if voter_id:
            sql = "select vote from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select vote from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id, ))
    
    def getVoteForMyChannel(self, voter_id):
        return self.getVote(self.channelcast_db._channel_id, voter_id)
    
    def getDispersyId(self, channel_id, voter_id):
        """ return the dispersy_id for this vote """
        if voter_id:
            sql = "select dispersy_id from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select dispersy_id from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id, ))
    
    def getTimestamp(self, channel_id, voter_id):
        """ return the timestamp for this vote """
        if voter_id:
            sql = "select time_stamp from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select time_stamp from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id, ))
    
    def getChannelsWithNegVote(self, voter_id):
        ''' return the channel_ids having a negative vote from voter_id '''
        if voter_id:
            sql = "select channel_id from ChannelVotes where voter_id = ? and vote = -1"
            return self._db.fetchall(sql,(voter_id,))
        
        sql = "select channel_id from ChannelVotes where voter_id ISNULL and vote = -1"
        return self._db.fetchall(sql)
    
    def getChannelsWithPosVote(self, voter_id):
        ''' return the publisher_ids having a negative vote from subscriber_id '''
        if voter_id:
            sql = "select channel_id from ChannelVotes where voter_id = ? and vote = 2"
            return self._db.fetchall(sql,(voter_id,))
        sql = "select channel_id from ChannelVotes where voter_id ISNULL and vote = 2"
        return self._db.fetchall(sql)
    
    def getEffectiveVote(self, channel_id):
        """ returns positive - negative votes """
        pos_votes, neg_votes = self.getPosNegVotes(channel_id)
        return pos_votes

    def getEffectiveVoteFromPermid(self, channel_permid):
        channel_id = self.peer_db.getPeerID(self.my_permid)
        return self.getEffectiveVote(channel_id)
                        
#end votes

class ChannelCastDBHandler:
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):        
        if ChannelCastDBHandler.__single is None:
            ChannelCastDBHandler.lock.acquire()   
            try:
                if ChannelCastDBHandler.__single is None:
                    ChannelCastDBHandler(*args, **kw)
            finally:
                ChannelCastDBHandler.lock.release()
        return ChannelCastDBHandler.__single
    
    getInstance = staticmethod(getInstance)

    def __init__(self):
        ChannelCastDBHandler.__single = self
        try:
            self._db = SQLiteCacheDB.getInstance()
            
            self.peer_db = PeerDBHandler.getInstance()
            self.votecast_db = VoteCastDBHandler.getInstance()
            self.torrent_db = TorrentDBHandler.getInstance()
            self.notifier = Notifier.getInstance()
        except:
            print >> sys.stderr, "Channels: could not make a connection to table"

        self._channel_id = self._db.fetchone('SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1')
        self.my_dispersy_cid = None
        if True or DEBUG:
            print >> sys.stderr, "Channels: my channel is", self._channel_id
    
    def registerSession(self, session):
        self.session = session
            
    #dispersy helper functions
    def _get_my_dispersy_cid(self):
        if not self.my_dispersy_cid:
            from Tribler.Community.channel.community import ChannelCommunity
            from Tribler.Core.dispersy.dispersy import Dispersy
            dispersy = Dispersy.get_instance()
            
            for community in dispersy.get_communities():
                if isinstance(community, ChannelCommunity) and community.master_member and community.master_member.private_key:
                    self.my_dispersy_cid = community.cid
                    break
        
        return self.my_dispersy_cid
    
    def getDispersyCIDFromChannelId(self, channel_id):
        return self._db.fetchone(u"SELECT dispersy_cid FROM Channels WHERE id = ?", (channel_id,))
    
    #dispersy modifying and receiving channels
    def on_channel_from_channelcast(self, publisher_permid, name):
        peer_id = self.peer_db.addOrGetPeerID(publisher_permid)
        return self.on_channel_from_dispersy(-1, peer_id, name, '')
            
    def on_channel_from_dispersy(self, dispersy_cid, peer_id, name, description):
        if isinstance(dispersy_cid, (str)):
            _dispersy_cid = buffer(dispersy_cid)
        else:
            _dispersy_cid = dispersy_cid
        
        #for now fix channels to one per peer_id
        get_channel = "SELECT id FROM Channels Where peer_id = ?"
        channel_id = self._db.fetchone(get_channel, (peer_id,))
        
        if channel_id: #update this channel
            update_channel = "UPDATE Channels SET dispersy_cid = ?, name = ?, description = ? WHERE id = ?"
            self._db.execute_write(update_channel, (_dispersy_cid, name, description, channel_id))
            
        else: #insert channel
            insert_channel = "INSERT INTO Channels (dispersy_cid, peer_id, name, description) VALUES (?, ?, ?, ?); SELECT last_insert_rowid();"
            channel_id = self._db.fetchone(insert_channel, (_dispersy_cid, peer_id, name, description))
            
        if not self._channel_id and self._get_my_dispersy_cid() == dispersy_cid:
            self._channel_id = channel_id
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_CREATE, channel_id)
        
        self.notifier.notify(NTFY_CHANNELCAST, NTFY_INSERT, channel_id)
        return channel_id
        
    def on_channel_modification_from_dispersy(self, channel_id, modification_type, modification_value):
        if modification_type in ['name','description']:
            update_channel = "UPDATE Channels Set " + modification_type + " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_channel, (modification_value, long(time()), channel_id))
            
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)
    
    #dispersy adding, modifying and receiving torrents
    def addOwnTorrentDef(self, torrentdef, store = True, update = True, forward = True):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        
        if not self.hasTorrent(self._channel_id, torrentdef.get_infohash()):
            def dispersy_thread():
                cid = self._get_my_dispersy_cid()
                if cid:
                    print >> sys.stderr, "Channels: addnewtorrent"
                    
                    community = dispersy.get_community(cid)
                    community._disp_create_torrent_from_torrentdef(torrentdef, long(time()))
                
            from Tribler.Core.dispersy.dispersy import Dispersy
            dispersy = Dispersy.get_instance()
            dispersy.rawserver.add_task(dispersy_thread)
        else:
            print >> sys.stderr, "Torrent allready in channel or not in Torrents table"
        
    def deleteTorrent(self, channel_id, torrent_id):
        #TODO, connect with dispersy, decrement nr_torrents!
        raise NotImplementedError()
        """
        sql = 'Delete From ChannelCast where infohash=? and publisher_id=?'
        self._db.execute_write(sql,(bin2str(infohash),bin2str(self.my_permid),))
        """    
    
    def on_torrents_from_dispersy(self, torrentlist):
        print >> sys.stderr, "Channels: on_torrents_from_dispersy", len(torrentlist)
        
        infohashes = [values[2] for values in torrentlist]
        torrent_ids = self.torrent_db.addOrGetTorrentIDS(infohashes)
        
        updated_channels = {}
        
        insert_data = []
        insert_files = []
        insert_collecting = []
        for i in xrange(len(torrentlist)):
            channel_id, dispersy_id, infohash, timestamp, name, files, trackers = torrentlist[i]
            torrent_id = torrent_ids[i]
                          
            for path, length in files:
                insert_files.append((torrent_id, path, length))
            
            magnetlink = "magnet:?xt=urn:btih:"+hexlify(infohash)
            for tracker in trackers:
                magnetlink += "&tr="+urllib.quote_plus(tracker)
            insert_collecting.append((torrent_id, magnetlink))
            
            insert_data.append((dispersy_id, torrent_id, channel_id, name, timestamp))
            updated_channels[channel_id] = updated_channels.get(channel_id, 0) + 1
            
            if len(trackers) > 0:
                self.torrent_db._addTorrentTrackerList(torrent_id, trackers[0], [], commit = False)

        sql_insert_torrent = "INSERT OR REPLACE INTO ChannelTorrents (dispersy_id, torrent_id, channel_id, name, time_stamp) VALUES (?,?,?,?,?)"
        self._db.executemany(sql_insert_torrent, insert_data, commit = False)
    
        if len(insert_files) > 0:
            sql_insert_files = "INSERT OR IGNORE INTO TorrentFiles (torrent_id, path, length) VALUES (?,?,?)"
            self._db.executemany(sql_insert_files, insert_files, commit = False)
            
        if len(insert_collecting) > 0:
            sql_insert_collecting = "INSERT OR IGNORE INTO TorrentCollecting (torrent_id, source) VALUES (?,?)"
            self._db.executemany(sql_insert_collecting, insert_collecting, commit = False)
        
        sql_update_channel = "UPDATE Channels SET modified = strftime('%s','now'), nr_torrents = nr_torrents+? WHERE id = ?"
        update_channels = [(new_torrents, channel_id) for channel_id, new_torrents in updated_channels.iteritems()]
        self._db.executemany(sql_update_channel, update_channels)

        for channel_id in updated_channels.keys():         
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

    def on_torrent_modification_from_dispersy(self, channeltorrent_id, modification_type, modification_value):
        if modification_type in ['name', 'description']:
            update_torrent = "UPDATE ChannelTorrents SET " + modification_type + " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_torrent, (modification_value, long(time()), channeltorrent_id))
                
            sql = "Select infohash From Torrent, ChannelTorrents Where Torrent.torrent_id = ChannelTorrents.torrent_id And ChannelTorrents.id = ?"
            infohash = self._db.fetchone(sql, (channeltorrent_id, ))
            
            infohash = str2bin(infohash)
            self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)

    def addOrGetChannelTorrentID(self, channel_id, infohash):
        torrent_id = self.torrent_db.addOrGetTorrentID(infohash)

        sql = "SELECT id FROM ChannelTorrents WHERE torrent_id = ?"
        channeltorrent_id = self._db.fetchone(sql, (torrent_id, ))
        if not channeltorrent_id:
            insert_torrent = "INSERT OR IGNORE INTO ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp) VALUES (?,?,?,?);"
            self._db.execute_write(insert_torrent, (-1, torrent_id, channel_id, -1))
            
            channeltorrent_id = self._db.fetchone(sql, (torrent_id, ))
        return channeltorrent_id
    
    def hasTorrent(self, channel_id, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id:
            sql = "SELECT id FROM ChannelTorrents WHERE torrent_id = ?"
            channeltorrent_id = self._db.fetchone(sql, (torrent_id, ))
            if channeltorrent_id:
                return True
            
        return False
    
    #Old code used by channelcast
    def on_torrents_from_channelcast(self, torrents):
        #torrents is a list of tuples (channel_id, channel_name, infohash, time_stamp
        select_max = "SELECT max(time_stamp) FROM ChannelTorrents WHERE channel_id = ?"
        
        update_name = "UPDATE Channels SET name = ?, modified = ?, nr_torrents = ? WHERE id = ?"
        update_channel = "UPDATE Channels SET modified = ?, nr_torrents = ? WHERE id = ?"
        insert_torrent = "INSERT OR IGNORE INTO ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp) VALUES (?,?,?,?)"
        
        max_update = {}
        latest_update = {}
        
        for channel_id, channel_name, infohash, name, timestamp in torrents:
            if not channel_id in max_update:
                max_update[channel_id] = self._db.fetchone(select_max, (channel_id,))
            
            if timestamp > max_update[channel_id]:
                #possible name change
                latest_update[channel_id] = max((timestamp, channel_name), latest_update.get(channel_id, None))
            
            torrent_id = self.torrent_db.addOrGetTorrentID(infohash)
            self._db.execute_write(insert_torrent, (-1, torrent_id, channel_id, timestamp), commit = False)
        
        
        for channel_id in max_update.keys():        
            if channel_id in latest_update:
                new_name = latest_update[channel_id][1][:40]
                self._db.execute_write(update_name, (new_name, int(time()), self.getNrTorrentsInChannel(channel_id), channel_id), commit = False)
            else:
                self._db.execute_write(update_channel, (int(time()), self.getNrTorrentsInChannel(channel_id), channel_id), commit = False)
        
        self._db.commit()
    
    #dispersy receiving comments
    def on_comment_from_dispersy(self, channel_id, dispersy_id, mid_global_time, peer_id, comment, timestamp, reply_to, reply_after, playlist_dispersy_id, infohash):
        #both reply_to and reply_after could be loose pointers to not yet received dispersy message
        if isinstance(reply_to, (str)):
            reply_to = buffer(reply_to)
            
        if isinstance(reply_after, (str)):
            reply_after = buffer(reply_after)
        
        sql = "INSERT INTO Comments (channel_id, dispersy_id, peer_id, comment, reply_to_id, reply_after_id, time_stamp) VALUES (?, ?, ?, ?, ?, ?, ?); SELECT last_insert_rowid();"
        comment_id = self._db.fetchone(sql, (channel_id, dispersy_id, peer_id, comment, reply_to, reply_after, timestamp))
        
        if playlist_dispersy_id or infohash:
            if playlist_dispersy_id:
                sql = "SELECT id FROM Playlists WHERE dispersy_id = ?"
                playlist_id = self._db.fetchone(sql, (playlist_dispersy_id, ))
                
                sql = "INSERT INTO CommentPlaylist (comment_id, playlist_id) VALUES (?, ?)"
                self._db.execute_write(sql, (comment_id, playlist_id))
                self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, playlist_id)
                
            if infohash:
                channeltorrent_id = self.addOrGetChannelTorrentID(channel_id, infohash)
                
                sql = "INSERT INTO CommentTorrent (comment_id, channeltorrent_id) VALUES (?, ?)"
                self._db.execute_write(sql, (comment_id, channeltorrent_id))
                self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, channeltorrent_id)
                
        #try fo fix loose reply_to and reply_after pointers
        sql =  "UPDATE COMMENTS SET reply_to_id = ? WHERE reply_to_id = ?; UPDATE COMMENTS SET reply_after_id = ? WHERE reply_after_id = ?"
        self._db.execute_write(sql, (dispersy_id, buffer(mid_global_time), dispersy_id, buffer(mid_global_time)))
        self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, channel_id)
    
    #dispersy receiving, modifying playlists
    def on_playlist_from_dispersy(self, channel_id, dispersy_id, name, description):
        sql = "INSERT INTO Playlists (channel_id, dispersy_id,  name, description) VALUES (?, ?, ?, ?)"
        self._db.execute_write(sql, (channel_id, dispersy_id, name, description))
        
        self.notifier.notify(NTFY_PLAYLISTS, NTFY_INSERT, channel_id)
        
    def on_playlist_modification_from_dispersy(self, playlist_id, modification_type, modification_value):
        if modification_type in ['name','description']:
            update_playlist = "UPDATE Playlists Set " + modification_type +  " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_playlist, (modification_value, long(time()), playlist_id))
            
            self.notifier.notify(NTFY_PLAYLISTS, NTFY_UPDATE, playlist_id)
    
    def on_playlist_torrent(self, dispersy_id, infohash):
        get_playlist = "SELECT id, channel_id FROM Playlists WHERE dispersy_id = ?"
        playlist_id, channel_id = self._db.fetchone(get_playlist, (dispersy_id, ))
        
        channeltorrent_id = self.addOrGetChannelTorrentID(channel_id, infohash)
        sql = "INSERT INTO PlaylistTorrents (playlist_id, channeltorrent_id) VALUES (?,?)"
        self._db.execute_write(sql, (playlist_id, channeltorrent_id))
        
        self.notifier.notify(NTFY_PLAYLISTS, NTFY_UPDATE, playlist_id)
        
    def on_metadata_from_dispersy(self, type, link_id, dispersy_id, mid_global_time, modification_type_id, modification_value, prev_modification_id, prev_modification_global_time):
        sql = "INSERT INTO ChannelMetaData (dispersy_id, type_id, value, prev_modification, prev_global_time) VALUES (?, ?, ?, ?, ?); SELECT last_insert_rowid();"
        metadata_id = self._db.fetchone(sql, (dispersy_id, modification_type_id, modification_value, prev_modification_id, prev_modification_global_time))
        
        if type == u"torrent":
            sql = "INSERT INTO MetaDataTorrent (metadata_id, channeltorrent_id) VALUES (?,?)"
            self._db.execute_write(sql, (metadata_id, link_id), commit = False)
            
        elif type == u"playlist":
            sql = "INSERT INTO MetaDataPlaylist (metadata_id, playlist_id) VALUES (?,?)"
            self._db.execute_write(sql, (metadata_id, link_id), commit = False)
            
        elif type == u"channel":
            sql = "INSERT INTO MetaDataChannel (metadata_id, channel_id) VALUES (?,?)"
            self._db.execute_write(sql, (metadata_id, link_id), commit = False)

        #try fo fix loose reply_to and reply_after pointers
        sql =  "UPDATE ChannelMetaData SET prev_modification = ? WHERE prev_modification = ?;"
        self._db.execute_write(sql, (dispersy_id, buffer(mid_global_time)))
    
    def selectTorrentsToCollect(self, channel_id = None):
        if channel_id:
            sql = 'Select infohash From ChannelTorrents, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND channel_id = ? and ChannelTorrents.torrent_id not in (Select torrent_id From CollectedTorrent)'
            records = self._db.fetchall(sql,(channel_id,))
        else:
            sql = 'Select infohash From ChannelTorrents, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND ChannelTorrents.torrent_id not in (Select torrent_id From CollectedTorrent)'
            records = self._db.fetchall(sql)
            
        return [str2bin(infohash) for infohash, in records]
    
    def getNrTorrentsDownloaded(self, channel_id):
        sql = "select count(*) from MyPreference, ChannelTorrents where MyPreference.torrent_id = ChannelTorrents.torrent_id and ChannelTorrents.channel_id = ? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))

    def getNrTorrentsInChannel(self, channel_id):
        sql = "select count(torrent_id) from ChannelTorrents where channel_id==? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))
    
    def getPermidForChannel(self, channel_id):
        sql = "SELECT permid FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id AND Channels.id = ?"
        return self._db.fetchone(sql, (channel_id,))
    
    def getPermChannelIdDict(self):
        returndict = {}
        
        sql = "SELECT permid, Channels.id FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id GROUP BY permid"
        results = self._db.fetchall(sql)
        for permid, channel_id in results:
            returndict[str2bin(permid)] = channel_id
            
        return returndict
    
    def getRecentAndRandomTorrents(self,NUM_OWN_RECENT_TORRENTS=15, NUM_OWN_RANDOM_TORRENTS=10, NUM_OTHERS_RECENT_TORRENTS=15, NUM_OTHERS_RANDOM_TORRENTS=10):
        allrecords = set()
        
        sql = "select dispersy_id, time_stamp from ChannelTorrents where channel_id==? and dispersy_id <> -1 order by time_stamp desc limit ?"
        myrecenttorrents = self._db.fetchall(sql, (self._channel_id, NUM_OWN_RECENT_TORRENTS))
        allrecords.update([dispersy_id for dispersy_id,_ in myrecenttorrents])
        
        if len(allrecords) == NUM_OWN_RECENT_TORRENTS:
            least_recent = myrecenttorrents[-1][1]
            
            sql = "select dispersy_id from ChannelTorrents where channel_id==? and time_stamp<? and dispersy_id <> -1 order by random() limit ?"
            myrandomtorrents = self._db.fetchall(sql,(self._channel_id, least_recent, NUM_OWN_RANDOM_TORRENTS))
            allrecords.update([dispersy_id for dispersy_id, in myrandomtorrents])
        
        additionalSpace = (NUM_OWN_RECENT_TORRENTS + NUM_OWN_RANDOM_TORRENTS) - len(allrecords)
        if additionalSpace > 0:
            NUM_OTHERS_RECENT_TORRENTS +=  additionalSpace/2
            NUM_OTHERS_RANDOM_TORRENTS +=  additionalSpace - (additionalSpace/2)
        
        sql = "select dispersy_id, time_stamp from ChannelTorrents where channel_id in (select channel_id from ChannelVotes where voter_id ISNULL and vote=2) and dispersy_id <> -1 order by time_stamp desc limit ?"
        othersrecenttorrents = self._db.fetchall(sql, (NUM_OTHERS_RECENT_TORRENTS,))
        allrecords.update([dispersy_id for dispersy_id,_ in othersrecenttorrents])
        
        if othersrecenttorrents and len(othersrecenttorrents) == NUM_OTHERS_RECENT_TORRENTS:
            least_recent = othersrecenttorrents[-1][1]
            
            sql = "select dispersy_id from ChannelTorrents where channel_id in (select channel_id from ChannelVotes where voter_id ISNULL and vote=2) and time_stamp < ? and dispersy_id <> -1 order by random() limit ?"
            othersrandomtorrents = self._db.fetchall(sql,(least_recent ,NUM_OTHERS_RANDOM_TORRENTS))
            allrecords.update([dispersy_id for dispersy_id, in othersrandomtorrents])
        
        sql = "select dispersy_id from ChannelTorrents where channel_id in (select distinct channel_id from ChannelTorrents where torrent_id in (select torrent_id from MyPreference)) and dispersy_id <> -1  order by time_stamp desc limit ?"
        interesting_records = self._db.fetchall(sql,(55-len(allrecords), ))
        allrecords.update([dispersy_id for dispersy_id, in interesting_records])
        return allrecords

    def getTorrentFromChannelId(self, channel_id, infohash, keys):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? AND infohash = ?"
        result = self._db.fetchone(sql, (channel_id, bin2str(infohash)))
        result = self.__fixTorrents(keys, [result]) 
        if result:
            return result[0]
    
    def getTorrentFromChannelTorrentId(self, channeltorrent_id, keys):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = ?"
        result = self._db.fetchone(sql, (channeltorrent_id,))
        result = self.__fixTorrents(keys, [result]) 
        if result:
            return result[0]
        else:
            print >> sys.stderr, "COULD NOT FIND CHANNELTORRENT_ID", channeltorrent_id
            
    def getTorrentsFromChannelId(self, channel_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (channel_id,))
        return self.__fixTorrents(keys, results)
    
    def getRecentTorrentsFromChannelId(self, channel_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? ORDER BY inserted DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (channel_id,))
        return self.__fixTorrents(keys, results)
    
    def getTorrentsFromPlaylist(self, playlist_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents, PlaylistTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND playlist_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (playlist_id,))
        return self.__fixTorrents(keys, results)
    
    def getRecentTorrentsFromPlaylist(self, playlist_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents, PlaylistTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND playlist_id = ? ORDER BY inserted DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (playlist_id,))
        return self.__fixTorrents(keys, results)
    
    def getTorrentsNotInPlaylist(self, channel_id, keys):
        sql = "SELECT " + ", ".join(keys) +" FROM CollectedTorrent, ChannelTorrents WHERE CollectedTorrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? And ChannelTorrents.id NOT IN (Select channeltorrent_id From PlaylistTorrents) ORDER BY time_stamp DESC"
        results = self._db.fetchall(sql, (channel_id,))
        return self.__fixTorrents(keys, results)
    
    def __fixTorrents(self, keys, results):
        torrent_list = []
        for result in results:
            if isinstance(result, basestring):
                result = [result]
                
            if result:
                torrent_list.append(dict(zip(keys,result)))
            
        for torrent in torrent_list:
            if 'infohash' in torrent:
                torrent['infohash'] = str2bin(torrent['infohash'])
            if 'category_id' in torrent:
                torrent['category'] = [self.torrent_db.id2category[torrent['category_id']]]
            if 'status_id' in torrent:
                torrent['status'] = self.torrent_db.id2status[torrent['status_id']]
        return torrent_list

    def getPlaylistsFromChannelId(self, channel_id, keys):
        sql = "SELECT " + ", ".join(keys) +" FROM Playlists WHERE channel_id = ? ORDER BY name DESC"
        results = self._db.fetchall(sql, (channel_id,))
        
        playlist_list = [dict(zip(keys,result)) for result in results]
        self._getPlaylists(playlist_list)
        return playlist_list
    
    def getPlaylist(self, playlist_id, keys):
        sql = "SELECT " + ", ".join(keys) +" FROM Playlists WHERE id = ?"
        result = self._db.fetchone(sql, (playlist_id,))
        return dict(zip(keys,result))
    
    def _getPlaylists(self, playlistdicts):
        sql = "SELECT count(*) FROM PlaylistTorrents WHERE playlist_id = ?"
        for dict in playlistdicts:
            dict['nr_torrents'] = self._db.fetchone(sql, (dict['id'],))
            
    def getCommentsFromChannelId(self, channel_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) + " FROM Comments LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id LEFT JOIN CommentPlaylist On Comments.id = CommentPlaylist.comment_id LEFT JOIN CommentTorrent On Comments.id = CommentTorrent.comment_id WHERE channel_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (channel_id, ))
        
        commentlist = [dict(zip(keys,result)) for result in results]
        return commentlist

    def getCommentsFromPlayListId(self, playlist_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) + " FROM Comments, CommentPlaylist LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id WHERE Comments.id = CommentPlaylist.comment_id AND playlist_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (playlist_id, ))
        
        commentlist = [dict(zip(keys,result)) for result in results]
        return commentlist
    
    def getCommentsFromChannelTorrentId(self, channeltorrent_id, keys, limit = None):
        sql = "SELECT " + ", ".join(keys) + " FROM Comments, CommentTorrent LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id WHERE Comments.id = CommentTorrent.comment_id AND channeltorrent_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d"%limit
        results = self._db.fetchall(sql, (channeltorrent_id, ))
        
        commentlist = [dict(zip(keys,result)) for result in results]
        return commentlist
        
    def searchChannels(self, keywords):
        # search channels based on keywords
        keywords = split_into_keywords(keywords)
        keywords = [keyword for keyword in keywords if len(keyword) > 1]
        
        if len(keywords) > 0:
            sql = "SELECT distinct id, name FROM Channels WHERE" + (" name like '%?%' and"*len(keywords))
            sql = sql[:-3]
                   
            channels = self._db.fetchall(sql)
            select_torrents = "SELECT infohash, ChannelTorrents.name, CollectedTorrent.name, time_stamp from ChannelTorrents, CollectedTorrent WHERE ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND channel_id = ? ORDER BY time_stamp DESC LIMIT 20"
            
            results = []
            for channel_id, name in channels:
                torrents = self._db.fetchall(select_torrents, (channel_id, ))
                for infohash, ChTname, CoTname, time_stamp in torrents:
                    results.append((channel_id, name, infohash, ChTname or CoTname, time_stamp))
            return results
        return []
        
        """
        SHOULD BE MOVED INTO DISPERSY
        elif query[0] == 'p':
            # search channel's torrents based on permid
            q = query[2:]
            arguments = q.split()
            records = []


            if len(arguments) == 1:
                publisher_id = q
            else:
                publisher_id = arguments[0]
            
            
            s = "Select 1 FROM VoteCast Where voter_id = ? AND mod_id = ? AND vote == 2"
            
            allrecords = []
            if len(arguments) == 1:
                s = "select * from ChannelCast where publisher_id==? order by time_stamp desc limit 50"
                allrecords = self._db.fetchall(s,(q,))
            
            elif publisher_id == bin2str(self.my_permid) or self._db.fetchone(s, (bin2str(self.my_permid), publisher_id)): #are we subscribed to this channel?
                publisher_id = arguments[0]
                min_timestamp = float(arguments[1])
                max_timestamp = float(arguments[2])
                nr_items = int(arguments[3])
                
                allrecords = []
                s = "select min(time_stamp), max(time_stamp), count(infohash) from ChannelCast where publisher_id==? group by publisher_id"
                record = self._db.fetchone(s,(publisher_id,))
                if record:
                    #detect if we have older items, newer items or more items
                    change = record[0] < min_timestamp or record[1] > max_timestamp or record[2] > nr_items
                    if change:
                        #does the peer have any missing items in its timeframe?
                        s = "select count(infohash) from ChannelCast where publisher_id==? and time_stamp between ? and ? group by publisher_id"
                        items = self._db.fetchone(s,(publisher_id,min_timestamp,max_timestamp))
                        
                        if items > nr_items:
                            #correct his timeframe, by returning nr_items + 1
                            nr_items_return = nr_items + 1
                            if nr_items_return < 50:
                                nr_items_return = 50
                            #print >> sys.stderr, "He has incorrect timeframe, returning %d items"%nr_items_return
                            
                            s = "select * from ChannelCast where publisher_id==? order by time_stamp desc limit ?"
                            allrecords = self._db.fetchall(s,(publisher_id,nr_items_return))
                        else:
                            #return max 50 newer, append with old
                            s = "select * from ChannelCast where publisher_id==? and time_stamp > ? order by time_stamp asc limit 50"
                            allrecords = self._db.fetchall(s,(publisher_id,max_timestamp))
                            
                            if len(allrecords) < 50:
                                s = "select * from ChannelCast where publisher_id==? and time_stamp < ? order by time_stamp desc limit ?"
                                allrecords.extend(self._db.fetchall(s,(publisher_id,min_timestamp,50 - len(allrecords))))
                    elif record[0] > min_timestamp or record[1] < max_timestamp or record[2] < nr_items:
                        #print >> sys.stderr, "HE HAS MORE DATA"
                        pass
                    else:
                        #print >> sys.stderr, "WE HAVE SAME DATA"
                        pass
                else:
                    #print >> sys.stderr, "WE DONT KNOW THIS CHANNEL"
                    pass
            for record in allrecords:
                records.append((str2bin(record[0]), record[1], str2bin(record[2]), str2bin(record[3]), record[4], record[5], str2bin(record[6])))
                
            return records #channelList#
         
        # Query is invalid: hence, it should not even come here
        return None
        """
       
    def getChannel(self, channel_id):
        sql = "Select id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE id = ?"
        channels = self._getChannels(sql, (channel_id,))
        if len(channels) > 0:
            channel = list(channels[0])
            
            sql = "Select description From Channels Where id = ?"
            channel.append(self._db.fetchone(sql, (channel_id, )))
            return channel 
   
    def getAllChannels(self):
        """ Returns all the channels """
        sql = "Select id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels"
        return self._getChannels(sql)
    
    def getNewChannels(self, updated_since = 0):
        """ Returns all newest unsubscribed channels, ie the ones with no votes (positive or negative)"""
        sql = "Select id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels"
        return self._getChannels(sql, maxvotes = 0, updated_since = updated_since)
    
    def getLatestUpdated(self, max_nr = 20):
        def channel_sort(a,b):
            #first compare local vote, spam -> return -1
            if a[6] == -1:
                return 1
            if b[6] == -1:
                return -1
            
            #then compare latest update
            if a[2] < b[2]:
                return 1
            if a[2] > b[2]:
                return -1
            #finally compare nr_torrents
            return cmp(a[4], b[4])
        
        sql = "Select Channels.id, Channels.name, Channels.dispersy_cid, Channels.modified, nr_torrents, nr_favorite, nr_spam FROM Channels, ChannelTorrents WHERE Channels.id = ChannelTorrents.channel_id GROUP BY Channels.id Order By max(time_stamp) DESC Limit ?"
        return self._getChannels(sql, (max_nr,), cmpF = channel_sort)
    
    def getMostPopularChannels(self, max_nr = 20):
        sql = "Select id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels"
        return self._getChannels(sql)[:20]

    def getMySubscribedChannels(self):
        sql = "SELECT id, name, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels, ChannelVotes WHERE Channels.id = ChannelVotes.channel_id AND voter_id ISNULL AND vote == 2"
        return self._getChannels(sql)
    
    def _getChannels(self, sql, args = None, maxvotes = sys.maxint, minvotes = 0, cmpF = None, updated_since = 0):
        """Returns the channels based on the input sql, if the number of positive votes is less than maxvotes and the number of torrent > 0"""
        channels = []
        results = self._db.fetchall(sql, args)
        
        for channel_id, channel_name, dispersy_cid, modified, nr_torrents, nr_favorites, nr_spam in results:
            nr_votes = nr_favorites + nr_spam
            
            if nr_votes >= minvotes and nr_votes <= maxvotes:
                my_vote = self.votecast_db.getVote(channel_id, None)
                channels.append((channel_id, channel_name[:40], modified, nr_favorites, nr_torrents, nr_spam, my_vote, dispersy_cid != '-1', dispersy_cid))
                
        def channel_sort(a, b):
            #first compare local vote, spam -> return -1
            if a[6] == -1:
                return 1
            if b[6] == -1:
                return -1
            
            #then compare nr_votes
            if a[3] < b[3]:
                return 1
            if a[3] > b[3]:
                return -1
            #then compare latest update
            if a[2] < b[2]:
                return 1
            if a[2] > b[2]:
                return -1
            #finally compare nr_torrents
            return cmp(a[4], b[4])
        
        if cmpF == None:
            cmpF = channel_sort
        channels.sort(cmpF)
        return channels

    def getMySubscribersCount(self):
        return self.getSubscribersCount(self._channel_id)

    def getSubscribersCount(self, channel_id):
        """returns the number of subscribers in integer format"""
        nr_favorites, nr_spam = self.votecast_db.getPosNegVotes(channel_id)
        return nr_favorites

    def getMostPopularChannelFromTorrent(self, infohash):
        """Returns channel id, name, nrfavorites of most popular channel if any"""
        sql = "select Channels.id, Channels.name from Channels, ChannelTorrents, CollectedTorrent where Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND infohash = ?" 
        channels = self._db.fetchall(sql,(bin2str(infohash),))
        
        if len(channels) > 0:
            max_id = -1
            max_name = ''
            max_vote = -1
            for channel_id, name in channels:
                nr_favorites, nr_spam = self.votecast_db.getPosNegVotes(channel_id)
                
                if nr_favorites > max_vote:
                    max_id = channel_id
                    max_name = name
                    max_vote = nr_favorites
            return (max_id, max_name, max_vote)
            
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


class PopularityDBHandler(BasicDBHandler):
    '''
    @author: Rahim    04-2009
    This class handles access to Popularity tables that is used for 
    keeping swarm size info, received through BuddyCast messages.
    '''
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if PopularityDBHandler.__single is None:
            PopularityDBHandler.lock.acquire()   
            try:
                if PopularityDBHandler.__single is None:
                    PopularityDBHandler(*args, **kw)
            finally:
                PopularityDBHandler.lock.release()
        return PopularityDBHandler.__single
    getInstance = staticmethod(getInstance)

    def __init__(self):
        if PopularityDBHandler.__single is not None:
            raise RuntimeError, "PopularityDBHandler is singleton"
        PopularityDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()        
        BasicDBHandler.__init__(self,db, 'Popularity')
        
        # define local handlers to access Peer and Torrent tables.
        self.peer_db = PeerDBHandler.getInstance()
        self.torrent_db = TorrentDBHandler.getInstance()
        
    ###--------------------------------------------------------------------------------------------------------------------------
        
    def calculateSwarmSize(self, torrentList, content, toBC=True):
        """
        This method gets a list of torrent_ids and then calculat the size of the swarm for those torrents.
        @author: Rahim
        @param torrentList: A list of torrent_id.
        @param content: If it be 'infohash' , the content of the torrentList is infohsh of torrents. If it be 'torrentIds', the content is a list 
        of torrent_id.
        @param toBc: This flag determines that whether the returned result will be used to create a new BC message or not. The difference is that nodes 
        just send first hand information to each other. The prevent speard of contamination if one of the nodes receive incorrent value from sender. 
        The main difference in the flow of the process is that, if toBC be set to False, this fucntion will look for the most recenct report inside 
        both Popularity and Torrent table, otherwise it will just use torrent table.
        @return: returns a list with the same size az input and each items is composed of below items:
                  [torrent_id, num_seeders, num_leechers, age, num_of_sources]
        """
        if content=='Infohash':
            torrentList = self.torrent_db.getTorrentIDS(torrentList)
        elif content=='TorrentIds':
            pass
        else:
            return []
        trackerSizeDict = self.torrent_db.getSwarmInfos(torrentList)
        """
        for torrentId in torrentList:
            trackerSizeList.append(self.torrent_db.getSwarmInfo(torrentId))
            if not toBC:
                popularityList.append(self.getPopularityList(torrent_id = torrentId))
        """
        result =[]
        timeNow=int(time())
        
        averagePeerUpTime = 2 * 60 * 60  # we suppose that the average uptime is roughly two hours.
        for torrent_id in torrentList:
            if torrent_id not in trackerSizeDict:
                result.append([torrent_id, -1, -1, -1, -1])  # (torrent_id, num_seeders, num_leechers, calc_age, num_sources_seen)
            elif toBC:
                torrentList = trackerSizeDict[torrent_id]
                result.append([torrent_id, torrentList[1], torrentList[2], timeNow - torrentList[3], torrentList[4]])
            else:
                popList = self.getPopularityList(torrent_id = torrent_id)
                latest = self.getLatestPopularityReport(popList, timeNow)
                result.append([torrent_id, latest[4], latest[5], timeNow - latest[2]+latest[3], latest[6]])
        return result
    
    def getLatestPopularityReport(self, reportList, timeNow):
       
        """
        gets a list of list and then returns on of the them that has highest value in the specified index.
        @author: Rahim    
        @param reportList: A list that contains popularity report for specified torrent. The first item contains torrent_id.
        @param index: The index of item that comparision is done based on it.
        @param timeNow: Indictes local time of the node that runs this process.
       
        """
        if len(reportList) ==0:
            return []
       
        result=reportList.pop(0)
        listLength = len(reportList)
        
        for i in range(0,listLength):
            if (timeNow - reportList[i][2] + reportList[i][3])  < (timeNow - result[2] + result[3]): #it selects the youngest report
                result = reportList[i]
       
        return result
       
        
    ###--------------------------------------------------------------------------------------------------------------------------         
    def checkPeerValidity(self, peer_id):
        '''
        checks whether the peer_id is valid or not, in other word it is in the Peer table or not?
        @param peer_id: the id of the peer to be checked.
        @return: True if the peer_is is valid, False if not.
        '''
        if self.peer_db.getPermid(peer_id) is None:
            return False
        else: 
            return True  
    ###--------------------------------------------------------------------------------------------------------------------------            
    def checkTorrentValidity(self, torrent_id):
        '''
        checks whether the torrent_id is valid or not, in other word it is in the Torrent table or not?
        @param torrent_id: the id of the torrent to be checked.
        @return: True if the torrent_is is valid, False if not.
        '''        
        if self.torrent_db.getInfohash(torrent_id) is None:
            return False
        else:
            return True
    ###--------------------------------------------------------------------------------------------------------------------------        
    def addPopularity(self, torrent_id, peer_id, recv_time, calc_age=sys.maxint, num_seeders=-1, num_leechers=-1, num_sources=-1, validatePeerId=False, validateTorrentId=False,
                       checkNumRecConstraint=True, commit=True):
        '''
        Addes a new popularity record to the popularity table.
        @param torrent_id: The id of the torrent that is added to the table.
        @param peer_id: The id of the peer that is added to the table.
        @param recv_time: The time that peer has received the message.
        @param num_seeders: Number of seeders reportd by the remote peer.
        @param num_leechers: Number of leechers reported by the remote peer.
        @param num_sources: Number of the Tribler sources that have seen this torrent, reported by the remote peer.
        @param calc_age: The time that the remote peer has calculated( or message send time) the swarm size.
        @param validateTorrent: If set to True check validity of the Torrent otherwise no.
        @param validatePeer: If set to True check validity of the Peer otherwise no.
        '''
        if validatePeerId: # checks whether the peer is valid or not
            if not self.checkPeerValidity(peer_id):
                return None
        if validateTorrentId: #checks whether the torrent is valid or not
            if not self.checkTorrentValidity(torrent_id):
                return None

        sql_insert_new_populairty = u"""INSERT OR REPLACE INTO Popularity (torrent_id, peer_id, msg_receive_time, size_calc_age, num_seeders,
                                        num_leechers, num_of_sources) VALUES (?,?,?,?,?,?,?)"""
        try:
            self._db.execute_write(sql_insert_new_populairty, (torrent_id, peer_id, recv_time, calc_age, num_seeders, num_leechers, num_sources), commit=commit)
        except Exception, msg:    
            print_exc() 
        
        timeNow = int(time())
        if checkNumRecConstraint: # Removes old records. The number of records should not exceed defined limitations.
 
            availableRecsT = self.countTorrentPopularityRec(torrent_id, timeNow)
            if availableRecsT[0] > MAX_POPULARITY_REC_PER_TORRENT:
                self.deleteOldTorrentRecords(torrent_id, availableRecsT[0] - MAX_POPULARITY_REC_PER_TORRENT, timeNow, commit=commit)
    
    
            availableRecsTP = self.countTorrentPeerPopularityRec(torrent_id, peer_id, timeNow)
            if availableRecsTP[0] > MAX_POPULARITY_REC_PER_TORRENT_PEER:
                self.deleteOldTorrentPeerRecords(torrent_id,peer_id, availableRecsTP[0] - MAX_POPULARITY_REC_PER_TORRENT_PEER, timeNow, commit=commit)
    
    ###--------------------------------------------------------------------------------------------------------------------------            
    def storePeerPopularity(self, peer_id, popularityList, validatePeerId=False, validateTorrentId=False, commit=True):
        '''
        Insert all popularity info received through BuddyCast message. popularityList is a tuple of 
        @param peer_id: The id of the popularity info sender.
        @param popularityList: A list of tuple (torrent_id, recv_time, calc_age, num_seeders, num_leechers, num_sources), usually received through BuddyCast message.
        '''
        if validatePeerId:
           if not self.checkPeerValidity(peer_id):
               return None
        
        for item in popularityList[:-1]:
           self.addPopularity(item[0], peer_id, item[1], item[2], item[3], item[4], item[5], validateTorrentId=validateTorrentId, commit=False)
        
        if len(popularityList)>0:
            item = popularityList[-1]
            self.addPopularity(item[0], peer_id, item[1], item[2], item[3], item[4], item[5], validateTorrentId=validateTorrentId, commit=commit)
    ###--------------------------------------------------------------------------------------------------------------------------        
    def countTorrentPopularityRec(self, torrent_id, timeNow):
        '''
        This method counts the number of logged popularity for the input torrrent.
        @param torrent_id: the id of the torrent
        @return: (number_of_records, oldest_record_time)
        '''     
        
        count_sql = "SELECT count(*) FROM Popularity WHERE torrent_id=?" 
        num_of_popularity = self._db.fetchone(count_sql,(torrent_id, ))
                    
        if num_of_popularity > 0:
            sql_oldest_record = "SELECT size_calc_age FROM Popularity WHERE torrent_id=? ORDER BY ( ? - msg_receive_time+size_calc_age) DESC LIMIT ?"
            oldest_record_age = self._db.fetchone(sql_oldest_record, (torrent_id, timeNow, 1))
            return (num_of_popularity, oldest_record_age)
        else:
            if DEBUG:
                print >> sys.stderr, "The torrent with the id ", torrent_id, " does not have any popularity record."
            return (0 , sys.maxint) 
    ###--------------------------------------------------------------------------------------------------------------------------        
    def countTorrentPeerPopularityRec(self, torrent_id, peer_id, timeNow):
        '''
        counts the number of popularity records done for the input torrent_id by the input peer_id.
        @param torrent_id: the id of the torrent.
        @param peer_id: the id of the peer.
        @return: (number_of_records, oldest_record_time) with same torrent_id and peer_id as input.
        '''
        count_sql = "SELECT count(*) FROM Popularity WHERE torrent_id=? AND peer_id=?" 
        num_of_popularity = self._db.fetchone(count_sql,(torrent_id, peer_id))
        
        if num_of_popularity > 0:
            sql_oldest_record = "SELECT size_calc_age FROM Popularity WHERE torrent_id=? AND peer_id=? ORDER BY ( ? - msg_receive_time+size_calc_age) DESC LIMIT ?"
            oldest_record_age = self._db.fetchone(sql_oldest_record, (torrent_id, peer_id, timeNow, 1))
            return (num_of_popularity, oldest_record_age)
        else:
            if DEBUG:
                print >> sys.stderr, "The peer with the id ", peer_id, "has not reported any thing about the torrent: ", torrent_id
            return (0 , sys.maxint) 
    ###--------------------------------------------------------------------------------------------------------------------------     
    def deleteOldTorrentRecords(self, torrent_id, num_rec_to_delete, timeNow, commit=True):
         '''
         Deletes the oldest num_rec_to_del popularity records about the torrect_id from popularity table.
         @param torrent_id: the id of the torrent.
         @param num_rec_to_delete: Number of the oldest records that should be removed from the table.
         '''
         
         sql_delete = u""" DELETE FROM Popularity WHERE torrent_id=? AND size_calc_age IN 
                           (SELECT size_calc_age FROM Popularity WHERE torrent_id=? 
                           ORDER BY (? - msg_receive_time+size_calc_age) DESC LIMIT ?)"""
         
         self._db.execute_write(sql_delete, (torrent_id, torrent_id, timeNow, num_rec_to_delete), commit=commit)

    ###--------------------------------------------------------------------------------------------------------------------------
    def deleteOldTorrentPeerRecords(self, torrent_id, peer_id, num_rec_to_delete, timeNow, commit=True):
         '''
         Deletes the oldest num_rec_to_del popularity records about the torrect_id repported by peer_id from popularity table.
         @param torrent_id: the id of the torrent.
         @param peer_id: the id of the popularity sender.
         @param num_rec_to_delete: Number of the oldest records that should be removed from the table.
         '''
         
         sql_delete = u""" DELETE FROM Popularity where torrent_id=? AND peer_id=? AND size_calc_age IN 
                           (SELECT size_calc_age FROM popularity WHERE torrent_id=? AND peer_id=?
                           ORDER BY (? - msg_receive_time+size_calc_age) DESC LIMIT ?)"""
         
         self._db.execute_write(sql_delete, (torrent_id, peer_id,torrent_id, peer_id,timeNow, num_rec_to_delete), commit=commit)
         
    ###--------------------------------------------------------------------------------------------------------------------------
    def getPopularityList(self, torrent_id=None, peer_id=None , recv_time_lbound=0, recv_time_ubound=sys.maxint):
         '''
         Returns a list of the records from the Popularity table, by using input parameters.
         @param torremt_id: The id of the torrent.
         @param peer_id: The id of the peer.
         @param recv_time_lbound: Lower bound for the message receive time. Default value is 0.
         @param recv_time_ubound: Upper bound for the message receive time. Default value is 0x10000000L
         @return: A list of tuple (torrent_id, recv_time, calc_age, num_seeders, num_leechers, num_sources)
         '''
         sql_getPopList=" SELECT * FROM Popularity"
         
         if (torrent_id is not None) or (peer_id is not None) or (not recv_time_lbound==0) or (not recv_time_ubound==sys.maxint):
             sql_getPopList += " WHERE "
         
         if torrent_id is not None:
             sql_getPopList += "torrent_id = %s" % torrent_id 
             if (peer_id is not None) or (not recv_time_lbound==0) or (not recv_time_ubound==sys.maxint):
                 sql_getPopList += " AND "
         
         if peer_id is not None:
             sql_getPopList += "peer_id = %d" % peer_id 
             if (not recv_time_lbound==0) or (not recv_time_ubound==sys.maxint):
                 sql_getPopList += " AND "
             
         if not recv_time_lbound==0:
             sql_getPopList += "msg_receive_time >= %d" % recv_time_lbound
             if not recv_time_ubound==sys.maxint: 
                 sql_getPopList += " AND " 
         
         if not recv_time_ubound==sys.maxint:
             sql_getPopList += "msg_receive_time <= %d" % recv_time_ubound 
          
         print sql_getPopList 
         popularityList = self._db.fetchall(sql_getPopList)
         
         return popularityList 
     
    ###----------------------------------------------------------------------------------------------------------------------
    
    def addPopularityRecord(self, peer_permid, pops, selversion, recvTime, is_torrent_id=False, commit=True):
        """
        """       
       
        peer_id = self._db.getPeerID(peer_permid)
        if peer_id is None:
            print >> sys.stderr, 'PopularityDBHandler: update received popularity list from a peer that is not existed in Peer table', `peer_permid`
            return

        pops = [type(pop) is str and {"infohash":pop} or pop
                 for pop
                 in pops]
        
        if __debug__:
            for pop in pops:
                assert isinstance(pop["infohash"], str), "INFOHASH has invalid type: %s" % type(pop["infohash"])
                assert len(pop["infohash"]) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(pop["infohash"])
        
        if is_torrent_id:
            #Rahim : Since overlay version 11 swarm size information is 
            # appended and should be added to the database . The codes below 
            # does this. torrent_id, recv_time, calc_age, num_seeders, 
            # num_leechers, num_sources
            #
            torrent_id_swarm_size =[]
            for pop in pops:
                if pop is not None:
                    tempAge = pop.get('calc_age')
                    tempSeeders = pop.get('num_seeders')
                    tempLeechers = pop.get('num_leechers')
                    if tempAge > 0 and tempSeeders >= 0 and tempLeechers >= 0:
                        torrent_id_swarm_size.append( [pop['torrent_id'],
                                     recvTime, 
                                     tempAge,  
                                     tempSeeders,
                                     tempLeechers,
                                     pop.get('num_sources_seen', -1)]# -1 means invalud value 
                                     )
        else:
            torrent_id_swarm_size = []
            for pop in pops:
                if type(pop)==dict:
                    infohash = pop["infohash"]
                else:
                    # Nicolas: from wherever this might come, we even handle 
                    # old list of infohashes style
                    infohash = pop 
                torrent_id = self._db.getTorrentID(infohash)
                if not torrent_id:
                    self._db.insertInfohash(infohash)
                    torrent_id = self._db.getTorrentID(infohash)
                #Rahim: Amended for handling and adding swarm size info.
                #torrent_id_swarm_size.append((torrent_id, timeNow,0, -1, -1, -1))
        if len(torrent_id_swarm_size) > 0:
            try:
                #popularity_db = PopularityDBHandler.getInstance()
                #popularity_db.storePeerPopularity(peer_id, torrent_id_swarm_size, commit=commit)
                self.storePeerPopularity(peer_id, torrent_id_swarm_size, commit=commit)
            except Exception, msg:    
                print_exc()
                print >> sys.stderr, 'dbhandler: updatePopularity:', Exception, msg 

class TermDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if TermDBHandler.__single is None:
            TermDBHandler.lock.acquire()   
            try:
                if TermDBHandler.__single is None:
                    TermDBHandler(*args, **kw)
            finally:
                TermDBHandler.lock.release()
        return TermDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if TermDBHandler.__single is not None:
            raise RuntimeError, "TermDBHandler is singleton"
        TermDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()        
        BasicDBHandler.__init__(self,db, 'ClicklogTerm') 
        
        
    def getNumTerms(self):
        """returns number of terms stored"""
        return self.getOne("count(*)")
    
 
    
    def bulkInsertTerms(self, terms, commit=True):
        for term in terms:
            term_id = self.getTermIDNoInsert(term)
            if not term_id:
                self.insertTerm(term, commit=False) # this HAS to commit, otherwise last_insert_row_id() won't work. 
            # if you want to avoid committing too often, use bulkInsertTerm
        if commit:         
            self.commit()
            
    def getTermIDNoInsert(self, term):
        return self.getOne('term_id', term=term[:MAX_KEYWORD_LENGTH].lower())
            
    def getTermID(self, term):
        """returns the ID of term in table ClicklogTerm; creates a new entry if necessary"""
        term_id = self.getTermIDNoInsert(term)
        if term_id:
            return term_id
        else:
            self.insertTerm(term, commit=True) # this HAS to commit, otherwise last_insert_row_id() won't work. 
            return self.getOne("last_insert_rowid()")
    
    def insertTerm(self, term, commit=True):
        """creates a new entry for term in table Term"""
        self._db.insert(self.table_name, commit=commit, term=term[:MAX_KEYWORD_LENGTH])
    
    def getTerm(self, term_id):
        """returns the term for a given term_id"""
        return self.getOne("term", term_id=term_id)
        # if term_id==-1:
        #     return ""
        # term = self.getOne('term', term_id=term_id)
        # try:
        #     return str2bin(term)
        # except:
        #     return term
    
    def getTermsStartingWith(self, beginning, num=10):
        """returns num most frequently encountered terms starting with beginning"""
        
        # request twice the amount of hits because we need to apply
        # the familiy filter...
        terms = self.getAll('term', 
                            term=("like", u"%s%%" % beginning),
                            order_by="times_seen DESC",
                            limit=num * 2)

        if terms:
            # terms is a list containing lists. We only want the first
            # item of the inner lists.
            terms = [term for (term,) in terms]

            catobj = Category.getInstance()
            if catobj.family_filter_enabled():
                return filter(lambda term: not catobj.xxx_filter.foundXXXTerm(term), terms)[:num]
            else:
                return terms[:num]

        else:
            return []
    
    def getAllEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("term_id, term", order_by="term_id")
    
class SimilarityDBHandler:
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if SimilarityDBHandler.__single is None:
            SimilarityDBHandler.lock.acquire()   
            try:
                if SimilarityDBHandler.__single is None:
                    SimilarityDBHandler(*args, **kw)
            finally:
                SimilarityDBHandler.lock.release()
        return SimilarityDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if SimilarityDBHandler.__single is not None:
            raise RuntimeError, "SimilarityDBHandler is singleton"
        SimilarityDBHandler.__single = self
        self._db = SQLiteCacheDB.getInstance()
    
    def getOverlapWithPeer(self, peer_id, myprefs):
        sql_get_overlap_with_peer = """SELECT Peer.peer_id, num_prefs, COUNT(torrent_id) FROM Peer
                                        JOIN Preference ON Peer.peer_id = Preference.peer_id 
                                        WHERE torrent_id IN("""+','.join(map(str,myprefs))+""") 
                                        AND Peer.peer_id = ? GROUP BY Peer.peer_id"""
        row = self._db.fetchone(sql_get_overlap_with_peer, (peer_id,))
        return row
    
    def getPeersWithOverlap(self, not_peer_id, myprefs):
        sql_get_peers_with_overlap = """SELECT Peer.peer_id, num_prefs, COUNT(torrent_id) FROM Peer
                                        JOIN Preference ON Peer.peer_id = Preference.peer_id 
                                        WHERE torrent_id IN("""+','.join(map(str,myprefs))+""") 
                                        AND Peer.peer_id <> ? GROUP BY Peer.peer_id"""
        row = self._db.fetchall(sql_get_peers_with_overlap, (not_peer_id,))
        return row
    
    def getTorrentsWithSimilarity(self, myprefs, top_x):
        sql_get_torrents_with_similarity = """SELECT similarity, torrent_id FROM Peer
                                              JOIN Preference ON Peer.peer_id = Preference.peer_id
                                              WHERE Peer.peer_id IN(Select peer_id from Peer WHERE similarity > 0 ORDER By similarity DESC Limit ?)
                                              AND torrent_id NOT IN(""" + ','.join(map(str,myprefs))+""")"""
        row = self._db.fetchall(sql_get_torrents_with_similarity, (top_x,))
        return row
    
                 
                                        

class SearchDBHandler(BasicDBHandler):
    
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if SearchDBHandler.__single is None:
            SearchDBHandler.lock.acquire()   
            try:
                if SearchDBHandler.__single is None:
                    SearchDBHandler(*args, **kw)
            finally:
                SearchDBHandler.lock.release()
        return SearchDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if SearchDBHandler.__single is not None:
            raise RuntimeError, "SearchDBHandler is singleton"
        SearchDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self,db, 'ClicklogSearch') ## self,db,'Search'
        
        
    ### write methods
    
    def storeKeywordsByID(self, peer_id, torrent_id, term_ids, commit=True):
        sql_insert_search = u"INSERT INTO ClicklogSearch (peer_id, torrent_id, term_id, term_order) values (?, ?, ?, ?)"
        
        if len(term_ids)>MAX_KEYWORDS_STORED:
            term_ids= term_ids[0:MAX_KEYWORDS_STORED]

        # TODO before we insert, we should delete all potentially existing entries
        # with these exact values
        # otherwise, some strange attacks might become possible
        # and again we cannot assume that user/torrent/term only occurs once
        
        # vliegendhart: only store 1 query per (peer_id,torrent_id)
        # Step 1: fetch current stored term_ids, if any, and decrease count
        old_term_ids = self.getTorrentSearchTerms(torrent_id, peer_id) # list of 1-tuples
        sql_update_term_popularity= u"UPDATE ClicklogTerm SET times_seen = times_seen-1 WHERE term_id=?"        
        self._db.executemany(sql_update_term_popularity, old_term_ids, commit=commit)
        # Step 2: delete (peer_id,torrent_id) records, if any
        self._db.execute_write("DELETE FROM ClicklogSearch WHERE peer_id=? AND torrent_id=?", [peer_id,torrent_id])
        # TODO: Consider putting a UNIQUE constraint on (peer_id,torrent_id,term_order) in the schema?
        
        # create insert data
        values = [(peer_id, torrent_id, term_id, term_order) 
                  for (term_id, term_order) 
                  in zip(term_ids, range(len(term_ids)))]
        self._db.executemany(sql_insert_search, values, commit=commit)        
        
        # update term popularity
        sql_update_term_popularity= u"UPDATE ClicklogTerm SET times_seen = times_seen+1 WHERE term_id=?"        
        self._db.executemany(sql_update_term_popularity, [[term_id] for term_id in term_ids], commit=commit)        
        
    def storeKeywords(self, peer_id, torrent_id, terms, commit=True):
        """creates a single entry in Search with peer_id and torrent_id for every term in terms"""
        terms = [term.strip() for term in terms if len(term.strip())>0]
        term_db = TermDBHandler.getInstance()
        term_ids = [term_db.getTermID(term) for term in terms]
        self.storeKeywordsByID(peer_id, torrent_id, term_ids, commit)

    def getAllEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("rowid, peer_id, torrent_id, term_id, term_order ", order_by="rowid")
    
    def getAllOwnEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("rowid, peer_id, torrent_id, term_id, term_order ", where="peer_id=0", order_by="rowid")
    

    
    ### read methods
    
    def getNumTermsPerTorrent(self, torrent_id):
        """returns the number of terms associated with a given torrent"""
        return self.getOne("COUNT (DISTINCT term_id)", torrent_id=torrent_id)
        
    def getNumTorrentsPerTerm(self, term_id):
        """returns the number of torrents stored with a given term."""
        return self.getOne("COUNT (DISTINCT torrent_id)", term_id=term_id)
    
    def getNumTorrentTermCooccurrences(self, term_id, torrent_id):
        """returns the number of times a torrent has been associated with a term"""
        return self.getOne("COUNT (*)", term_id=term_id, torrent_id=torrent_id)    
    
    def getRelativeTermFrequency(self, term_id, torrent_id):
        """returns the relative importance of a term for a torrent
        This is basically tf/idf 
        term frequency tf = # keyword used per torrent/# keywords used with torrent at all
        inverse document frequency = # of torrents associated with term at all
        
        normalization in tf ensures that a torrent cannot get most important for all keywords just 
        by, e.g., poisoning the db with a lot of keywords for this torrent
        idf normalization ensures that returned values are meaningful across several keywords 
        """
        
        terms_per_torrent = self.getNumTermsPerTorrent(torrent_id)
        if terms_per_torrent==0:
            return 0
        
        torrents_per_term = self.getNumTorrentsPerTerm(term_id)
        if torrents_per_term == 0:
            return 0
        
        coocc = self.getNumTorrentTermCooccurrences(term_id, torrent_id)
        
        tf = coocc/float(terms_per_torrent)
        idf = 1.0/math.log(torrents_per_term+1)
        
        return tf*idf
    
    
    def getTorrentSearchTerms(self, torrent_id, peer_id):
        return self.getAll("term_id", "torrent_id=%d AND peer_id=%s" % (torrent_id, peer_id), order_by="term_order")
    
    def getMyTorrentSearchTerms(self, torrent_id):
        return [x[0] for x in self.getTorrentSearchTerms(torrent_id, peer_id=0)]
    
    def getMyTorrentSearchTermsStr(self, torrent_id):
        sql = "SELECT distinct term FROM ClicklogSearch, ClicklogTerm WHERE ClicklogSearch.term_id = ClicklogTerm.term_id AND torrent_id = ? AND peer_id = ? ORDER BY term_order"
        return self._db.fetchall(sql, (torrent_id, 0))
                
    ### currently unused
                  
    def numSearchesWithTerm(self, term_id):
        """returns the number of searches stored with a given term. 
        I feel like I might miss something, but this should simply be the number of rows containing
        the term"""
        return self.getOne("COUNT (*)", term_id=term_id)
    
    def getNumTorrentPeers(self, torrent_id):
        """returns the number of users for a given torrent. if this should be used 
        extensively, an index on torrent_id might be in order"""
        return self.getOne("COUNT (DISTINCT peer_id)", torrent_id=torrent_id)
    
    def removeKeywords(self, peer_id, torrent_id, commit=True):
        """removes records of keywords used by peer_id to find torrent_id"""
        # TODO
        # would need to be called by deletePreference
        pass
    
    
class NetworkBuzzDBHandler(BasicDBHandler):
    """
    The Network Buzz database handler singleton for sampling the TermFrequency table
    and maintaining the TorrentBiTermPhrase table.
    """
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if NetworkBuzzDBHandler.__single is None:
            NetworkBuzzDBHandler.lock.acquire()   
            try:
                if NetworkBuzzDBHandler.__single is None:
                    NetworkBuzzDBHandler(*args, **kw)
            finally:
                NetworkBuzzDBHandler.lock.release()
        return NetworkBuzzDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if NetworkBuzzDBHandler.__single is not None:
            raise RuntimeError, "NetworkBuzzDBHandler is singleton"
        NetworkBuzzDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()      
        BasicDBHandler.__init__(self,db, 'TermFrequency')
        
        from Tribler.Core.Tag.Extraction import TermExtraction
        self.extractor = TermExtraction.getInstance()
        
    # Default sampling size (per freq category)
    # With an update period of 5s, there will be at most 12 updates per minute.
    # Each update consumes, say, 5 terms or phrases for a freq category, so about
    # 60 terms or phrases per minute. If we set the sample size to 50, each getBuzz()
    # call will give about 50 terms and 50 phrases, so 100 displayable items in total.
    # This means getBuzz() will get called about every 1.6 minute.
    DEFAULT_SAMPLE_SIZE = 50
    
    # Only consider terms that appear more than once
    MIN_FREQ = 2
    
    # "Stopword"-threshold for single terms. Multiplied by #torrents to get max_freq upperbound.
    STOPWORD_THRESHOLD = 0.20
    # ...but only apply this threshold when we have at least this many torrents:
    NUM_TORRENTS_THRESHOLD = 150
    
    # Partition parameters
    PARTITION_AT = (0.33, 0.67)
    
    # Tables from which can be sampled:
    TABLES = dict(
        TermFrequency = dict(
            table = 'TermFrequency',
            selected_fields = 'term',
            min_freq = 2
        ),
        TorrentBiTermPhrase = dict(
            table = '''
            (
                SELECT TF1.term || " " || TF2.term AS phrase,
                       COUNT(*) AS freq
                FROM TorrentBiTermPhrase P, TermFrequency TF1, TermFrequency TF2
                WHERE P.term1_id = TF1.term_id AND P.term2_id = TF2.term_id
                GROUP BY term1_id, term2_id
            )
            ''',
            selected_fields = 'phrase',
            min_freq = 1
        )
    )
    
    def addTorrent(self, torrent_id, torrent_name, commit=True):
        """
        Extracts terms and the bi-term phrase from the added Torrent and stores it in
        the TermFrequency and TorrentBiTermPhrase tables, respectively.
        
        @param torrent_id Identifier of the added Torrent.
        @param torrent_name Name of the added Torrent.
        @param commit Flag to indicate whether database changes should be committed.
        """
        keywords = split_into_keywords(torrent_name)
        terms = set(self.extractor.extractTerms(keywords))
        phrase = self.extractor.extractBiTermPhrase(keywords)
        
        update_terms_sql = u"""
            INSERT OR IGNORE INTO TermFrequency (term, freq) VALUES (?, 0);
            UPDATE TermFrequency SET freq = freq+1 WHERE term = ?;
            """
        ins_phrase_sql = u"""INSERT OR REPLACE INTO TorrentBiTermPhrase (torrent_id, term1_id, term2_id)
                                    SELECT ? AS torrent_id, TF1.term_id, TF2.term_id
                                    FROM TermFrequency TF1, TermFrequency TF2
                                    WHERE TF1.term = ? AND TF2.term = ?"""
            
        
        self._db.executemany(update_terms_sql, [(term,term) for term in terms], commit=False)
        if phrase is not None:
            self._db.execute_write(ins_phrase_sql, (torrent_id,) + phrase, commit=False)
        
        if commit:
            self.commit()
    
    def deleteTorrent(self, torrent_id, commit=True):
        """
        Updates the TorrentBiTermPhrase table to reflect the change that a Torrent
        has been deleted.
        
        Currently, the TermFrequency table remains unaffected.
        
        @param torrent_id Identifier of the deleted Torrent.
        @param commit Flag to indicate whether database changes should be committed.
        """
        self._db.delete('TorrentBiTermPhrase', commit=commit, torrent_id=torrent_id)
    
    def getBuzz(self, size= DEFAULT_SAMPLE_SIZE, with_freq=True, flat=False):
        """
        Samples both the TermFrequency and the TorrentBiTermPhrase table for high, 
        medium, and low frequent terms and phrases.
        
        @param size Number of terms/phrases to be sampled for each category (high frequent, 
        mid frequent, low frequent).
        @param with_freq Flag indicating whether the frequency for each term and phrase needs 
        to be returned as well. True by default.
        @param flat If True, this method returns a single triple with the two samples merged,
        instead of two separate triples for terms and phrases. Default: False.
        @return When flat=False, two triples containing a sample of high, medium and low frequent 
        terms (in that order) for the first triple, and a sample of high, medium and low frequent
        prases for the second triple. When flat=True, these two triples are merged into a single 
        triple. If with_freq=True, each sample is a list of (term,freq) tuples, 
        otherwise it is a list of terms. 
        """
        num_torrents = self._db.getOne('CollectedTorrent', 'COUNT(torrent_id)')
        if num_torrents is None or num_torrents < self.NUM_TORRENTS_THRESHOLD:
            max_freq = None
        else:
            max_freq = int(round(num_torrents * self.STOPWORD_THRESHOLD))
        
        terms_triple = self.getBuzzForTable('TermFrequency', size, with_freq, max_freq = max_freq)
        phrases_triple = self.getBuzzForTable('TorrentBiTermPhrase', size, with_freq)
        if not flat:
            return terms_triple, phrases_triple
        else:
            return map(lambda t1,t2: (t1 or [])+(t2 or []), terms_triple, phrases_triple)
    
    def getBuzzForTable(self, table, size, with_freq=True, max_freq=None):
        """
        Retrieves a sample of high, medium and low frequent terms or phrases, paired
        with their frequencies, depending on the table to be sampled from.
        
        @table Table to retrieve the highest frequency from. Must be a key in 
        NetworkBuzzDBHandler.TABLES.
        @param size Number of terms/phrases to be sampled for each category (high frequent, 
        mid frequent, low frequent).
        @param with_freq Flag indicating whether the frequency for each term/phrase needs 
        to be returned as well. True by default.
        @param max_freq Optional. When set, high frequent terms or phrases occurring more than
        max_freq times are not included. Default: None (i.e., include all).
        @return Triple containing a sample of high, medium and low frequent 
        terms/phrases (in that order). If with_freq=True, each sample is a list of (term,freq) 
        tuples, otherwise it is a list of terms. 
        """
        # Partition using a ln-scale
        M = self._max(table, max_freq=max_freq)
        if M is None:
            return ()
        lnM = math.log(M)
        
        min_freq = self.TABLES[table]['min_freq']
        a, b = [int(round(math.exp(boundary*lnM))) for boundary in self.PARTITION_AT]
        a = max(min_freq, a)
        
        ranges = (
            (b, max_freq),
            (a, b),
            (min_freq, a)
        )
        # ...and sample each range
        return tuple(self._sample(table, range, size, with_freq=with_freq) for range in ranges)
    
    def _max(self, table, max_freq=None):
        """
        Internal method to select the highest occurring term or phrase frequency,
        depending on the table parameter.
        
        @param table Table to retrieve the highest frequency from. Must be a key in 
        NetworkBuzzDBHandler.TABLES.
        @param max_freq Optional. When set, high frequent terms or phrases occurring more than
        max_freq times are not considered in determining the highest frequency. 
        Default: None (i.e., consider all). 
        @return Highest occurring frequency.
        """
        sql = 'SELECT MAX(freq) FROM %s WHERE freq >= %s' % (self.TABLES[table]['table'], self.MIN_FREQ)
        if max_freq is not None:
            sql += ' AND freq < %s' % max_freq
        return self._db.fetchone(sql)
    
    def _sample(self, table, range, samplesize, with_freq=True):
        """
        Internal method to randomly select terms or phrases within a certain frequency 
        range, depending on the table parameter
        
        @table Table to sample from. Must be a key in NetworkBuzzDBHandler.TABLES. 
        @param range Pair (N,M) to select random terms or phrases that occur at least N 
        times, but less than M times. If M is None, no upperbound is used.
        @param samplesize Number of terms or phrases to select.
        @param with_freq Flag indicating whether the frequency for each term needs 
        to be returned as well. True by default.
        @return A list of (term_or_phrase,freq) pairs if with_freq=True,
        otherwise a list of terms or phrases.  
        """
        if not samplesize or samplesize < 0:
            return []
        
        minfreq, maxfreq = range
        if maxfreq is not None:
            whereclause = 'freq BETWEEN %s AND %s' % (minfreq, maxfreq-1)
        else:
            whereclause = 'freq >= %s' % minfreq
        
        selected_fields = self.TABLES[table]['selected_fields']
        if with_freq:
            selected_fields += ', freq'
        
        sql = '''SELECT %s
                 FROM %s
                 WHERE %s
                 ORDER BY random()
                 LIMIT %s''' % (selected_fields, self.TABLES[table]['table'], whereclause, samplesize)
        res = self._db.fetchall(sql)
        if not with_freq:
            res = map(lambda x: x[0], res)
        return res
    
    def getTermsStartingWith(self, beginning, num = 10):
        terms = None

        words = beginning.split()
        if len(words) < 3:
            if beginning[-1] == ' ' or len(words) > 1:
                termid = self.getOne('term_id', term=("=", words[0]))
                if termid:
                    sql = '''SELECT "%s " || TF.term AS phrase
                             FROM TorrentBiTermPhrase P, TermFrequency TF
                             WHERE P.term1_id = ? 
                             AND P.term2_id = TF.term_id '''%words[0]
                    if len(words) > 1:
                        sql += 'AND TF.term like "%s%%" '%words[1]
                    sql +='''GROUP BY term1_id, term2_id
                             ORDER BY freq DESC
                             LIMIT ?'''
                    terms = self._db.fetchall(sql, (termid, num))
            else:
                terms = self.getAll('term', 
                                    term=("like", u"%s%%" % beginning),
                                    order_by="freq DESC",
                                    limit=num * 2)
        
        if terms:
            # terms is a list containing lists. We only want the first
            # item of the inner lists.
            terms = [term for (term,) in terms]

            catobj = Category.getInstance()
            if catobj.family_filter_enabled():
                return filter(lambda term: not catobj.xxx_filter.foundXXXTerm(term), terms)[:num]
            else:
                return terms[:num]
        else:
            return []


class UserEventLogDBHandler(BasicDBHandler):
    """
    The database handler for logging user events.
    """
    __single = None    # used for multithreaded singletons pattern
    lock = threading.Lock()
    
    # maximum number of events to store
    # when this maximum is reached, approx. 50% of teh entries are deleted.
    MAX_EVENTS = 2*10000
    
    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if UserEventLogDBHandler.__single is None:
            UserEventLogDBHandler.lock.acquire()   
            try:
                if UserEventLogDBHandler.__single is None:
                    UserEventLogDBHandler(*args, **kw)
            finally:
                UserEventLogDBHandler.lock.release()
        return UserEventLogDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if UserEventLogDBHandler.__single is not None:
            raise RuntimeError, "UserEventLogDBHandler is singleton"
        UserEventLogDBHandler.__single = self
        db = SQLiteCacheDB.getInstance()      
        BasicDBHandler.__init__(self,db, 'UserEventLog')
        
        self.count = self._db.size(self.table_name)
    
    def addEvent(self, message, type=1, timestamp=None):
        """
        Log a user event to the database. Commits automatically.
        
        @param message A message (string) describing the event.
        @param type Optional type of event (default: 1). There is no
        mechanism to register user event types.
        @param timestamp Optional timestamp of the event. If omitted,
        the current time is used.
        """
        if timestamp is None:
            timestamp = time()
        self._db.insert(self.table_name, commit=False,
                        timestamp=timestamp, type=type, message=message)
        
        self.count += 1
        if self.count > UserEventLogDBHandler.MAX_EVENTS:
            sql=\
            '''
            DELETE FROM UserEventLog
            WHERE timestamp < (SELECT MIN(timestamp)
                               FROM (SELECT timestamp
                                     FROM UserEventLog
                                     ORDER BY timestamp DESC LIMIT %s))
            ''' % (UserEventLogDBHandler.MAX_EVENTS / 2)
            self._db.execute_write(sql, commit=True)
            self.count = self._db.size(self.table_name)
        else:
            self._db.commit()
            
        
    
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
        return ranks.index(key)+1
    except:
        return -1
    
