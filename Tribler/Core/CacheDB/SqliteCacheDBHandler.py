# Written by Jie Yang
# Modified by George Milescu
# see LICENSE.txt for license information
# Note for Developers: Please write a unittest in Tribler/Test/test_sqlitecachedbhandler.py
# for any function you add to database.
# Please reuse the functions in sqlitecachedb as much as possible

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL, SQLiteNoCacheDB
from copy import deepcopy, copy
from traceback import print_exc, print_stack
from time import time
from binascii import hexlify
from Tribler.Core.TorrentDef import TorrentDef
import sys
import os
import socket
import threading
import base64
import urllib
from random import randint, sample, choice
import math
import re
from sets import Set
from struct import unpack_from

from maxflow import Network
from math import atan, pi

from Tribler.Core.Utilities.bencode import bencode, bdecode
from Notifier import Notifier
from Tribler.Core.simpledefs import *
from Tribler.Core.Search.SearchManager import split_into_keywords, \
    filter_keywords
from Tribler.Core.Utilities.unicode import name2unicode, dunno2unicode
from Tribler.Category.Category import Category
from Tribler.Core.defaults import DEFAULTPORT
from threading import currentThread, RLock, Lock
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
import binascii

try:
    WindowsError
except NameError:
    WindowsError = Exception

# maxflow constants
MAXFLOW_DISTANCE = 2
ALPHA = float(1) / 30000

DEBUG = False
SHOW_ERROR = False

MAX_KEYWORDS_STORED = 5
MAX_KEYWORD_LENGTH = 50

# Rahim:
MAX_POPULARITY_REC_PER_TORRENT = 5  # maximum number of records in popularity table for each torrent
MAX_POPULARITY_REC_PER_TORRENT_PEER = 3  # maximum number of records per each combination of torrent and peer

from Tribler.Core.Search.SearchManager import split_into_keywords


def show_permid_shorter(permid):
    if not permid:
        return 'None'
    s = base64.encodestring(permid).replace("\n", "")
    return s[-5:]


class BasicDBHandler:
    _singleton_lock = RLock()
    _single = None

    def __init__(self, db, table_name):  # # self, table_name
        self._db = db  # # SQLiteCacheDB.getInstance()
        self.table_name = table_name
        self.notifier = Notifier.getInstance()

    @classmethod
    def getInstance(cls, *args, **kargs):
        with cls._singleton_lock:
            if not cls._single:
                cls._single = cls(*args, **kargs)
            return cls._single

    @classmethod
    def delInstance(cls):
        with cls._singleton_lock:
            cls._single = None

    @classmethod
    def hasInstance(cls):
        return cls._single != None

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


NETW_MIME_TYPE = 'image/jpeg'


class PeerDBHandler(BasicDBHandler):

    gui_value_name = ('permid', 'name', 'ip', 'port', 'similarity', 'friend',
                      'num_peers', 'num_torrents', 'num_prefs',
                      'connected_times', 'buddycast_times', 'last_connected',
                      'is_local', 'services')

    def __init__(self):
        if PeerDBHandler._single:
            raise RuntimeError("PeerDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Peer')  # # self, db ,'Peer'

    def __len__(self):
        return self.size()

    def getPeerID(self, permid):
        return self._db.getPeerID(permid)

    def getPeerIDS(self, permids):
        return self._db.getPeerIDS(permids)

    def addOrGetPeerID(self, permid):
        peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            self.addPeer(permid, {})
            peer_id = self._db.getPeerID(permid)

        return peer_id

    def addOrGetPeerIDS(self, permids):
        peer_ids = self._db.getPeerIDS(permids)

        to_be_inserted = []
        for i, peer_id in enumerate(peer_ids):
            if peer_id is None:
                to_be_inserted.append(permids[i])

        sql = "INSERT OR IGNORE INTO Peer (permid) VALUES (?)"
        self._db.executemany(sql, [(bin2str(permid),) for permid in to_be_inserted])
        return self._db.getPeerIDS(permids)

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

    def getPeerList(self, peerids=None):  # get the list of all peers' permid
        if peerids is None:
            permid_strs = self.getAll('permid')
            return [str2bin(permid_str[0]) for permid_str in permid_strs]
        else:
            if not peerids:
                return []
            s = str(peerids).replace('[', '(').replace(']', ')')
#            if len(peerids) == 1:
# s = '(' + str(peerids[0]) + ')'    # tuple([1]) = (1,), syntax error for sql
#            else:
#                s = str(tuple(peerids))
            sql = 'select permid from Peer where peer_id in ' + s
            permid_strs = self._db.fetchall(sql)
            return [str2bin(permid_str[0]) for permid_str in permid_strs]

    def getPeers(self, peer_list, keys):  # get a list of dictionaries given peer list
        # BUG: keys must contain 2 entries, otherwise the records in all are single values??
        value_names = ",".join(keys)
        sql = 'select %s from Peer where permid=?;' % value_names
        all = []
        for permid in peer_list:
            permid_str = bin2str(permid)
            p = self._db.fetchone(sql, (permid_str,))
            all.append(p)

        peers = []
        for i in range(len(all)):
            p = all[i]
            peer = dict(zip(keys, p))
            peer['permid'] = peer_list[i]
            peers.append(peer)

        return peers

    def getLocalPeerList(self, max_peers, minoversion=None):  # return a list of peer_ids
        """Return a list of peerids for local nodes, then random local nodes"""

        sql = 'select permid from Peer where is_local=1 '
        if minoversion is not None:
            sql += 'and oversion >= ' + str(minoversion) + ' '
        # sql += 'ORDER BY friend DESC, random() limit %d'%max_peers
        sql += 'ORDER BY random() limit %d' % max_peers

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
            if 'ip' in value:
                _ip = value.pop('ip')
            if 'port' in value:
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

        # print >>sys.stderr,"sqldbhand: addPeer",`permid`,self._db.getPeerID(permid),`value`
        # print_stack()

    def hasPeer(self, permid):
        return self._db.hasPeer(permid)

    def findPeers(self, key, value):
        # only used by Connecter
        if key == 'permid':
            value = bin2str(value)
        res = self.getAll('permid', **{key: value})
        if not res:
            return []
        ret = []
        for p in res:
            ret.append({'permid': str2bin(p[0])})
        return ret

    def setPeerLocalFlag(self, permid, is_local, commit=True):
        # argv = {"is_local":int(is_local)}
        # updated = self._db.update(self.table_name, 'permid='+repr(bin2str(permid)), **argv)
        # if commit:
        #     self.commit()
        # return updated
        self._db.update(self.table_name, 'permid=' + repr(bin2str(permid)), commit=commit, is_local=int(is_local))

    def updatePeer(self, permid, commit=True, **argv):
        self._db.update(self.table_name, 'permid=' + repr(bin2str(permid)), commit=commit, **argv)
        self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)

        # print >>sys.stderr,"sqldbhand: updatePeer",`permid`,argv
        # print_stack()

    def deletePeer(self, permid=None, peer_id=None, force=False, commit=True):
        # don't delete friend of superpeers, except that force is True
        if peer_id is None:
            peer_id = self._db.getPeerID(permid)
        if peer_id is None:
            return
        deleted = self._db.deletePeer(permid=permid, peer_id=peer_id, force=force, commit=commit)
        self.notifier.notify(NTFY_PEERS, NTFY_DELETE, permid)

    def updateTimes(self, permid, key, change=1, commit=True):
        permid_str = bin2str(permid)
        sql = "SELECT peer_id,%s FROM Peer WHERE permid==?" % key
        find = self._db.fetchone(sql, (permid_str,))
        if find:
            peer_id, value = find
            if value is None:
                value = 1
            else:
                value += change
            sql_update_peer = "UPDATE Peer SET %s=? WHERE peer_id=?" % key
            self._db.execute_write(sql_update_peer, (value, peer_id), commit=commit)
        self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)

    def updatePeerSims(self, sim_list, commit=True):
        sql_update_sims = 'UPDATE Peer SET similarity=? WHERE peer_id=?'
        s = time()
        self._db.executemany(sql_update_sims, sim_list, commit=commit)

    def getPermIDByIP(self, ip):
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

    def getPermids(self, peer_ids):
        parameters = '?,' * len(peer_ids)
        sql = "SELECT permid, peer_id FROM Peer WHERE peer_id IN (" + parameters[:-1] + ")"

        results = {}
        for permid, peer_id in self._db.fetchall(sql, peer_ids):
            results[peer_id] = str2bin(permid)

        to_return = []
        for peer_id in peer_ids:
            if peer_id in results:
                to_return.append(results[peer_id])
            else:
                to_return.append(None)
        return to_return

    def getNumberPeers(self, category_name='all'):
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

    def getRanks(self):
        value_name = 'permid'
        order_by = 'similarity desc'
        rankList_size = 20
        where = '(last_connected>0 or friend=1) '
        res_list = self._db.getAll('Peer', value_name, where=where, limit=rankList_size, order_by=order_by)
        return [a[0] for a in res_list]

    def registerConnectionUpdater(self, session):
        pass

    def updatePeerIcon(self, permid, icontype, icondata, commit=True):
        # save thumb in db
        self.updatePeer(permid, thumbnail=bin2str(icondata))
        # if self.mm is not None:
        #    self.mm.save_data(permid, icontype, icondata)

    def getPeerIcon(self, permid):
        item = self.getOne('thumbnail', permid=bin2str(permid))
        if item:
            return NETW_MIME_TYPE, str2bin(item)
        else:
            return None, None
        # if self.mm is not None:
        #    return self.mm.load_data(permid)
        # 3else:
        #    return None

    def getPeerIconByPeerId(self, peerid):
        item = self.getOne('thumbnail', peer_id=peerid)
        if item:
            return NETW_MIME_TYPE, str2bin(item)
        else:
            return None, None

    def searchNames(self, kws):
        return doPeerSearchNames(self, 'Peer', kws)


class TorrentDBHandler(BasicDBHandler):

    def __init__(self):
        if TorrentDBHandler._single is not None:
            raise RuntimeError("TorrentDBHandler is singleton")

        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'Torrent')  # # self,db,torrent

        self.status_table = {'good': 1, 'unknown': 0, 'dead': 2}
        self.status_table.update(self._db.getTorrentStatusTable())
        self.id2status = dict([(x, y) for (y, x) in self.status_table.items()])
        self.id2status[None] = 'unknown'
        self.torrent_dir = None
        # 0 - unknown
        # 1 - good
        # 2 - dead

        self.category_table = {u'Video': 1,
                                u'VideoClips': 2,
                                u'Audio': 3,
                                u'Compressed': 4,
                                u'Document': 5,
                                u'Picture': 6,
                                u'xxx': 7,
                                u'other': 8, }
        self.category_table.update(self._db.getTorrentCategoryTable())
        self.category_table[u'unknown'] = 0

        self.id2category = dict([(x, y) for (y, x) in self.category_table.items()])
        self.id2category[None] = u'unknown'
        # 1 - Video
        # 2 - VideoClips
        # 3 - Audio
        # 4 - Compressed
        # 5 - Document
        # 6 - Picture
        # 7 - xxx
        # 8 - other

        self.src_table = self._db.getTorrentSourceTable()
        self.id2src = dict([(x, y) for (y, x) in self.src_table.items()])
        self.id2src[None] = u'unknown'

        # 0 - ''    # local added
        # 1 - BC
        # 2,3,4... - URL of RSS feed
        self.keys = ['torrent_id', 'name', 'torrent_file_name',
                'length', 'creation_date', 'num_files', 'thumbnail',
                'insert_time', 'secret', 'relevance',
                'source_id', 'category_id', 'status_id',
                'num_seeders', 'num_leechers', 'comment', 'swift_hash', 'swift_torrent_hash',
                'tracker_check_retries',
                'last_tracker_check', 'trackers']
        self.existed_torrents = set()

        self.value_name = ['C.torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
                      'num_leechers', 'num_seeders', 'length',
                      'secret', 'insert_time', 'source_id', 'torrent_file_name',
                      'relevance', 'infohash',
                      'trackers', 'last_tracker_check',
                      'tracker_check_retries']

        self.value_name_for_channel = ['C.torrent_id', 'infohash', 'name', 'torrent_file_name', 'length', 'creation_date', 'num_files', 'thumbnail', 'insert_time', 'secret', 'relevance', 'source_id', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'comment']
        self.category = Category.getInstance()

        self.mypref_db = self.votecast_db = self.channelcast_db = self._rtorrent_handler = None

    def register(self, torrent_dir):
        self.torrent_dir = torrent_dir

        self.mypref_db = MyPreferenceDBHandler.getInstance()
        self.votecast_db = VoteCastDBHandler.getInstance()
        self.channelcast_db = ChannelCastDBHandler.getInstance()
        self._rtorrent_handler = RemoteTorrentHandler.getInstance()
        self._nb = NetworkBuzzDBHandler.getInstance()

    def getTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        return self._db.getTorrentID(infohash)

    def getTorrentIDRoot(self, roothash):
        assert isinstance(roothash, str), "roothash has invalid type: %s" % type(roothash)
        assert len(roothash) == INFOHASH_LENGTH, "roothash has invalid length: %d" % len(roothash)
        return self._db.getTorrentIDRoot(roothash)

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
        if infohash in self.existed_torrents:  # to do: not thread safe
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

    def addExternalTorrentNoDef(self, infohash, name, files, trackers, timestamp, source, extra_info={}):
        if not self.hasTorrent(infohash):
            metainfo = {'info': {}, 'encoding': 'utf_8'}
            metainfo['info']['name'] = name.encode('utf_8')
            metainfo['info']['piece length'] = -1
            metainfo['info']['pieces'] = ''

            if len(files) > 1:
                files_as_dict = []
                for filename, file_lenght in files:
                    filename = filename.encode('utf_8')
                    files_as_dict.append({'path': [filename], 'length': file_lenght})
                metainfo['info']['files'] = files_as_dict

            elif len(files) == 1:
                metainfo['info']['length'] = files[0][1]
            else:
                return

            if len(trackers) > 0:
                metainfo['announce'] = trackers[0]
            else:
                metainfo['nodes'] = []

            metainfo['creation date'] = timestamp

            try:
                torrentdef = TorrentDef.load_from_dict(metainfo)
                torrentdef.infohash = infohash

                torrent_id = self._addTorrentToDB(torrentdef, source, extra_info, False)
                self._rtorrent_handler.notify_possible_torrent_infohash(infohash)

                insert_files = [(torrent_id, unicode(path), length) for path, length in files]
                if len(insert_files) > 0:
                    sql_insert_files = "INSERT OR IGNORE INTO TorrentFiles (torrent_id, path, length) VALUES (?,?,?)"
                    self._db.executemany(sql_insert_files, insert_files, commit=False)

                magnetlink = u"magnet:?xt=urn:btih:" + hexlify(infohash)
                for tracker in trackers:
                    magnetlink += "&tr=" + urllib.quote_plus(tracker)
                insert_collecting = [(torrent_id, magnetlink)]

                if len(insert_collecting) > 0:
                    sql_insert_collecting = "INSERT OR IGNORE INTO TorrentCollecting (torrent_id, source) VALUES (?,?)"
                    self._db.executemany(sql_insert_collecting, insert_collecting, False)
            except:
                print >> sys.stderr, "Could not create a TorrentDef instance", infohash, timestamp, name, files, trackers, source, extra_info
                print_exc()

    def addInfohash(self, infohash, commit=True):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)
        if self._db.getTorrentID(infohash) is None:
            self._db.insert_or_ignore('Torrent', commit=commit, infohash=bin2str(infohash))

    def addOrGetTorrentID(self, infohash):
        assert isinstance(infohash, str), "INFOHASH has invalid type: %s" % type(infohash)
        assert len(infohash) == INFOHASH_LENGTH, "INFOHASH has invalid length: %d" % len(infohash)

        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            self._db.insert('Torrent', commit=True, infohash=bin2str(infohash), status_id=self._getStatusID("good"))
            torrent_id = self._db.getTorrentID(infohash)
        return torrent_id

    def addOrGetTorrentIDRoot(self, roothash, name):
        assert isinstance(roothash, str), "roothash has invalid type: %s" % type(roothash)
        assert len(roothash) == INFOHASH_LENGTH, "roothash has invalid length: %d" % len(roothash)

        torrent_id = self._db.getTorrentIDRoot(roothash)
        if torrent_id is None:
            infohash = 'swift' + bin2str(roothash)[5:]
            self._db.insert('Torrent', commit=True, infohash=infohash, swift_hash=bin2str(roothash), name=name, status_id=self._getStatusID("good"))
            torrent_id = self._db.getTorrentIDRoot(roothash)
        return torrent_id

    def addOrGetTorrentIDS(self, infohashes):
        torrentIds, _ = self.addOrGetTorrentIDSReturn(infohashes)
        return torrentIds

    def addOrGetTorrentIDSReturn(self, infohashes):
        to_be_inserted = []
        torrent_ids = self._db.getTorrentIDS(infohashes)
        for i in range(len(torrent_ids)):
            torrent_id = torrent_ids[i]
            if torrent_id is None:
                to_be_inserted.append(infohashes[i])

        status_id = self._getStatusID("good")
        sql = "INSERT OR IGNORE INTO Torrent (infohash, status_id) VALUES (?, ?)"
        self._db.executemany(sql, [(bin2str(infohash), status_id) for infohash in to_be_inserted])
        return self._db.getTorrentIDS(infohashes), to_be_inserted

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
            src_int = self._insertNewSrc(src)  # add a new src, e.g., a RSS feed
            self.src_table[src] = src_int
            self.id2src[src_int] = src
        return src_int

    def _get_database_dict(self, torrentdef, source="BC", extra_info={}):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        assert torrentdef.is_finalized(), "TORRENTDEF is not finalized"
        mime, thumb = torrentdef.get_thumbnail()

        dict = {"infohash": bin2str(torrentdef.get_infohash()),
                "name": torrentdef.get_name_as_unicode(),
                "torrent_file_name": extra_info.get("filename", None),
                "length": torrentdef.get_length(),
                "creation_date": torrentdef.get_creation_date(),
                "num_files": len(torrentdef.get_files()),
                "thumbnail": bool(thumb),
                "insert_time": long(time()),
                "secret": 0,  # todo: check if torrent is secret
                "relevance": 0.0,
                "source_id": self._getSourceID(source),
                # todo: the category_id is calculated directly from
                # torrentdef.metainfo, the category checker should use
                # the proper torrentdef api
                "category_id": self._getCategoryID(self.category.calculateCategory(torrentdef.metainfo, torrentdef.get_name_as_unicode())),
                "status_id": self._getStatusID(extra_info.get("status", "unknown")),
                "num_seeders": extra_info.get("seeder", -1),
                "num_leechers": extra_info.get("leecher", -1),
                "comment": torrentdef.get_comment_as_unicode()
                }

        if extra_info.get('swift_hash', ''):
            dict['swift_hash'] = bin2str(extra_info['swift_hash'])

        if extra_info.get('swift_torrent_hash', ''):
            dict['swift_torrent_hash'] = bin2str(extra_info['swift_torrent_hash'])

        return dict

    def _addTorrentToDB(self, torrentdef, source, extra_info, commit):
        assert isinstance(torrentdef, TorrentDef), "TORRENTDEF has invalid type: %s" % type(torrentdef)
        assert torrentdef.is_finalized(), "TORRENTDEF is not finalized"

        infohash = torrentdef.get_infohash()
        swarmname = torrentdef.get_name_as_unicode()
        database_dict = self._get_database_dict(torrentdef, source, extra_info)

        # see if there is already a torrent in the database with this infohash
        torrent_id = self._db.getTorrentID(infohash)

        if torrent_id is None:  # not in database
            self._db.insert("Torrent", commit=True, **database_dict)
            torrent_id = self._db.getTorrentID(infohash)

        else:  # infohash in db
            where = 'torrent_id = %d' % torrent_id
            self._db.update('Torrent', where=where, commit=False, **database_dict)

        if not torrentdef.is_multifile_torrent():
            swarmname, _ = os.path.splitext(swarmname)
        self._indexTorrent(torrent_id, swarmname, torrentdef.get_files_as_unicode(), source in ['BC', 'SWIFT', 'DISP_SC'])

        self._addTorrentTracker(torrent_id, torrentdef, extra_info, commit=False)
        if commit:
            self.commit()
        return torrent_id

    def _indexTorrent(self, torrent_id, swarmname, files, collected):
        existed = self._db.getOne('CollectedTorrent', 'infohash', torrent_id=torrent_id)
        if existed and not collected:
            return

        # Niels: new method for indexing, replaces invertedindex
        # Making sure that swarmname does not include extension for single file torrents
        swarm_keywords = " ".join(split_into_keywords(swarmname, filterStopwords=False))

        filedict = {}
        fileextensions = set()
        for filename in files:
            filename, extension = os.path.splitext(filename)
            for keyword in split_into_keywords(filename, filterStopwords=True):
                filedict[keyword] = filedict.get(keyword, 0) + 1

            fileextensions.add(extension[1:])

        filenames = filedict.keys()
        if len(filenames) > 1000:
            def popSort(a, b):
                return filedict[a] - filedict[b]
            filenames.sort(cmp=popSort, reverse=True)
            filenames = filenames[:1000]

        values = (torrent_id, swarm_keywords, " ".join(filenames), " ".join(fileextensions))
        try:
            # INSERT OR REPLACE not working for fts3 table
            self._db.execute_write(u"DELETE FROM FullTextIndex WHERE rowid = ?", (torrent_id,), commit=False)
            self._db.execute_write(u"INSERT INTO FullTextIndex (rowid, swarmname, filenames, fileextensions) VALUES(?,?,?,?)", values, commit=False)
        except:
            # this will fail if the fts3 module cannot be found
            print_exc()

        # vliegendhart: extract terms and bi-term phrase from Torrent and store it
        self._nb.addTorrent(torrent_id, swarmname, collected=collected, commit=False)

    def getInfohashFromTorrentName(self, name):  # #
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
        ignore_number = 0
        retry_number = 0
        last_check_time = 0
        if "last_check_time" in extra_info:
            last_check_time = int(time() - extra_info["last_check_time"])

        sql_insert_torrent_tracker = """
        INSERT OR IGNORE INTO TorrentTracker
        (torrent_id, tracker, announce_tier,
        ignored_times, retried_times, last_check)
        VALUES (?,?,?, ?,?,?)
        """

        values = []
        if announce != None:
            values.append((torrent_id, announce, 1, ignore_number, retry_number, last_check_time))

        # each torrent only has one announce with tier number 1
        tier_num = 2
        trackers = {announce: None}
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

    def updateTorrent(self, infohash, commit=True, notify=True, **kw):  # watch the schema of database
        if 'category' in kw:
            cat_id = self._getCategoryID(kw.pop('category'))
            kw['category_id'] = cat_id
        if 'status' in kw:
            status_id = self._getStatusID(kw.pop('status'))
            kw['status_id'] = status_id

        if 'progress' in kw:
            torrent_id = self._db.getTorrentID(infohash)
            if infohash:
                self.mypref_db.updateProgress(torrent_id, kw.pop('progress'), commit=False)  # commit at end of function
        if 'seeder' in kw:
            kw['num_seeders'] = kw.pop('seeder')
        if 'leecher' in kw:
            kw['num_leechers'] = kw.pop('leecher')
        #if 'last_check_time' in kw or 'ignore_number' in kw or 'retry_number' in kw \
        #  or 'retried_times' in kw or 'ignored_times' in kw:
        #    self.updateTracker(infohash, kw, commit=False)

        if 'retries' in kw:
            kw['tracker_check_retries'] = kw.pop('retries')
        if 'last_check' in kw:
            kw['last_tracker_check'] = kw.pop('last_check')
        if 'trackers' in kw:
            kw['trackers'] = kw.pop('trackers')

        if 'swift_hash' in kw:
            kw['swift_hash'] = bin2str(kw['swift_hash'])

        if 'swift_torrent_hash' in kw:
            kw['swift_torrent_hash'] = bin2str(kw['swift_torrent_hash'])

        for key in kw.keys():
            if key not in self.keys:
                kw.pop(key)

        if len(kw) > 0:
            infohash_str = bin2str(infohash)
            where = "infohash='%s'" % infohash_str
            self._db.update(self.table_name, where, commit=False, **kw)

        if commit:
            self.commit()

        if notify:
            self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)

    def on_torrent_collect_response(self, torrents):
        torrents = [(bin2str(torrent[0]), bin2str(torrent[1])) for torrent in torrents]

        infohashes = [infohash for infohash, _ in torrents if infohash]
        roothashes = [roothash for _, roothash in torrents if roothash]

        i_parameters = '?,' * len(infohashes)
        i_parameters = i_parameters[:-1]

        r_parameters = '?,' * len(roothashes)
        r_parameters = r_parameters[:-1]

        sql = "SELECT torrent_id, infohash, swift_torrent_hash FROM Torrent WHERE infohash in (" + i_parameters + ") or swift_torrent_hash in (" + r_parameters + ")"
        results = self._db.fetchall(sql, infohashes + roothashes)

        info_dict = {}
        root_dict = {}
        for torrent_id, infohash, roothash in results:
            if infohash.startswith('swift'):
                infohash = ''

            if infohash:
                info_dict[infohash] = torrent_id
            if roothash:
                root_dict[roothash] = torrent_id

        to_be_inserted = []
        update_infohash = []
        update_roothash = []
        for infohash, roothash in torrents:
            if infohash in info_dict and roothash in root_dict:
                continue
            elif infohash in info_dict:
                update_roothash.append((roothash, info_dict[infohash]))
            elif roothash in root_dict:
                update_infohash.append((infohash, root_dict[roothash]))
            else:
                to_be_inserted.append((infohash, roothash))

        if len(to_be_inserted) > 0:
            sql = "INSERT OR IGNORE INTO Torrent (infohash, swift_torrent_hash) VALUES (?, ?)"
            self._db.executemany(sql, to_be_inserted)

        if len(update_infohash) > 0:
            sql = "UPDATE Torrent SET infohash = ? WHERE torrent_id = ?"
            self._db.executemany(sql, update_infohash)

        if len(update_roothash) > 0:
            sql = "UPDATE Torrent SET swift_torrent_hash = ? WHERE torrent_id = ?"
            self._db.executemany(sql, update_roothash)

    def on_search_response(self, torrents):
        source_id = self._getSourceID("DISP_SEARCH")
        status_id = self._getStatusID("unknown")

        torrents = [(bin2str(torrent[0]), torrent[1], torrent[2], torrent[3], self.category_table.get(torrent[4][0], 0), torrent[5], bin2str(torrent[8]) if torrent[8] else '', bin2str(torrent[9]) if torrent[9] else '') for torrent in torrents]
        info_root = [(torrent[0], torrent[6] or '--') for torrent in torrents]

        sql = "SELECT torrent_id, infohash, swift_hash, torrent_file_name, name FROM Torrent WHERE infohash = ? or swift_hash = ?"
        results = self._db.executemany(sql, info_root) or []

        infohash_tid = {}
        roothash_tid = {}

        tid_collected = set()
        tid_name = {}
        for torrent_id, infohash, roothash, torrent_filename, name in results:
            infohash = str(infohash)
            roothash = str(roothash)

            if infohash.startswith('swift'):
                infohash = ''

            if infohash:
                infohash_tid[infohash] = torrent_id
            if roothash:
                roothash_tid[roothash] = torrent_id
            if torrent_filename:
                tid_collected.add(torrent_id)
            tid_name[torrent_id] = name

        insert = []
        update = []
        update_roothash = []
        update_infohash = []
        to_be_indexed = []
        for infohash, swarmname, length, nrfiles, categoryid, creation_date, swift_hash, swift_torrent_hash in torrents:
            # 12/07/12 Boudewijn: swift_hash must be unique in the database, hence empty strings
            # must be stored as None
            if swift_hash == "":
                swift_hash = None
            # 02/08/12 Boudewijn: swift_torrent_hash has the same issue as swift_hash above
            if swift_torrent_hash == "":
                swift_torrent_hash = None

            tid = infohash_tid.get(infohash, None) or roothash_tid.get(swift_hash, None)

            if tid:  # we know this torrent
                if tid not in tid_collected and swarmname != tid_name.get(tid, ''):  # if not collected and name not equal then do fullupdate
                    update.append((swarmname, length, nrfiles, categoryid, creation_date, infohash, swift_hash, swift_torrent_hash, source_id, status_id, tid))
                    to_be_indexed.append((tid, swarmname))

                elif swift_hash and swift_hash not in roothash_tid:  # else check if we need to update swift
                    update_roothash.append((swift_hash, tid))

                elif infohash and infohash not in infohash_tid:  # or infohash
                    update_infohash.append((infohash, tid))
            else:
                insert.append((swarmname, length, nrfiles, categoryid, creation_date, infohash, swift_hash, swift_torrent_hash, source_id, status_id))

        if len(update) > 0:
            sql = "UPDATE Torrent SET name = ?, length = ?, num_files = ?, category_id = ?, creation_date = ?, infohash = ?, swift_hash = ?, swift_torrent_hash = ?, source_id = ?, status_id = ? WHERE torrent_id = ?"
            self._db.executemany(sql, update)

        if len(update_roothash) > 0:
            sql = "UPDATE Torrent SET swift_hash = ? WHERE torrent_id = ?"
            self._db.executemany(sql, update_roothash)

        if len(update_infohash) > 0:
            sql = "UPDATE Torrent SET infohash = ? WHERE torrent_id = ?"
            self._db.executemany(sql, update_infohash)

        if len(insert) > 0:
            sql = "INSERT INTO Torrent (name, length, num_files, category_id, creation_date, infohash, swift_hash, swift_torrent_hash, source_id, status_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            try:
                self._db.executemany(sql, insert)

                were_inserted = [(inserted[5], inserted[7]) for inserted in insert]
                sql = "SELECT torrent_id, name FROM Torrent WHERE infohash = ? or swift_hash = ?"
                to_be_indexed = to_be_indexed + list(self._db.executemany(sql, were_inserted))
            except:
                print_exc()
                print >> sys.stderr, "infohashes:", insert

        for torrent_id, swarmname in to_be_indexed:
            self._indexTorrent(torrent_id, swarmname, [], False)

    def updateTracker(self, infohash, kw, tier=1, tracker=None, commit=True):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is None:
            return
        update = {}
        assert isinstance(kw, dict) and kw, 'updateTracker error: kw should be filled dict, but is: %s' % kw
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
            where = 'torrent_id=%d AND announce_tier=%d' % (torrent_id, tier)
        else:
            where = 'torrent_id=%d AND tracker=%s' % (torrent_id, repr(tracker))
        self._db.update('TorrentTracker', where, commit=commit, **update)

    def deleteTorrent(self, infohash, delete_file=False, commit=True):
        if not self.hasTorrent(infohash):
            return False

        torrent_id = self._db.getTorrentID(infohash)
        if self.mypref_db.hasMyPreference(torrent_id):  # don't remove torrents in my pref
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
                self._db.update(self.table_name, where="torrent_id=%d" % torrent_id, commit=commit, torrent_file_name=None)
            else:
                self._db.delete(self.table_name, commit=commit, torrent_id=torrent_id)
                # vliegendhart: synch bi-term phrase table
                self._nb.deleteTorrent(torrent_id, commit)
            if infohash in self.existed_torrents:
                self.existed_torrents.remove(infohash)
            self._db.delete('TorrentTracker', commit=commit, torrent_id=torrent_id)
            # print '******* delete torrent', torrent_id, `infohash`, self.hasTorrent(infohash)

    def eraseTorrentFile(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            torrent_dir = self.getTorrentDir()
            torrent_name = self.getOne('torrent_file_name', torrent_id=torrent_id)
            src = os.path.join(torrent_dir, torrent_name)
            if not os.path.exists(src):  # already removed
                return True

            try:
                os.remove(src)
            except Exception as msg:
                print >> sys.stderr, "cachedbhandler: failed to erase torrent", src, Exception, msg
                return False

        return True

    # ============================================================
    # MARK <BEGIN>: Added by Lipu Fei
    # ============================================================
    # ------------------------------------------------------------
    # Gets a list of torrents that have a given tracker.
    # ------------------------------------------------------------
    def getTorrentsOnTracker(self, tracker):
        sql = 'SELECT infohash, tracker_check_retries, last_tracker_check from Torrent WHERE trackers like ?'
        args = ['%' + tracker + '%']
        torrent_list = self._db.fetchall(sql, args)
        return [torrent for torrent in torrent_list]

    def getTrackerInfoList(self):
        sql = 'SELECT tracker, last_check, failures, is_alive FROM TrackerInfo'
        tracker_info_list = self._db.fetchall(sql)
        return [tracker_info for tracker_info in tracker_info_list]

    # ------------------------------------------------------------
    # Updates a tracker status into the TrackerInfo table.
    # ------------------------------------------------------------
    def updateTrackerInfo(self, tracker, last_check, failures, is_alive):
        sql = 'SELECT * FROM TrackerInfo WHERE tracker = ?'
        tracker_info_list = self._db.fetchall(sql, (tracker,))
        if not tracker_info_list:
            # insert a new record
            kw = [ (tracker, last_check, failures, is_alive) ]
            sql = 'INSERT INTO TrackerInfo(tracker, last_check, failures, is_alive)' \
                 + ' VALUES(?, ?, ?, ?)'
            self._db.executemany(sql, kw)
        else:
            # update the old one
            kw = dict()
            kw['last_check'] = last_check
            kw['failures'] = failures
            kw['is_alive'] = is_alive
            where = 'tracker = \'%s\'' % tracker
            self._db.update('TrackerInfo', where, **kw)

    # ============================================================
    # MARK <END>: Added by Lipu Fei
    # ============================================================

    def getTracker(self, infohash, tier=0):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            sql = "SELECT tracker, announce_tier FROM TorrentTracker WHERE torrent_id==%d" % torrent_id
            if tier > 0:
                sql += " AND announce_tier<=%d" % tier
            return self._db.fetchall(sql)

    def getTorrentsFromTracker(self, tracker, max_last_check, limit):
        sql = "SELECT infohash FROM TorrentTracker, Torrent WHERE Torrent.torrent_id = TorrentTracker.torrent_id AND tracker = ? AND last_check < ? ORDER BY RANDOM() LIMIT ?"
        infohashes = self._db.fetchall(sql, (tracker, max_last_check, limit))
        return [str2bin(infohash) for infohash, in infohashes]

    def getPopularTrackers(self, limit=10):
        sql = "SELECT DISTINCT tracker FROM torrenttracker WHERE ignored_times = 0 ORDER BY last_check DESC LIMIT ?"
        trackers = self._db.fetchall(sql, (limit,))
        return [tracker for tracker, in trackers]

    def getSwarmInfoByInfohash(self, infohash):
        sql = "SELECT t.torrent_id, t.num_seeders, t.num_leechers, max(last_check) FROM Torrent t, TorrentTracker tr WHERE t.torrent_id = tr.torrent_id AND t.infohash  = ?"
        return self._db.fetchone(sql, (bin2str(infohash),))

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
        sql += ','.join(map(str, torrent_id_list))
        sql += ") AND t.torrent_id = tr.torrent_id GROUP BY t.torrent_id"

        rows = self._db.fetchall(sql)
        for row in rows:
            torrent_id = row[0]
            num_seeders = row[1]
            num_leechers = row[2]
            last_check = row[3]
            results[torrent_id] = [torrent_id, num_seeders, num_leechers, last_check, -1, row]

        return results

    def getLargestSourcesSeen(self, torrent_id, timeNow, freshness= -1):
        """
        Returns the largest number of the sources that have seen the torrent.
        @author: Rahim
        @param torrent_id: the id of the torrent.
        @param freshness: A parameter that filters old records. The assumption is that those popularity reports that are
        older than a rate are not reliable
        @return: The largest number of the torrents that have seen the torrent.
        """

        if freshness == -1:
            sql2 = """SELECT MAX(num_of_sources) FROM Popularity WHERE torrent_id=%d""" % torrent_id
        else:
            latestValidTime = timeNow - freshness
            sql2 = """SELECT MAX(num_of_sources) FROM Popularity WHERE torrent_id=%d AND msg_receive_time > %d""" % (torrent_id, latestValidTime)

        othersSeenSources = self._db.fetchone(sql2)
        if othersSeenSources is None:
            othersSeenSources = 0
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
            # ('torrent_id', 'category_id', 'status_id', 'name', 'creation_date', 'num_files',
            # 'num_leechers', 'num_seeders',   'length',
            # 'secret', 'insert_time', 'source_id', 'torrent_file_name',
            # 'relevance', 'infohash', 'torrent_id')
        else:
            keys = list(keys)

        # TODO: to be removed
        #tracker_keys = ['tracker', 'announce_tier', 'ignored_times', 'retried_times', 'last_check']
        #tracker_keys = [key for key in tracker_keys if key in keys]
        #if len(tracker_keys) > 0:
        #    res = self._db.getOne('Torrent C LEFT JOIN TorrentTracker T ON C.torrent_id = T.torrent_id', keys, infohash=bin2str(infohash))
        #else:
        res = self._db.getOne('Torrent C', keys, infohash=bin2str(infohash))

        if not res:
            return None
        torrent = dict(zip(keys, res))
        if 'source_id' in torrent:
            torrent['source'] = self.id2src[torrent['source_id']]

        if 'category_id' in torrent:
            torrent['category'] = [self.id2category[torrent['category_id']]]

        if 'status_id' in torrent:
            torrent['status'] = self.id2status[torrent['status_id']]

        if 'swift_hash' in torrent and torrent['swift_hash']:
            torrent['swift_hash'] = str2bin(torrent['swift_hash'])

        if 'swift_torrent_hash' in torrent and torrent['swift_torrent_hash']:
            torrent['swift_torrent_hash'] = str2bin(torrent['swift_torrent_hash'])

        torrent['infohash'] = infohash

        # TODO: to be removed
        #if 'last_check' in torrent:
        #    torrent['last_check_time'] = torrent['last_check']
        if 'trackers' in torrent and torrent['trackers']:
            torrent['tracker_list'] = torrent['trackers'].split('\n')

        if include_mypref:
            tid = torrent['C.torrent_id']
            stats = self.mypref_db.getMyPrefStats(tid)

            if stats:
                torrent['myDownloadHistory'] = True
                torrent['creation_time'] = stats[tid][0]
                torrent['progress'] = stats[tid][1]
                torrent['destination_path'] = stats[tid][2]
            else:
                torrent['myDownloadHistory'] = False

        return torrent

    def getNumberTorrents(self, category_name='all', library=False):
        table = 'CollectedTorrent'
        value = 'count(torrent_id)'
        where = '1 '

        if category_name != 'all':
            where += ' and category_id= %d' % self.category_table.get(category_name.lower(), -1)  # unkown category_name returns no torrents
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

    def getTorrents(self, category_name='all', range=None, library=False, sort=None, reverse=False):
        """
        get Torrents of some category and with alive status (opt. not in family filter)

        if library == True: only torrents with destination_path != '' are returned
        else: return only good torrents, accepted by family filter

        @return Returns a list of dicts with keys:
            torrent_id, infohash, name, category, status, creation_date, num_files, num_leechers, num_seeders,
            length, secret, insert_time, source, torrent_filename, relevance, simRank, tracker, last_check
            (if in library: myDownloadHistory, download_started, progress, dest_dir)

        niels 25-10-2010: changed behaviour to left join TorrentTracker, due to magnet links
        """

        # print >> sys.stderr, 'TorrentDBHandler: getTorrents(%s, %s, %s, %s, %s)' % (category_name, range, library, sort, reverse)
        s = time()

        value_name = deepcopy(self.value_name)
        sql = 'Select ' + ','.join(value_name)
        sql += ' From CollectedTorrent C Left Join TorrentTracker T ON C.torrent_id = T.torrent_id'

        where = ''
        if category_name != 'all':
            where += 'category_id = %d AND' % self.category_table.get(category_name.lower(), -1)  # unkown category_name returns no torrents

        if library:
            where += 'C.torrent_id in (select torrent_id from MyPreference where destination_path != "")'
        else:
            where += 'status_id=%d ' % self.status_table['good']  # if not library, show only good files
            where += self.category.get_family_filter_sql(self._getCategoryID)  # add familyfilter

        sql += ' Where ' + where

        if 'infohash' in value_name:
            sql += " GROUP BY infohash"

        if range:
            offset = range[0]
            limit = range[1] - range[0]
            sql += ' Limit %d Offset %d' % (limit, offset)

        if sort:
            # Arno, 2008-10-6: buggy: not reverse???
            desc = (reverse) and 'desc' or ''
            if sort == 'name':
                sql += ' Order By lower(%s) %s' % (sort, desc)
            else:
                sql += ' Order By %s %s' % (sort, desc)

        # print >>sys.stderr,"TorrentDBHandler: GET TORRENTS val",value_name,"where",where,"limit",limit,"offset",offset,"order",order_by
        # print_stack

        # Must come before query
        ranks = self.getRanks()
        res_list = self._db.fetchall(sql)
        mypref_stats = self.mypref_db.getMyPrefStats() if self.mypref_db else None

        torrent_list = self.valuelist2torrentlist(value_name, res_list, ranks, mypref_stats)
        del res_list
        del mypref_stats
        return torrent_list

    def getLibraryTorrents(self, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM MyPreference, Torrent LEFT JOIN ChannelTorrents ON Torrent.torrent_id = ChannelTorrents.torrent_id WHERE destination_path != '' AND MyPreference.torrent_id = Torrent.torrent_id"
        data = self._db.fetchall(sql)

        fixed = self.__fixTorrents(keys, data)
        return fixed

    def valuelist2torrentlist(self, value_name, res_list, ranks, mypref_stats):

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
            torrent['simRank'] = ranksfind(ranks, torrent['infohash'])
            torrent['infohash'] = str2bin(torrent['infohash'])
            # torrent['num_swarm'] = torrent['num_seeders'] + torrent['num_leechers']
            torrent['last_check_time'] = torrent['last_check']
            del torrent['last_check']
            del torrent['source_id']

            # Niels: we now convert category and status in gui
            # del torrent['category_id']
            # del torrent['status_id']
            torrent_id = torrent['torrent_id']
            if mypref_stats is not None and torrent_id in mypref_stats:
                # add extra info for torrent in mypref
                torrent['myDownloadHistory'] = True
                data = mypref_stats[torrent_id]  # (create_time,progress,destdir)
                torrent['download_started'] = data[0]
                torrent['progress'] = data[1]
                torrent['destdir'] = data[2]

            # print >>sys.stderr,"TorrentDBHandler: GET TORRENTS",`torrent`

            torrent_list.append(torrent)
        return torrent_list

    def __fixTorrents(self, keys, results):
        def fix_value(key):
            if key in keys:
                key_index = keys.index(key)
                for i in range(len(results)):
                    result = list(results[i])
                    if result[key_index]:
                        result[key_index] = str2bin(result[key_index])
                        results[i] = result
        fix_value('infohash')
        fix_value('swift_hash')
        fix_value('swift_torrent_hash')
        return results

    def getRanks(self):
        value_name = 'infohash'
        order_by = 'relevance desc'
        rankList_size = 20
        where = 'status_id=%d ' % self.status_table['good']
        res_list = self._db.getAll('Torrent', value_name, where=where, limit=rankList_size, order_by=order_by)
        return [a[0] for a in res_list]

    def getNumberCollectedTorrents(self):
        # return self._db.size('CollectedTorrent')
        return self._db.getOne('CollectedTorrent', 'count(torrent_id)')

    def getRecentlyCollectedSwiftHashes(self, limit=50):
        sql = "SELECT swift_torrent_hash, infohash, num_seeders, num_leechers, last_check, insert_time FROM CollectedTorrent LEFT JOIN TorrentTracker ON CollectedTorrent.torrent_id = TorrentTracker.torrent_id WHERE swift_torrent_hash IS NOT NULL AND swift_torrent_hash <> '' ORDER BY insert_time DESC LIMIT ?"
        results = self._db.fetchall(sql, (limit,))
        return [[str2bin(result[0]), str2bin(result[1]), result[2], result[3], result[4] or 0, result[5]] for result in results]

    def getRandomlyCollectedSwiftHashes(self, insert_time, limit=50):
        sql = "SELECT swift_torrent_hash, infohash, num_seeders, num_leechers, last_check FROM CollectedTorrent LEFT JOIN TorrentTracker ON CollectedTorrent.torrent_id = TorrentTracker.torrent_id WHERE insert_time < ? AND swift_torrent_hash IS NOT NULL AND swift_torrent_hash <> '' ORDER BY RANDOM() DESC LIMIT ?"
        results = self._db.fetchall(sql, (insert_time, limit))
        return [[str2bin(result[0]), str2bin(result[1]), result[2], result[3], result[4] or 0] for result in results]

    def selectSwiftTorrentsToCollect(self, hashes):
        parameters = '?,' * len(hashes)
        parameters = parameters[:-1]

        # TODO: bias according to votecast, popular first

        sql = "SELECT infohash, swift_torrent_hash FROM Torrent WHERE torrent_file_name is NULL and infohash in (" + parameters + ")"
        results = self._db.fetchall(sql, map(bin2str, hashes))
        return [(str2bin(hash), str2bin(roothash)) for hash, roothash in results]

    def getTorrentsStats(self):
        return self._db.getOne('CollectedTorrent', ['count(torrent_id)', 'sum(length)', 'sum(num_files)'])

    def freeSpace(self, torrents2del):
# if torrents2del > 100:  # only delete so many torrents each time
#            torrents2del = 100
        if self.channelcast_db and self.channelcast_db._channel_id:
            sql = """
                select torrent_file_name, torrent_id, swift_torrent_hash, relevance,
                    min(relevance,2500) +  min(500,num_leechers) + 4*min(500,num_seeders) - (max(0,min(500,(%d-creation_date)/86400)) ) as weight
                from CollectedTorrent
                where torrent_id not in (select torrent_id from MyPreference)
                and torrent_id not in (select torrent_id from ChannelTorrents where channel_id = %d)
                order by weight
                limit %d
            """ % (int(time()), self.channelcast_db._channel_id, torrents2del)
        else:
            sql = """
                select torrent_file_name, torrent_id, swift_torrent_hash, relevance,
                    min(relevance,2500) +  min(500,num_leechers) + 4*min(500,num_seeders) - (max(0,min(500,(%d-creation_date)/86400)) ) as weight
                from CollectedTorrent
                where torrent_id not in (select torrent_id from MyPreference)
                order by weight
                limit %d
            """ % (int(time()), torrents2del)

        res_list = self._db.fetchall(sql)
        if len(res_list) == 0:
            return False

        # delete torrents from db
        sql_del_torrent = "update Torrent set torrent_file_name = null where torrent_id=?"
        # sql_del_tracker = "delete from TorrentTracker where torrent_id=?"
        # sql_del_pref = "delete from Preference where torrent_id=?"
        tids = [(torrent_id,) for torrent_file_name, torrent_id, swift_torrent_hash, relevance, weight in res_list]

        self._db.executemany(sql_del_torrent, tids, commit=False)
        # self._db.executemany(sql_del_tracker, tids, commit=False)
        # self._db.executemany(sql_del_pref, tids, commit=False)

        self._db.commit()

        # but keep the infohash in db to maintain consistence with preference db
        # torrent_id_infohashes = [(torrent_id,infohash_str,relevance) for torrent_file_name, torrent_id, infohash_str, relevance, weight in res_list]
        # sql_insert =  "insert into Torrent (torrent_id, infohash, relevance) values (?,?,?)"
        # self._db.executemany(sql_insert, torrent_id_infohashes, commit=True)

        torrent_dir = self.getTorrentDir()
        deleted = 0  # deleted any file?
        insert_files = []
        for torrent_file_name, torrent_id, swift_torrent_hash, relevance, weight in res_list:

            torrent_path = os.path.join(torrent_dir, torrent_file_name)
            if not os.path.exists(torrent_path):
                roothash_as_hex = binascii.hexlify(swift_torrent_hash)
                torrent_path = os.path.join(torrent_dir, roothash_as_hex)

            if os.path.exists(torrent_path):
                try:
                    tdef = TorrentDef.load(torrent_path)
                    files = [(torrent_id, unicode(path), length) for path, length in tdef.get_files_as_unicode_with_length()]
                    files = sample(files, 25)
                    insert_files.extend(files)
                except:
                    pass

            mhash_path = torrent_path + '.mhash'
            mbinmap_path = torrent_path + '.mbinmap'
            try:
                if os.path.exists(torrent_path):
                    os.remove(torrent_path)

                if os.path.exists(mhash_path):
                    os.remove(mhash_path)

                if os.path.exists(mbinmap_path):
                    os.remove(mbinmap_path)

                deleted += 1
            except WindowsError:
                pass
            except Exception:
                print_exc()
                # print >> sys.stderr, "Error in erase torrent", Exception, msg
                pass

        if len(insert_files) > 0:
            sql_insert_files = "INSERT OR IGNORE INTO TorrentFiles (torrent_id, path, length) VALUES (?,?,?)"
            self._db.executemany(sql_insert_files, insert_files, commit=False)

        print >> sys.stderr, "Erased %d torrents" % deleted
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

    def searchNames(self, kws, local=True, keys=['torrent_id', 'infohash', 'name', 'torrent_file_name', 'length', 'creation_date', 'num_files', 'insert_time', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'dispersy_id', 'swift_hash', 'swift_torrent_hash'], doSort=True):
        #        if local:
#            mainsql += "C.id, C.dispersy_id, C.name, C.description, C.time_stamp, inserted, "
#            value_name += ['channeltorrent_id', 'dispersy_id', 'chant_name', 'description', 'time_stamp', 'inserted']
#
        assert 'infohash' in keys
        assert not doSort or ('num_seeders' in keys or 'T.num_seeders' in keys)

        infohash_index = keys.index('infohash')
        swift_hash_index = keys.index('swift_hash') if 'swift_hash' in keys else -1
        swift_torrent_hash_index = keys.index('swift_torrent_hash') if 'swift_torrent_hash' in keys else -1
        num_seeders_index = keys.index('num_seeders') if 'num_seeders' in keys else -1

        if num_seeders_index == -1:
            doSort = False

        t1 = time()
        values = ", ".join(keys)
        mainsql = "SELECT " + values + ", C.channel_id, Matchinfo(FullTextIndex) FROM"
        if local:
            mainsql += " Torrent T"
        else:
            mainsql += " CollectedTorrent T"

        mainsql += """, FullTextIndex
                    LEFT OUTER JOIN _ChannelTorrents C ON T.torrent_id = C.torrent_id
                    WHERE t.torrent_id = FullTextIndex.rowid AND C.deleted_at IS NULL AND FullTextIndex MATCH ?
                    """

        if not local:
            mainsql += " LIMIT 250"

        query = " ".join(filter_keywords(kws))
        not_negated = [kw for kw in filter_keywords(kws) if kw[0] != '-']

        results = self._db.fetchall(mainsql, (query,))

        t2 = time()

        channels = set()
        channel_dict = {}
        for result in results:
            if result[-2]:
                channels.add(result[-2])

        if len(channels) > 0:
            # Channels consist of a tuple (id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified)
            for channel in self.channelcast_db.getChannels(channels):
                if channel[1] != '-1':
                    channel_dict[channel[0]] = channel

        t3 = time()
        myChannelId = self.channelcast_db._channel_id or 0

        result_dict = {}

        # step 1, merge torrents keep one with best channel
        for result in results:
            channel_id = result[-2]
            channel = channel_dict.get(channel_id, False)

            infohash = result[infohash_index]
            if channel:
                # ignoring spam channels
                if channel[7] < 0:
                    continue

                # see if we have a better channel in torrents_dict
                if infohash in result_dict:
                    old_channel = channel_dict.get(result_dict[infohash][-2], False)
                    if old_channel:

                        # allways prefer my channel
                        if old_channel[0] == myChannelId:
                            continue

                        # allways prefer channel with higher vote
                        if channel[7] < old_channel[7]:
                            continue

                        votes = (channel[5] or 0) - (channel[6] or 0)
                        oldvotes = (old_channel[5] or 0) - (old_channel[6] or 0)
                        if votes < oldvotes:
                            continue

                result_dict[infohash] = result

            elif infohash not in result_dict:
                result_dict[infohash] = result

        t4 = time()

        # step 2, fix all dict fields
        dont_sort_list = []
        results = [list(result) for result in result_dict.values()]
        for i in xrange(len(results) - 1, -1, -1):
            result = results[i]

            result[infohash_index] = str2bin(result[infohash_index])
            if swift_hash_index >= 0 and result[swift_hash_index]:
                result[swift_hash_index] = str2bin(result[swift_hash_index])
            if swift_torrent_hash_index >= 0 and result[swift_torrent_hash_index]:
                result[swift_torrent_hash_index] = str2bin(result[swift_torrent_hash_index])

            matches = {'swarmname': set(), 'filenames': set(), 'fileextensions': set()}

            # Matchinfo is documented at: http://www.sqlite.org/fts3.html#matchinfo
            matchinfo = str(result[-1])
            num_phrases, num_cols = unpack_from('II', matchinfo)
            unpack_str = 'I' * (3 * num_cols * num_phrases)
            matchinfo = unpack_from('II' + unpack_str, matchinfo)

            swarmnames, filenames, fileextensions = [
                [matchinfo[3 * (i + p * num_cols) + 2] for p in range(num_phrases)]
                for i in range(num_cols)
            ]

            for i, keyword in enumerate(not_negated):
                if swarmnames[i]:
                    matches['swarmname'].add(keyword)
                if filenames[i]:
                    matches['filenames'].add(keyword)
                if fileextensions[i]:
                    matches['fileextensions'].add(keyword)
            result[-1] = matches

            channel = channel_dict.get(result[-2], (result[-2], None, '', '', 0, 0, 0, 0, 0, False))
            result.extend(channel)

            if doSort and result[num_seeders_index] <= 0:
                dont_sort_list.append(result)
                results.pop(i)

        t5 = time()

        if doSort:
            def compare(a, b):
                return cmp(a[num_seeders_index], b[num_seeders_index])
            results.sort(compare, reverse=True)
        results.extend(dont_sort_list)

        if not local:
            results = results[:25]

        # print >> sys.stderr, "# hits:%d (%d from db, %d not sorted); search time:%.3f,%.3f,%.3f,%.3f,%.3f,%.3f" % (len(results),len(results),len(dont_sort_list),t2-t1, t3-t2, t4-t3, t5-t4, time()-t5, time()-t1)
        return results

    def getSearchSuggestion(self, keywords, limit=1):
        match = [keyword.lower() for keyword in keywords]

        def lev(b):
            a = match
            b = b.lower()

            "Calculates the Levenshtein distance between a and b."
            n, m = len(a), len(b)
            if n > m:
                # Make sure n <= m, to use O(min(n,m)) space
                a, b = b, a
                n, m = m, n

            current = range(n + 1)
            for i in range(1, m + 1):
                previous, current = current, [i] + [0] * n
                for j in range(1, n + 1):
                    add, delete = previous[j] + 1, current[j - 1] + 1
                    change = previous[j - 1]
                    if a[j - 1] != b[i - 1]:
                        change = change + 1
                    current[j] = min(add, delete, change)

            return current[n]

        def levcollate(s1, s2):
            l1 = lev(s1.split()[0])
            l2 = lev(s2.split()[0])

            # return -1 if s1<s2, +1 if s1>s2 else 0
            if l1 < l2:
                return -1
            if l1 > l2:
                return 1
            return 0

        cursor = self._db.getCursor()
        connection = cursor.getconnection()
        connection.createcollation("leven", levcollate)

        sql = "SELECT term, freq FROM TermFrequency WHERE term LIKE '%" + match[0] + "'ORDER By term collate leven ASC, freq DESC LIMIT ?"
        result = self._db.fetchall(sql, (limit,))
        connection.createcollation("leven", None)
        return result

    def selectTorrentsToCollect(self, permid, candidate_list=None, similarity_list_size=50, list_size=1):
        # Niels: no more preference table, hence this method does not work
        raise NotImplementedError('preference table is gone')
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
            # print >>sys.stderr,"torrentdb: selectTorrentToCollect: cands",`candidate_list`

            cand_str = [bin2str(infohash) for infohash in candidate_list]
            s = repr(cand_str).replace('[', '(').replace(']', ')')
            sql = """SELECT similarity, infohash FROM Peer, Preference, Torrent
                     WHERE Peer.peer_id = Preference.peer_id
                     AND Torrent.torrent_id = Preference.torrent_id
                     AND Peer.peer_id IN(Select peer_id from Peer WHERE similarity > 0 ORDER By similarity DESC Limit ?)
                     AND infohash in """ + s + """
                     AND torrent_file_name is NULL
                  """
            results = self._db.fetchall(sql, (similarity_list_size,))

        # convert top-x similarities into item recommendations
        infohashes = {}
        for sim, infohash in results:
            infohashes[infohash] = infohashes.get(infohash, 0) + sim

        res = []
        keys = infohashes.keys()
        if len(keys) > 0:
            keys.sort(lambda a, b: cmp(infohashes[b], infohashes[a]))

            # add all items with highest relevance to candidate_list
            candidate_list = []
            for infohash in keys:
                if infohashes[infohash] == infohashes[keys[0]]:
                    candidate_list.append(str2bin(infohash))

            # if only 1 candidate use that as result
            if len(candidate_list) <= list_size:
                res = filter(lambda x: not x is None, keys[:list_size])
                candidate_list = None

        # No torrent found with relevance, fallback to most downloaded torrent
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
                s = repr(cand_str).replace('[', '(').replace(']', ')')
                sql = """SELECT infohash FROM Torrent, Preference
                         WHERE Torrent.torrent_id == Preference.torrent_id
                         AND torrent_file_name is NULL
                         AND infohash IN """ + s + """
                         GROUP BY Preference.torrent_id
                         ORDER BY Count(Preference.torrent_id) DESC
                         LIMIT ?"""
                res.extend([infohash for infohash, in self._db.fetchall(sql, (list_size - len(res),))])

        return [str2bin(infohash) for infohash in res if not infohash is None]

    def selectTorrentToCheck(self, policy='random', infohash=None):  # for tracker checking
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

        # import threading
        # print >> sys.stderr, "****** selectTorrentToCheck", threading.currentThread().getName()

        if infohash is None:
            # create a view?
            sql = """select T.torrent_id, ignored_times, retried_times, torrent_file_name, infohash, status_id, num_seeders, num_leechers, last_check, tracker
                     from CollectedTorrent T, TorrentTracker TT
                     where TT.torrent_id=T.torrent_id and announce_tier=1 """
            if policy.lower() == 'random':
                ntorrents = self.getNumberCollectedTorrents()
                if ntorrents == 0:
                    rand_pos = 0
                else:
                    rand_pos = randint(0, ntorrents - 1)
                last_check_threshold = int(time()) - 300
                sql += """and last_check < %d
                        limit 1 offset %d """ % (last_check_threshold, rand_pos)
            elif policy.lower() == 'oldest':
                last_check_threshold = int(time()) - 300
                sql += """ and last_check < %d and status_id <> 2
                         order by last_check
                         limit 1 """ % last_check_threshold
            elif policy.lower() == 'popular':
                last_check_threshold = int(time()) - 4 * 60 * 60
                sql += """ and last_check < %d and status_id <> 2
                         order by 3*num_seeders+num_leechers desc
                         limit 1 """ % last_check_threshold
            res = self._db.fetchone(sql)
        else:
            # Niels: If we specifiy a particular torrent, allow for non-collected torrents (ie torrent from channels can have trackers before the .torrent is collected)
            sql = """select T.torrent_id, ignored_times, retried_times, torrent_file_name, infohash, status_id, num_seeders, num_leechers, last_check, tracker
                     from Torrent T, TorrentTracker TT
                     where TT.torrent_id=T.torrent_id and announce_tier=1
                     and infohash=?
                  """
            infohash_str = bin2str(infohash)
            res = self._db.fetchone(sql, (infohash_str,))

        if res:
            torrent_file_name = res[3]
            if torrent_file_name:
                torrent_dir = self.getTorrentDir()
                torrent_path = os.path.join(torrent_dir, torrent_file_name)
            else:
                torrent_path = None

            res = {'torrent_id': res[0],
                   'ignored_times': res[1],
                   'retried_times': res[2],
                   'torrent_path': torrent_path,
                   'infohash': str2bin(res[4]),
                   'status': self.id2status[res[5]],
                   'last_check': res[8],
                   'trackers': [res[9]],
                  }
            return res

    def getTorrentsFromSource(self, source):
        """ Get all torrents from the specified Subscription source.
        Return a list of dictionaries. Each dict is in the NEWDBSTANDARD format.
        """
        id = self._getSourceID(source)

        where = 'C.source_id = %d and C.torrent_id = T.torrent_id and announce_tier=1' % (id)
        # add familyfilter
        where += self.category.get_family_filter_sql(self._getCategoryID)

        value_name = deepcopy(self.value_name)

        res_list = self._db.getAll('Torrent C, TorrentTracker T', value_name, where)

        torrent_list = self.valuelist2torrentlist(value_name, res_list, None, None)
        del res_list

        return torrent_list

    def getTorrentFiles(self, torrent_id):
        sql = "SELECT path, length FROM TorrentFiles WHERE torrent_id = ?"
        return self._db.fetchall(sql, (torrent_id,))

    def getTorrentCollecting(self, torrent_id):
        sql = "SELECT source FROM TorrentCollecting WHERE torrent_id = ?"
        return self._db.fetchall(sql, (torrent_id,))

    def setSecret(self, infohash, secret):
        kw = {'secret': secret}
        self.updateTorrent(infohash, commit=True, **kw)


class MyPreferenceDBHandler(BasicDBHandler):

    def __init__(self):
        if MyPreferenceDBHandler._single is not None:
            raise RuntimeError("MyPreferenceDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'MyPreference')  # # self,db,'MyPreference'

        self.status_table = {'good': 1, 'unknown': 0, 'dead': 2}
        self.status_table.update(self._db.getTorrentStatusTable())
        self.status_good = self.status_table['good']
        self.rlock = threading.RLock()
        self.loadData()

    def loadData(self):
        """ Arno, 2010-02-04: Brute force update method for the self.recent_
        caches, because people don't seem to understand that caches need
        to be kept consistent with the database. Caches are evil in the first place.
        """
#        self.rlock.acquire()
#        try:
#            self.recent_preflist = self._getRecentLivePrefList()
#            self.recent_preflist_with_clicklog = self._getRecentLivePrefListWithClicklog()
#            self.recent_preflist_with_swarmsize = self._getRecentLivePrefListOL11()
#        finally:
#            self.rlock.release()
        self.recent_preflist = self.recent_preflist_with_clicklog = self.recent_preflist_with_swarmsize = None

    def getMyPrefList(self, order_by=None):
        res = self.getAll('torrent_id', order_by=order_by)
        return [p[0] for p in res]

    def getMyPrefListInfohash(self, returnDeleted=True, limit=None):
        # Arno, 2012-08-01: having MyPreference (the shorter list) first makes
        # this faster.
        sql = 'select infohash, swift_hash from MyPreference, Torrent where Torrent.torrent_id == MyPreference.torrent_id'
        if not returnDeleted:
            sql += ' AND destination_path != ""'

        if limit:
            sql += ' ORDER BY creation_time DESC LIMIT %d' % limit

        res = self._db.fetchall(sql)
        res = [item for sublist in res for item in sublist]
        return [str2bin(p) if p else '' for p in res]

    def getMyPrefStats(self, torrent_id=None):
        # get the full {torrent_id:(create_time,progress,destdir)}
        value_name = ('torrent_id', 'creation_time', 'progress', 'destination_path')
        if torrent_id is not None:
            where = 'torrent_id=%s' % torrent_id
        else:
            where = None
        res = self.getAll(value_name, where)
        mypref_stats = {}
        for pref in res:
            torrent_id, creation_time, progress, destination_path = pref
            mypref_stats[torrent_id] = (creation_time, progress, destination_path)
        return mypref_stats

    def getMyPrefStatsInfohash(self, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id is not None:
            return self.getMyPrefStats(torrent_id)[torrent_id]

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
                # if self.recent_preflist_with_swarmsize is None:
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
        clicklog_already_stored = False  # equivalent to hasMyPreference TODO
        if torrent_id is None or clicklog_already_stored:
            return False

        d = {}
        # copy those elements of the clicklog data which are used in the update command
        for clicklog_key in ["click_position", "reranking_strategy"]:
            if clicklog_key in clicklog_data:
                d[clicklog_key] = clicklog_data[clicklog_key]

        if d == {}:
            if DEBUG:
                print >> sys.stderr, "no updatable information given to addClicklogToMyPreference"
        else:
            if DEBUG:
                print >> sys.stderr, "addClicklogToMyPreference: updatable clicklog data: %s" % d
            self._db.update(self.table_name, 'torrent_id=%d' % torrent_id, commit=commit, **d)

        # have keywords stored by SearchDBHandler
        if 'keywords' in clicklog_data:
            if not clicklog_data['keywords'] == []:
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
                                              t[3],  # insert search terms in next step, only for those actually required, store torrent id for now
                                              t[1],  # click position
                                              t[2]]  # reranking strategy
                                             for t in recent_preflist_with_clicklog]

        if num != 0:
            recent_preflist_with_clicklog = recent_preflist_with_clicklog[:num]

        # now that we only have those torrents left in which we are actually interested,
        # replace torrent id by user's search terms for torrent id
        searchdb = SearchDBHandler.getInstance()
        torrent_ids = [pref[1] for pref in recent_preflist_with_clicklog]
        terms_dict = searchdb.getMyTorrentsSearchTermsStr(torrent_ids)

        for pref in recent_preflist_with_clicklog:
            search_terms = [term.encode("UTF-8") for term in terms_dict[pref[1]]]

            # Arno, 2010-02-02: Explicit encoding
            pref[1] = search_terms
        return recent_preflist_with_clicklog

    def searchterms2utf8pref(self, termdb, search_terms):
        terms = [termdb.getTerm(search_term) for search_term in search_terms]
        eterms = []
        for term in terms:
            eterms.append(term.encode("UTF-8"))
        return eterms

    def _getRecentLivePrefList(self, num=0):  # num = 0: all files
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

    def hasMyPreference(self, torrent_id):
        res = self.getOne('torrent_id', torrent_id=torrent_id)
        if res is not None:
            return True
        else:
            return False

    def addMyPreference(self, torrent_id, data, commit=True):
        # keys in data: destination_path, progress, creation_time, torrent_id
        if self.hasMyPreference(torrent_id):
            # Arno, 2009-03-09: Torrent already exists in myrefs.
            # Hack for hiding from lib while keeping in myprefs.
            # see standardOverview.removeTorrentFromLibrary()
            #
            self.updateDestDir(torrent_id, data.get('destination_path'), commit=commit)
            infohash = self._db.getInfohash(torrent_id)
            if infohash:
                self.notifier.notify(NTFY_MYPREFERENCES, NTFY_UPDATE, infohash)
            return False

        d = {}
        d['destination_path'] = data.get('destination_path')
        d['progress'] = data.get('progress', 0)
        d['creation_time'] = data.get('creation_time', int(time()))
        d['torrent_id'] = torrent_id

        self._db.insert(self.table_name, commit=commit, **d)

        infohash = self._db.getInfohash(torrent_id)
        if infohash:
            self.notifier.notify(NTFY_MYPREFERENCES, NTFY_INSERT, infohash)

        # Arno, 2010-02-04: Update self.recent_ caches :-(
        # self.loadData()
        return True

    def deletePreference(self, torrent_id, commit=True):
        self._db.delete(self.table_name, commit=commit, **{'torrent_id': torrent_id})

        infohash = self._db.getInfohash(torrent_id)
        if infohash:
            self.notifier.notify(NTFY_MYPREFERENCES, NTFY_DELETE, infohash)

        # Arno, 2010-02-04: Update self.recent_ caches :-(
        # self.loadData()

    def updateProgress(self, torrent_id, progress, commit=True):
        self._db.update(self.table_name, 'torrent_id=%d' % torrent_id, commit=commit, progress=progress)

    def updateProgressByHash(self, hash, progress, commit=True):
        torrent_id = self._db.getTorrentID(hash)
        if not torrent_id:
            torrent_id = self._db.getTorrentIDRoot(hash)

        if torrent_id:
            self.updateProgress(torrent_id, progress, commit=commit)

    def getAllEntries(self):
        """use with caution,- for testing purposes"""
        return self.getAll("torrent_id, click_position, reranking_strategy", order_by="torrent_id")

    def updateDestDir(self, torrent_id, destdir, commit=True):
        if not isinstance(destdir, basestring):
            print >> sys.stderr, 'DESTDIR IS NOT STRING:', destdir
            return
        self._db.update(self.table_name, 'torrent_id=%d' % torrent_id, commit=commit, destination_path=destdir)

    def updateDestDirByHash(self, hash, destdir, commit=True):
        torrent_id = self._db.getTorrentID(hash)
        if not torrent_id:
            torrent_id = self._db.getTorrentIDRoot(hash)

        if torrent_id:
            self.updateDestDir(torrent_id, destdir, commit=commit)


class VoteCastDBHandler(BasicDBHandler):

    def __init__(self):
        try:
            db = SQLiteCacheDB.getInstance()
            BasicDBHandler.__init__(self, db, 'VoteCast')
            if DEBUG:
                print >> sys.stderr, "votecast: DB made"
        except:
            print >> sys.stderr, "votecast: couldn't make the table"

        self.my_votes = None
        if DEBUG:
            print >> sys.stderr, "votecast: "

    def registerSession(self, session):
        self.session = session

        self.peer_db = PeerDBHandler.getInstance()
        self.channelcast_db = ChannelCastDBHandler.getInstance()

    def on_vote_from_dispersy(self, channel_id, voter_id, dispersy_id, vote, timestamp):
        if not voter_id:
            self.removeVote(channel_id, voter_id)  # sqlite constraint does not work for NULL values

        insert_vote = "INSERT OR REPLACE INTO _ChannelVotes (channel_id, voter_id, dispersy_id, vote, time_stamp) VALUES (?,?,?,?,?)"
        self._db.execute_write(insert_vote, (channel_id, voter_id, dispersy_id, vote, timestamp))

        self._updateChannelVotes(channel_id)
        self.notifier.notify(NTFY_VOTECAST, NTFY_UPDATE, channel_id)

    def on_votes_from_dispersy(self, votes):
        removeVotes = [(channel_id, voter_id) for channel_id, voter_id, _, _, _ in votes if not voter_id]
        self.removeVotes(removeVotes, updateVotes=False, commit=False)

        insert_vote = "INSERT OR REPLACE INTO _ChannelVotes (channel_id, voter_id, dispersy_id, vote, time_stamp) VALUES (?,?,?,?,?)"
        self._db.executemany(insert_vote, votes)

        # Arno, 2012-08-01: _updateChannelsVotes would be executed one for every
        # pair, instead of once for every channel. And in many cases there would
        # be just 1 channel :-(
        channel_voter_ids = set((channel_id, voter_id) for channel_id, voter_id, _, _, _ in votes)
        just_channel_ids = set([channel_id for channel_id, _ in channel_voter_ids])

        if len(just_channel_ids) == 1:
            # WARNING: pop removes element
            self._updateChannelVotes(just_channel_ids.pop(), commit=False)
        else:
            self._updateChannelsVotes(just_channel_ids)
        self._db.commit()

        for channel_id, voter_id in channel_voter_ids:
            self.notifier.notify(NTFY_VOTECAST, NTFY_UPDATE, channel_id, voter_id == None)

    def on_remove_vote_from_dispersy(self, channel_id, dispersy_id, redo):
        remove_vote = "UPDATE _ChannelVotes SET deleted_at = ? WHERE channel_id = ? AND dispersy_id = ?"

        if redo:
            deleted_at = None
        else:
            deleted_at = long(time())
        self._db.execute_write(remove_vote, (deleted_at, channel_id, dispersy_id))
        self._updateChannelVotes(channel_id)

    def get_latest_vote_dispersy_id(self, channel_id, voter_id):
        if voter_id:
            select_vote = "SELECT dispersy_id FROM ChannelVotes WHERE channel_id = ? AND voter_id = ? AND dispersy_id != -1 ORDER BY time_stamp DESC Limit 1"
            return self._db.fetchone(select_vote, (channel_id, voter_id))

        select_vote = "SELECT dispersy_id FROM ChannelVotes WHERE channel_id = ? AND voter_id ISNULL AND dispersy_id != -1 ORDER BY time_stamp DESC Limit 1"
        return self._db.fetchone(select_vote, (channel_id,))

    def getPosNegVotes(self, channel_id):
        sql = 'select nr_favorite, nr_spam from Channels where id = ?'
        result = self._db.fetchone(sql, (channel_id,))
        if result:
            return result
        return 0, 0

    def getAllPosNegVotes(self, channel_ids=None):
        if channel_ids:
            channel_ids = " WHERE id IN ('" + "' ,'".join(map(str, channel_ids)) + "') "
        else:
            channel_ids = ''

        votes = {}

        sql = 'select id, nr_favorite, nr_spam from Channels' + channel_ids
        records = self._db.fetchall(sql)
        for channel_id, nr_favorite, nr_spam in records:
            votes[channel_id] = (nr_favorite or 0, nr_spam or 0)

        return votes

    def addVote(self, vote):
        sql = "INSERT OR IGNORE INTO _ChannelVotes (channel_id, voter_id, vote, time_stamp) VALUES (?,?,?,?)"
        self._db.execute_write(sql, vote)
        self._updateChannelVotes(vote[0])

        if vote[1] == None:
            self.my_votes = None

    def addVotes(self, votes):
        sql = "INSERT OR IGNORE INTO _ChannelVotes (channel_id, voter_id, vote, time_stamp) VALUES (?,?,?,?)"
        self._db.executemany(sql, votes)

        channels = set()
        for vote in votes:
            channels.add(vote[0])
        self._updateChannelsVotes(channels)

    def removeVote(self, channel_id, voter_id, commit=True):
        if voter_id:
            sql = "UPDATE _ChannelVotes SET deleted_at = ? WHERE channel_id = ? AND voter_id = ?"
            self._db.execute_write(sql, (long(time()), channel_id, voter_id), commit=commit)
        else:
            sql = "UPDATE _ChannelVotes SET deleted_at = ? WHERE channel_id = ? AND voter_id ISNULL"
            self._db.execute_write(sql, (long(time()), channel_id), commit=commit)
            self.my_votes = None

        if commit:
            self._updateChannelVotes(channel_id)

    def removeVotes(self, votes, updateVotes=True, commit=True):
        for channel_id, voter_id in votes:
            self.removeVote(channel_id, voter_id, commit=False)
        if commit:
            self._db.commit()

        if updateVotes:
            # Arno: why not use _updateCHannelsVotes here?
            channel_ids = set([channel_id for channel_id, _ in votes])
            for channel_id in channel_ids:
                self._updateChannelVotes(channel_id)
            if commit:
                self._db.commit()

    def _updateChannelVotes(self, channel_id, commit=True):
        nr_favorites = self._db.fetchone("SELECT count(*) FROM ChannelVotes WHERE vote == 2 AND channel_id = ?", (channel_id,))
        nr_spam = self._db.fetchone("SELECT count(*) FROM ChannelVotes WHERE vote == -1 AND channel_id = ?", (channel_id,))
        self._db.execute_write("UPDATE _Channels SET nr_favorite = ?, nr_spam = ? WHERE id = ?", (nr_favorites, nr_spam, channel_id), commit=commit)

    def _updateChannelsVotes(self, channel_ids, commit=True):
        parameters = ",".join("?" * len(channel_ids))
        sql = "Select channel_id, vote FROM ChannelVotes WHERE channel_id in (" + parameters + ")"
        positive_votes = {}
        negative_votes = {}
        for channel_id, vote in self._db.fetchall(sql, channel_ids):
            if vote == 2:
                positive_votes[channel_id] = positive_votes.get(channel_id, 0) + 1
            elif vote == -1:
                negative_votes[channel_id] = negative_votes.get(channel_id, 0) + 1

        updates = [(positive_votes.get(channel_id, 0), negative_votes.get(channel_id, 0), channel_id) for channel_id in channel_ids]
        self._db.executemany("UPDATE _Channels SET nr_favorite = ?, nr_spam = ? WHERE id = ?", updates, commit=commit)

    def getVote(self, channel_id, voter_id):
        """ return the vote status if such record exists, otherwise None  """
        if voter_id:
            sql = "select vote from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select vote from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id,))

    def getVoteForMyChannel(self, voter_id):
        return self.getVote(self.channelcast_db._channel_id, voter_id)

    def getDispersyId(self, channel_id, voter_id):
        """ return the dispersy_id for this vote """
        if voter_id:
            sql = "select dispersy_id from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select dispersy_id from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id,))

    def getTimestamp(self, channel_id, voter_id):
        """ return the timestamp for this vote """
        if voter_id:
            sql = "select time_stamp from ChannelVotes where channel_id = ? and voter_id = ?"
            return self._db.fetchone(sql, (channel_id, voter_id))
        sql = "select time_stamp from ChannelVotes where channel_id = ? and voter_id ISNULL"
        return self._db.fetchone(sql, (channel_id,))

    def getChannelsWithNegVote(self, voter_id):
        ''' return the channel_ids having a negative vote from voter_id '''
        if voter_id:
            sql = "select channel_id from ChannelVotes where voter_id = ? and vote = -1"
            return self._db.fetchall(sql, (voter_id,))

        sql = "select channel_id from ChannelVotes where voter_id ISNULL and vote = -1"
        return self._db.fetchall(sql)

    def getChannelsWithPosVote(self, voter_id):
        ''' return the publisher_ids having a negative vote from subscriber_id '''
        if voter_id:
            sql = "select channel_id from ChannelVotes where voter_id = ? and vote = 2"
            return self._db.fetchall(sql, (voter_id,))
        sql = "select channel_id from ChannelVotes where voter_id ISNULL and vote = 2"
        return self._db.fetchall(sql)

    def getEffectiveVote(self, channel_id):
        """ returns positive - negative votes """
        pos_votes, neg_votes = self.getPosNegVotes(channel_id)
        return pos_votes

    def getEffectiveVoteFromPermid(self, channel_permid):
        channel_id = self.peer_db.getPeerID(channel_permid)
        return self.getEffectiveVote(channel_id)

    def getMyVotes(self):
        if not self.my_votes:
            sql = "SELECT channel_id, vote FROM ChannelVotes WHERE voter_id ISNULL"

            self.my_votes = {}
            for channel_id, vote in self._db.fetchall(sql):
                self.my_votes[channel_id] = vote
        return self.my_votes


# end votes

class ChannelCastDBHandler(BasicDBHandler):

    def __init__(self):
        try:
            db = SQLiteCacheDB.getInstance()
            BasicDBHandler.__init__(self, db, '_Channels')
            if DEBUG:
                print >> sys.stderr, "Channels: DB made"
        except:
            print >> sys.stderr, "Channels: couldn't make the table"

        self._channel_id = None
        self.shouldCommit = True
        self.my_dispersy_cid = None

        self.modification_types = dict(self._db.fetchall("SELECT name, id FROM MetaDataTypes"))
        self.id2modification = dict([(v, k) for k, v in self.modification_types.iteritems()])

        self._channel_id = self.getMyChannelId()
        if DEBUG:
            print >> sys.stderr, "Channels: my channel is", self._channel_id

    def commit(self):
        self._db.commit()

    def registerSession(self, session):
        self.session = session

        self.peer_db = PeerDBHandler.getInstance()
        self.votecast_db = VoteCastDBHandler.getInstance()
        self.torrent_db = TorrentDBHandler.getInstance()

        def updateNrTorrents():
            while True:
                rows = self.getChannelNrTorrents(50)
                update = "UPDATE _Channels SET nr_torrents = ? WHERE id = ?"
                self._db.executemany(update, rows, commit=self.shouldCommit)

                # schedule a call for in 5 minutes
                yield 300.0

                rows = self.getChannelNrTorrentsLatestUpdate(50)
                update = "UPDATE _Channels SET nr_torrents = ?, modified = ? WHERE id = ?"
                self._db.executemany(update, rows, commit=self.shouldCommit)

                # schedule a call for in 5 minutes
                yield 300.0
        self.session.lm.database_thread.register(updateNrTorrents, delay=120.0)

    # dispersy helper functions
    def _get_my_dispersy_cid(self):
        if not self.my_dispersy_cid:
            from Tribler.community.channel.community import ChannelCommunity

            for community in self.session.lm.dispersy.get_communities():
                if isinstance(community, ChannelCommunity) and community.master_member and community.master_member.private_key:
                    self.my_dispersy_cid = community.cid
                    break

        return self.my_dispersy_cid

    def getDispersyCIDFromChannelId(self, channel_id):
        return self._db.fetchone(u"SELECT dispersy_cid FROM Channels WHERE id = ?", (channel_id,))

    def getChannelIdFromDispersyCID(self, dispersy_cid):
        return self._db.fetchone(u"SELECT id FROM Channels WHERE dispersy_cid = ?", (dispersy_cid,))

    def getCountMaxFromChannelId(self, channel_id):
        sql = u"SELECT COUNT(*), MAX(inserted) FROM ChannelTorrents WHERE channel_id = ? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))

    def drop_all_newer(self, dispersy_id):
        sql = "DELETE FROM _TorrentMarkings WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _ChannelVotes WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _ChannelMetaData WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _Moderations WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _Comments WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _PlaylistTorrents WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _Playlists WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=False)

        sql = "DELETE FROM _ChannelTorrents WHERE dipsersy_id > ?"
        self._db.execute_write(sql, (dispersy_id), commit=self.shouldCommit)

    # dispersy modifying and receiving channels
    def on_channel_from_channelcast(self, publisher_permid, name):
        peer_id = self.peer_db.addOrGetPeerID(publisher_permid)
        return self.on_channel_from_dispersy(-1, peer_id, name, '')

    def on_channel_from_dispersy(self, dispersy_cid, peer_id, name, description):
        if isinstance(dispersy_cid, (str)):
            _dispersy_cid = buffer(dispersy_cid)
        else:
            _dispersy_cid = dispersy_cid

        # merge channels if we detect upgrade from old-channelcast to new-dispersy-channelcast
        get_channel = "SELECT id FROM Channels Where peer_id = ? and dispersy_cid == -1"
        channel_id = self._db.fetchone(get_channel, (peer_id,))

        if channel_id:  # update this channel
            update_channel = "UPDATE _Channels SET dispersy_cid = ?, name = ?, description = ? WHERE id = ?"
            self._db.execute_write(update_channel, (_dispersy_cid, name, description, channel_id), commit=self.shouldCommit)

            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

        else:
            get_channel = "SELECT id FROM Channels Where dispersy_cid = ?"
            channel_id = self._db.fetchone(get_channel, (_dispersy_cid,))

            if channel_id:
                update_channel = "UPDATE _Channels SET name = ?, description = ?, peer_id = ? WHERE dispersy_cid = ?"
                self._db.execute_write(update_channel, (name, description, peer_id, _dispersy_cid), commit=self.shouldCommit)

            else:
                # insert channel
                insert_channel = "INSERT INTO _Channels (dispersy_cid, peer_id, name, description) VALUES (?, ?, ?, ?); SELECT last_insert_rowid();"
                channel_id = self._db.fetchone(insert_channel, (_dispersy_cid, peer_id, name, description))

            self.notifier.notify(NTFY_CHANNELCAST, NTFY_INSERT, channel_id)

        if not self._channel_id and self._get_my_dispersy_cid() == dispersy_cid:
            self._channel_id = channel_id
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_CREATE, channel_id)
        return channel_id

    def on_channel_modification_from_dispersy(self, channel_id, modification_type, modification_value, commit=None):
        if commit is None:
            commit = self.shouldCommit

        if modification_type in ['name', 'description']:
            update_channel = "UPDATE _Channels Set " + modification_type + " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_channel, (modification_value, long(time()), channel_id), commit=commit)

            self.notifier.notify(NTFY_CHANNELCAST, NTFY_MODIFIED, channel_id)

    def on_torrents_from_dispersy(self, torrentlist):
        infohashes = [torrent[3] for torrent in torrentlist]
        torrent_ids, inserted = self.torrent_db.addOrGetTorrentIDSReturn(infohashes)

        insert_data = []
        updated_channels = {}
        for i, torrent in enumerate(torrentlist):
            channel_id, dispersy_id, peer_id, infohash, timestamp, name, files, trackers = torrent
            torrent_id = torrent_ids[i]

            # if new or not yet collected
            if infohash in inserted:
                self.torrent_db.addExternalTorrentNoDef(infohash, name, files, trackers, timestamp, "DISP", {'dispersy_id': dispersy_id})

            insert_data.append((dispersy_id, torrent_id, channel_id, peer_id, name, timestamp))
            updated_channels[channel_id] = updated_channels.get(channel_id, 0) + 1

        if len(insert_data) > 0:
            sql_insert_torrent = "INSERT INTO _ChannelTorrents (dispersy_id, torrent_id, channel_id, peer_id, name, time_stamp) VALUES (?,?,?,?,?,?)"
            self._db.executemany(sql_insert_torrent, insert_data, commit=False)

        sql_update_channel = "UPDATE _Channels SET modified = strftime('%s','now'), nr_torrents = nr_torrents+? WHERE id = ?"
        update_channels = [(new_torrents, channel_id) for channel_id, new_torrents in updated_channels.iteritems()]
        self._db.executemany(sql_update_channel, update_channels, commit=self.shouldCommit)

        for channel_id in updated_channels.keys():
            self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

    def on_remove_torrent_from_dispersy(self, channel_id, dispersy_id, redo):
        sql = "UPDATE _ChannelTorrents SET deleted_at = ? WHERE channel_id = ? and dispersy_id = ?"

        if redo:
            deleted_at = None
        else:
            deleted_at = long(time())
        self._db.execute_write(sql, (deleted_at, channel_id, dispersy_id), commit=self.shouldCommit)

        self.notifier.notify(NTFY_CHANNELCAST, NTFY_UPDATE, channel_id)

    def on_torrent_modification_from_dispersy(self, channeltorrent_id, modification_type, modification_value, commit=None):
        if commit is None:
            commit = self.shouldCommit

        if modification_type in ['name', 'description']:
            update_torrent = "UPDATE _ChannelTorrents SET " + modification_type + " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_torrent, (modification_value, long(time()), channeltorrent_id), commit=commit)

            sql = "Select infohash From Torrent, ChannelTorrents Where Torrent.torrent_id = ChannelTorrents.torrent_id And ChannelTorrents.id = ?"
            infohash = self._db.fetchone(sql, (channeltorrent_id,))

            if infohash:
                infohash = str2bin(infohash)
                self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)

        elif modification_type in ['swift-url']:
            sql = "Select infohash From Torrent, ChannelTorrents Where Torrent.torrent_id = ChannelTorrents.torrent_id And ChannelTorrents.id = ?"
            infohash = self._db.fetchone(sql, (channeltorrent_id,))

            if infohash:
                from Tribler.Core.Swift.SwiftDef import SwiftDef

                sdef = SwiftDef.load_from_url(modification_value)
                roothash = bin2str(sdef.get_roothash())
                # If a user created two .torrents from the same set of files with different swarmnames we have two infohashes pointing to the same roothash.
                update_torrent = "UPDATE or IGNORE Torrent SET swift_hash = ? WHERE infohash = ?"
                self._db.execute_write(update_torrent, (roothash, infohash))

    def addOrGetChannelTorrentID(self, channel_id, infohash):
        torrent_id = self.torrent_db.addOrGetTorrentID(infohash)

        sql = "SELECT id FROM _ChannelTorrents WHERE torrent_id = ? AND channel_id = ?"
        channeltorrent_id = self._db.fetchone(sql, (torrent_id, channel_id))
        if not channeltorrent_id:
            insert_torrent = "INSERT OR IGNORE INTO _ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp) VALUES (?,?,?,?);"
            self._db.execute_write(insert_torrent, (-1, torrent_id, channel_id, -1), commit=self.shouldCommit)

            channeltorrent_id = self._db.fetchone(sql, (torrent_id, channel_id))
        return channeltorrent_id

    def hasTorrent(self, channel_id, infohash):
        torrent_id = self._db.getTorrentID(infohash)
        if torrent_id:
            sql = "SELECT id FROM ChannelTorrents WHERE torrent_id = ? and channel_id = ?"
            channeltorrent_id = self._db.fetchone(sql, (torrent_id, channel_id))
            if channeltorrent_id:
                return True
        return False

    def hasTorrents(self, channel_id, infohashes):
        returnAr = []
        torrent_ids = self._db.getTorrentIDS(infohashes)

        for i in range(len(infohashes)):
            if torrent_ids[i] == None:
                returnAr.append(False)

            else:
                sql = "SELECT id FROM ChannelTorrents WHERE torrent_id = ? AND channel_id = ? AND dispersy_id <> -1"
                channeltorrent_id = self._db.fetchone(sql, (torrent_ids[i], channel_id))
                returnAr.append(True if channeltorrent_id else False)
        return returnAr

    def playlistHasTorrent(self, playlist_id, channeltorrent_id):
        sql = "SELECT id FROM PlaylistTorrents WHERE playlist_id = ? AND channeltorrent_id = ?"
        playlisttorrent_id = self._db.fetchone(sql, (playlist_id, channeltorrent_id))
        if playlisttorrent_id:
            return True
        return False

    # Old code used by channelcast
    def on_torrents_from_channelcast(self, torrents):
        # torrents is a list of tuples (channel_id, channel_name, infohash, time_stamp
        select_max = "SELECT max(time_stamp) FROM ChannelTorrents WHERE channel_id = ?"

        update_name = "UPDATE _Channels SET name = ?, modified = ?, nr_torrents = ? WHERE id = ?"
        update_channel = "UPDATE _Channels SET modified = ?, nr_torrents = ? WHERE id = ?"
        select_torrent = "SELECT torrent_id FROM ChannelTorrents WHERE torrent_id = ? AND channel_id = ?"
        insert_torrent = "INSERT INTO _ChannelTorrents (dispersy_id, torrent_id, channel_id, time_stamp) VALUES (?,?,?,?)"

        max_update = {}
        latest_update = {}

        # batch fetch torrent_ids:
        infohashes = [infohash for channel_id, channel_name, infohash, name, timestamp in torrents]
        torrent_ids = self.torrent_db.addOrGetTorrentIDS(infohashes)

        for i, torrent in enumerate(torrents):
            channel_id, channel_name, infohash, name, timestamp = torrent
            torrent_id = torrent_ids[i]

            present = self._db.fetchone(select_torrent, (torrent_id, channel_id))
            if present == None:
                if not channel_id in max_update:
                    max_update[channel_id] = self._db.fetchone(select_max, (channel_id,))

                if timestamp > max_update[channel_id]:
                    # possible name change
                    latest_update[channel_id] = max((timestamp, channel_name), latest_update.get(channel_id, None))

                self._db.execute_write(insert_torrent, (-1, torrent_id, channel_id, timestamp), commit=False)

        for channel_id in max_update.keys():
            modified, nrTorrents = self.getLatestUpdateNrTorrentsInChannel(channel_id, collected=True)

            if channel_id in latest_update:
                new_name = latest_update[channel_id][1][:40]
                self._db.execute_write(update_name, (new_name, modified, nrTorrents, channel_id), commit=False)
            else:
                self._db.execute_write(update_channel, (modified, nrTorrents, channel_id), commit=False)

        if self.shouldCommit:
            self._db.commit()

    def deleteTorrentFromChannel(self, channel_id):
        # remove all non-dispersy torrents
        sql = "DELETE FROM _ChannelTorrents WHERE channel_id = ? AND dispersy_id = ?"
        self._db.execute_write(sql, (channel_id, -1), commit=self.shouldCommit)

    # dispersy receiving comments
    def on_comment_from_dispersy(self, channel_id, dispersy_id, mid_global_time, peer_id, comment, timestamp, reply_to, reply_after, playlist_dispersy_id, infohash):
        # both reply_to and reply_after could be loose pointers to not yet received dispersy message
        if isinstance(reply_to, (str)):
            reply_to = buffer(reply_to)

        if isinstance(reply_after, (str)):
            reply_after = buffer(reply_after)
        mid_global_time = buffer(mid_global_time)

        sql = "INSERT OR REPLACE INTO _Comments (channel_id, dispersy_id, peer_id, comment, reply_to_id, reply_after_id, time_stamp) VALUES (?, ?, ?, ?, ?, ?, ?); SELECT last_insert_rowid();"
        comment_id = self._db.fetchone(sql, (channel_id, dispersy_id, peer_id, comment, reply_to, reply_after, timestamp))

        if playlist_dispersy_id or infohash:
            if playlist_dispersy_id:
                sql = "SELECT id FROM Playlists WHERE dispersy_id = ?"
                playlist_id = self._db.fetchone(sql, (playlist_dispersy_id,))

                sql = "INSERT INTO CommentPlaylist (comment_id, playlist_id) VALUES (?, ?)"
                self._db.execute_write(sql, (comment_id, playlist_id), commit=False)

            if infohash:
                channeltorrent_id = self.addOrGetChannelTorrentID(channel_id, infohash)

                sql = "INSERT INTO CommentTorrent (comment_id, channeltorrent_id) VALUES (?, ?)"
                self._db.execute_write(sql, (comment_id, channeltorrent_id), commit=False)

        # try fo fix loose reply_to and reply_after pointers
        sql = "UPDATE _Comments SET reply_to_id = ? WHERE reply_to_id = ?"
        self._db.execute_write(sql, (dispersy_id, mid_global_time), commit=False)
        sql = "UPDATE _Comments SET reply_after_id = ? WHERE reply_after_id = ?"
        self._db.execute_write(sql, (dispersy_id, mid_global_time), commit=self.shouldCommit)

        self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, channel_id)
        if playlist_dispersy_id:
            self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, playlist_id)
        if infohash:
            self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, infohash)

    # dispersy removing comments
    def on_remove_comment_from_dispersy(self, channel_id, dispersy_id, infohash=None, redo=False):
        sql = "UPDATE _Comments SET deleted_at = ? WHERE dispersy_id = ?"

        if redo:
            deleted_at = None
            self._db.execute_write(sql, (deleted_at, dispersy_id), commit=self.shouldCommit)

            self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, channel_id)
            if infohash:
                self.notifier.notify(NTFY_COMMENTS, NTFY_INSERT, infohash)
        else:
            deleted_at = long(time())
            self._db.execute_write(sql, (deleted_at, dispersy_id), commit=self.shouldCommit)

            self.notifier.notify(NTFY_COMMENTS, NTFY_DELETE, channel_id)
            if infohash:
                self.notifier.notify(NTFY_COMMENTS, NTFY_DELETE, infohash)

    # dispersy receiving, modifying playlists
    def on_playlist_from_dispersy(self, channel_id, dispersy_id, peer_id, name, description):
        sql = "INSERT OR REPLACE INTO _Playlists (channel_id, dispersy_id,  peer_id, name, description) VALUES (?, ?, ?, ?, ?)"
        self._db.execute_write(sql, (channel_id, dispersy_id, peer_id, name, description), commit=self.shouldCommit)

        self.notifier.notify(NTFY_PLAYLISTS, NTFY_INSERT, channel_id)

    def on_remove_playlist_from_dispersy(self, channel_id, dispersy_id, redo):
        sql = "UPDATE _Playlists SET deleted_at = ? WHERE channel_id = ? and dispersy_id = ?"

        if redo:
            deleted_at = None
            self._db.execute_write(sql, (deleted_at, channel_id, dispersy_id), commit=self.shouldCommit)
            self.notifier.notify(NTFY_PLAYLISTS, NTFY_INSERT, channel_id)

        else:
            deleted_at = long(time())
            self._db.execute_write(sql, (deleted_at, channel_id, dispersy_id), commit=self.shouldCommit)
            self.notifier.notify(NTFY_PLAYLISTS, NTFY_DELETE, channel_id)

    def on_playlist_modification_from_dispersy(self, playlist_id, modification_type, modification_value, commit=None):
        if commit is None:
            commit = self.shouldCommit

        if modification_type in ['name', 'description']:
            update_playlist = "UPDATE _Playlists Set " + modification_type + " = ?, modified = ? WHERE id = ?"
            self._db.execute_write(update_playlist, (modification_value, long(time()), playlist_id), commit=commit)

            self.notifier.notify(NTFY_PLAYLISTS, NTFY_UPDATE, playlist_id)

    def on_playlist_torrent(self, dispersy_id, playlist_dispersy_id, peer_id, infohash):
        get_playlist = "SELECT id, channel_id FROM _Playlists WHERE dispersy_id = ?"
        playlist_id, channel_id = self._db.fetchone(get_playlist, (playlist_dispersy_id,))

        channeltorrent_id = self.addOrGetChannelTorrentID(channel_id, infohash)
        sql = "INSERT INTO _PlaylistTorrents (dispersy_id, playlist_id, peer_id, channeltorrent_id) VALUES (?,?,?,?)"
        self._db.execute_write(sql, (dispersy_id, playlist_id, peer_id, channeltorrent_id), commit=self.shouldCommit)

        self.notifier.notify(NTFY_PLAYLISTS, NTFY_UPDATE, playlist_id, infohash)

    def on_remove_playlist_torrent(self, channel_id, playlist_dispersy_id, infohash, redo):
        get_playlist = "SELECT id FROM _Playlists WHERE dispersy_id = ? AND channel_id = ?"
        playlist_id = self._db.fetchone(get_playlist, (playlist_dispersy_id, channel_id))

        if playlist_id:
            get_channeltorent_id = "SELECT id FROM _ChannelTorrents, Torrent WHERE _ChannelTorrents.torrent_id = Torrent.torrent_id AND Torrent.infohash = ?"
            channeltorrent_id = self._db.fetchone(get_channeltorent_id, (bin2str(infohash),))

            if channeltorrent_id:
                sql = "UPDATE _PlaylistTorrents SET deleted_at = ? WHERE playlist_id = ? AND channeltorrent_id = ?"

                if redo:
                    deleted_at = None
                else:
                    deleted_at = long(time())
                self._db.execute_write(sql, (deleted_at, playlist_id, channeltorrent_id), commit=self.shouldCommit)

            self.notifier.notify(NTFY_PLAYLISTS, NTFY_UPDATE, playlist_id)

    def on_metadata_from_dispersy(self, type, channeltorrent_id, playlist_id, channel_id, dispersy_id, peer_id, mid_global_time, modification_type_id, modification_value, timestamp, prev_modification_id, prev_modification_global_time, commit=None):
        if commit is None:
            commit = self.shouldCommit

        if isinstance(prev_modification_id, (str)):
            prev_modification_id = buffer(prev_modification_id)

        sql = "INSERT OR REPLACE INTO _ChannelMetaData (dispersy_id, channel_id, peer_id, type_id, value, time_stamp, prev_modification, prev_global_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?); SELECT last_insert_rowid();"
        metadata_id = self._db.fetchone(sql, (dispersy_id, channel_id, peer_id, modification_type_id, modification_value, timestamp, prev_modification_id, prev_modification_global_time))

        if channeltorrent_id:
            sql = "INSERT INTO MetaDataTorrent (metadata_id, channeltorrent_id) VALUES (?,?)"
            self._db.execute_write(sql, (metadata_id, channeltorrent_id), commit=False)

            self.notifier.notify(NTFY_MODIFICATIONS, NTFY_INSERT, channeltorrent_id)

        if playlist_id:
            sql = "INSERT INTO MetaDataPlaylist (metadata_id, playlist_id) VALUES (?,?)"
            self._db.execute_write(sql, (metadata_id, playlist_id), commit=False)

            self.notifier.notify(NTFY_MODIFICATIONS, NTFY_INSERT, playlist_id)
        self.notifier.notify(NTFY_MODIFICATIONS, NTFY_INSERT, channel_id)

        # try fo fix loose reply_to and reply_after pointers
        sql = "UPDATE _ChannelMetaData SET prev_modification = ? WHERE prev_modification = ?;"
        self._db.execute_write(sql, (dispersy_id, buffer(mid_global_time)), commit=commit)

    def on_remove_metadata_from_dispersy(self, channel_id, dispersy_id, redo):
        sql = "UPDATE _ChannelMetaData SET deleted_at = ? WHERE dispersy_id = ? AND channel_id = ?"

        if redo:
            deleted_at = None
        else:
            deleted_at = long(time())
        self._db.execute_write(sql, (deleted_at, dispersy_id, channel_id))

    def on_moderation(self, channel_id, dispersy_id, peer_id, by_peer_id, cause, message, timestamp, severity):
        sql = "INSERT OR REPLACE INTO _Moderations (dispersy_id, channel_id, peer_id, by_peer_id, message, cause, time_stamp, severity) VALUES (?,?,?,?,?,?,?,?)"
        self._db.execute_write(sql, (dispersy_id, channel_id, peer_id, by_peer_id, message, cause, timestamp, severity), commit=self.shouldCommit)

        self.notifier.notify(NTFY_MODERATIONS, NTFY_INSERT, channel_id)

    def on_remove_moderation(self, channel_id, dispersy_id, redo):
        sql = "UPDATE _Moderations SET deleted_at = ? WHERE dispersy_id = ? AND channel_id = ?"
        if redo:
            deleted_at = None
        else:
            deleted_at = long(time())
        self._db.execute_write(sql, (deleted_at, dispersy_id, channel_id))

    def on_mark_torrent(self, channel_id, dispersy_id, global_time, peer_id, infohash, type, timestamp):
        channeltorrent_id = self.addOrGetChannelTorrentID(channel_id, infohash)

        if peer_id:
            select = "SELECT global_time FROM TorrentMarkings WHERE channeltorrent_id = ? AND peer_id = ?"
            prev_global_time = self._db.fetchone(select, (channeltorrent_id, peer_id))
        else:
            select = "SELECT global_time FROM TorrentMarkings WHERE channeltorrent_id = ? AND peer_id IS NULL"
            prev_global_time = self._db.fetchone(select, (channeltorrent_id,))

        if prev_global_time:
            if global_time > prev_global_time:
                if peer_id:
                    sql = "DELETE FROM _TorrentMarkings WHERE channeltorrent_id = ? AND peer_id = ?"
                    self._db.execute_write(sql, (channeltorrent_id, peer_id), commit=False)
                else:
                    sql = "DELETE FROM _TorrentMarkings WHERE channeltorrent_id = ? AND peer_id IS NULL"
                    self._db.execute_write(sql, (channeltorrent_id,), commit=False)
            else:
                return

        sql = "INSERT INTO _TorrentMarkings (dispersy_id, global_time, channeltorrent_id, peer_id, type, time_stamp) VALUES (?,?,?,?,?,?)"
        self._db.execute_write(sql, (dispersy_id, global_time, channeltorrent_id, peer_id, type, timestamp), commit=self.shouldCommit)
        self.notifier.notify(NTFY_MARKINGS, NTFY_INSERT, channeltorrent_id)

    def on_remove_mark_torrent(self, channel_id, dispersy_id, redo):
        sql = "UPDATE _TorrentMarkings SET deleted_at = ? WHERE dispersy_id = ?"

        if redo:
            deleted_at = None
        else:
            deleted_at = long(time())
        self._db.execute_write(sql, (deleted_at, dispersy_id))

    def on_dynamic_settings(self, channel_id):
        self.notifier.notify(NTFY_CHANNELCAST, NTFY_STATE, channel_id)

    def selectTorrentsToCollect(self, channel_id=None):
        if channel_id:
            sql = 'Select infohash From ChannelTorrents, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND channel_id = ? and ChannelTorrents.torrent_id not in (Select torrent_id From CollectedTorrent)'
            records = self._db.fetchall(sql, (channel_id,))
        else:
            sql = 'Select infohash From ChannelTorrents, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND ChannelTorrents.torrent_id not in (Select torrent_id From CollectedTorrent)'
            records = self._db.fetchall(sql)

        return [str2bin(infohash) for infohash, in records]

    def getNrTorrentsDownloaded(self, channel_id):
        sql = "select count(*) from MyPreference, ChannelTorrents where MyPreference.torrent_id = ChannelTorrents.torrent_id and ChannelTorrents.channel_id = ? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))

    def getNrTorrentsInChannel(self, channel_id, collected=False):
        if collected:
            sql = "select count(ChannelTorrents.torrent_id) from ChannelTorrents, CollectedTorrent where ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND channel_id==? LIMIT 1"
        else:
            sql = "select count(ChannelTorrents.torrent_id) from ChannelTorrents where channel_id==? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))

    def getLatestUpdateNrTorrentsInChannel(self, channel_id, collected=False):
        if collected:
            sql = "select max(ChannelTorrents.time_stamp), count(ChannelTorrents.torrent_id) from ChannelTorrents, CollectedTorrent where ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND channel_id==? LIMIT 1"
        else:
            sql = "select max(ChannelTorrents.time_stamp), count(ChannelTorrents.torrent_id) from ChannelTorrents where channel_id==? LIMIT 1"
        return self._db.fetchone(sql, (channel_id,))

    def getChannelNrTorrents(self, limit=None):
        if limit:
            sql = "select count(torrent_id), channel_id from Channels, ChannelTorrents WHERE Channels.id = ChannelTorrents.channel_id AND dispersy_cid <>  -1 GROUP BY channel_id ORDER BY RANDOM() LIMIT ?"
            return self._db.fetchall(sql, (limit,))

        sql = "select count(torrent_id), channel_id from Channels, ChannelTorrents WHERE Channels.id = ChannelTorrents.channel_id AND dispersy_cid <>  -1 GROUP BY channel_id"
        return self._db.fetchall(sql)

    def getChannelNrTorrentsLatestUpdate(self, limit=None):
        if limit:
            sql = "select count(CollectedTorrent.torrent_id), max(ChannelTorrents.time_stamp), channel_id from Channels, ChannelTorrents, CollectedTorrent WHERE ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND dispersy_cid == -1 GROUP BY channel_id ORDER BY RANDOM() LIMIT ?"
            return self._db.fetchall(sql, (limit,))

        sql = "select count(CollectedTorrent.torrent_id), max(ChannelTorrents.time_stamp), channel_id from Channels, ChannelTorrents, CollectedTorrent WHERE ChannelTorrents.torrent_id = CollectedTorrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND dispersy_cid == -1 GROUP BY channel_id"
        return self._db.fetchall(sql)

    def getNrChannels(self):
        sql = "select count(DISTINCT id) from Channels LIMIT 1"
        return self._db.fetchone(sql)

    def getPermidForChannel(self, channel_id):
        sql = "SELECT permid FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id AND Channels.id = ?"
        return self._db.fetchone(sql, (channel_id,))

    def getPermidForChannels(self, channel_ids):
        if len(channel_ids) == 1:
            return self.getPermidForChannel(channel_ids[0])

        sql = "SELECT permid FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id AND Channels.id in ("
        sql += ','.join(channel_ids)
        sql += ")"
        return self._db.fetchall(sql)

    def getPermChannelIdDict(self, binary=False):
        returndict = {}

        sql = "SELECT permid, Channels.id FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id GROUP BY permid"
        results = self._db.fetchall(sql)
        for permid, channel_id in results:
            if binary:
                returndict[str2bin(permid)] = channel_id
            else:
                returndict[permid] = channel_id

        return returndict

    def getPermidForChannelsDict(self, channel_ids=None):
        if len(channel_ids) == 1:
            channel_ids = list(channel_ids)
            return {channel_ids[0]: self.getPermidForChannel(channel_ids[0])}

        returndict = {}

        sql = "SELECT Channels.id, permid FROM Peer, Channels WHERE Channels.peer_id = Peer.peer_id GROUP BY permid"
        results = self._db.fetchall(sql)
        for channel_id, permid in results:
            returndict[channel_id] = permid
        return returndict

    def getRecentAndRandomTorrents(self, NUM_OWN_RECENT_TORRENTS=15, NUM_OWN_RANDOM_TORRENTS=10, NUM_OTHERS_RECENT_TORRENTS=15, NUM_OTHERS_RANDOM_TORRENTS=10, NUM_OTHERS_DOWNLOADED=5):
        torrent_dict = {}

        least_recent = -1
        sql = "select dispersy_cid, infohash, time_stamp from ChannelTorrents, Channels, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.channel_id==? and ChannelTorrents.dispersy_id <> -1 order by time_stamp desc limit ?"
        myrecenttorrents = self._db.fetchall(sql, (self._channel_id, NUM_OWN_RECENT_TORRENTS))
        for cid, infohash, timestamp in myrecenttorrents:
            torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))
            least_recent = timestamp

        if len(myrecenttorrents) == NUM_OWN_RECENT_TORRENTS and least_recent != -1:
            sql = "select dispersy_cid, infohash from ChannelTorrents, Channels, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.channel_id==? and time_stamp<? and ChannelTorrents.dispersy_id <> -1 order by random() limit ?"
            myrandomtorrents = self._db.fetchall(sql, (self._channel_id, least_recent, NUM_OWN_RANDOM_TORRENTS))
            for cid, infohash, _ in myrecenttorrents:
                torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))

            for cid, infohash in myrandomtorrents:
                torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))

        nr_records = sum(len(torrents) for torrents in torrent_dict.values())
        additionalSpace = (NUM_OWN_RECENT_TORRENTS + NUM_OWN_RANDOM_TORRENTS) - nr_records

        if additionalSpace > 0:
            NUM_OTHERS_RECENT_TORRENTS += additionalSpace / 2
            NUM_OTHERS_RANDOM_TORRENTS += additionalSpace - (additionalSpace / 2)

            # Niels 6-12-2011: we should substract additionalspace from recent and random, otherwise the totals will not be correct.
            NUM_OWN_RECENT_TORRENTS -= additionalSpace / 2
            NUM_OWN_RANDOM_TORRENTS -= additionalSpace - (additionalSpace / 2)

        least_recent = -1
        sql = "select dispersy_cid, infohash, time_stamp from ChannelTorrents, Channels, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.channel_id in (select channel_id from ChannelVotes where voter_id ISNULL and vote=2) and ChannelTorrents.dispersy_id <> -1 order by time_stamp desc limit ?"
        othersrecenttorrents = self._db.fetchall(sql, (NUM_OTHERS_RECENT_TORRENTS,))
        for cid, infohash, timestamp in othersrecenttorrents:
            torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))
            least_recent = timestamp

        if othersrecenttorrents and len(othersrecenttorrents) == NUM_OTHERS_RECENT_TORRENTS and least_recent != -1:
            sql = "select dispersy_cid, infohash from ChannelTorrents, Channels, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.channel_id in (select channel_id from ChannelVotes where voter_id ISNULL and vote=2) and time_stamp < ? and ChannelTorrents.dispersy_id <> -1 order by random() limit ?"
            othersrandomtorrents = self._db.fetchall(sql, (least_recent, NUM_OTHERS_RANDOM_TORRENTS))
            for cid, infohash in othersrandomtorrents:
                torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))

        twomonthsago = long(time() - 5259487)
        nr_records = sum(len(torrents) for torrents in torrent_dict.values())
        additionalSpace = (NUM_OWN_RECENT_TORRENTS + NUM_OWN_RANDOM_TORRENTS + NUM_OTHERS_RECENT_TORRENTS + NUM_OTHERS_RANDOM_TORRENTS) - nr_records
        NUM_OTHERS_DOWNLOADED += additionalSpace

        sql = "select dispersy_cid, infohash from ChannelTorrents, Channels, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.channel_id in (select distinct channel_id from ChannelTorrents where torrent_id in (select torrent_id from MyPreference)) and ChannelTorrents.dispersy_id <> -1 and Channels.modified > ? order by time_stamp desc limit ?"
        interesting_records = self._db.fetchall(sql, (twomonthsago, NUM_OTHERS_DOWNLOADED))
        for cid, infohash in interesting_records:
            torrent_dict.setdefault(str(cid), set()).add(str2bin(infohash))

        return torrent_dict

    def getRandomTorrents(self, channel_id, limit=15, dispersyOnly=True):
        twomonthsago = long(time() - 5259487)
        sql = "select infohash from ChannelTorrents, Torrent where ChannelTorrents.torrent_id = Torrent.torrent_id AND channel_id = ? and ChannelTorrents.time_stamp > ?"
        if dispersyOnly:
            sql += " and ChannelTorrents.dispersy_id != -1"
        sql += " ORDER BY RANDOM() LIMIT ?"

        returnar = []
        for infohash, in self._db.fetchall(sql, (channel_id, twomonthsago, limit)):
            returnar.append(str2bin(infohash))
        return returnar

    def getTorrentFromChannelId(self, channel_id, infohash, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? AND infohash = ?"
        result = self._db.fetchone(sql, (channel_id, bin2str(infohash)))

        return self.__fixTorrent(keys, result)

    def getChannelTorrents(self, infohash, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND infohash = ?"
        results = self._db.fetchall(sql, (bin2str(infohash),))

        return self.__fixTorrents(keys, results)

    def getTorrentFromChannelTorrentId(self, channeltorrent_id, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = ?"
        result = self._db.fetchone(sql, (channeltorrent_id,))
        if not result:
            print >> sys.stderr, "COULD NOT FIND CHANNELTORRENT_ID", channeltorrent_id
        else:
            return self.__fixTorrent(keys, result)

    def getTorrentsFromChannelId(self, channel_id, isDispersy, keys, limit=None):
        if isDispersy:
            sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id"
        else:
            sql = "SELECT " + ", ".join(keys) + " FROM CollectedTorrent as Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id"

        if channel_id:
            sql += " AND channel_id = ?"
        sql += " ORDER BY time_stamp DESC"

        if limit:
            sql += " LIMIT %d" % limit

        if channel_id:
            results = self._db.fetchall(sql, (channel_id,))
        else:
            results = self._db.fetchall(sql)

        if limit is None and channel_id:
            # use this possibility to update nrtorrent in channel

            if 'time_stamp' in keys and len(results) > 0:
                update = "UPDATE _Channels SET nr_torrents = ?, modified = ? WHERE id = ?"
                self._db.execute_write(update, (len(results), results[0][keys.index('time_stamp')], channel_id))
            else:
                # use this possibility to update nrtorrent in channel
                update = "UPDATE _Channels SET nr_torrents = ? WHERE id = ?"
                self._db.execute_write(update, (len(results), channel_id))

        return self.__fixTorrents(keys, results)

    def getRecentReceivedTorrentsFromChannelId(self, channel_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? ORDER BY inserted DESC"
        if limit:
            sql += " LIMIT %d" % limit
        results = self._db.fetchall(sql, (channel_id,))
        return self.__fixTorrents(keys, results)

    def getRecentModificationsFromChannelId(self, channel_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM ChannelMetaData LEFT JOIN MetaDataTorrent ON ChannelMetaData.id = MetaDataTorrent.metadata_id LEFT JOIN Moderations ON Moderations.cause = ChannelMetaData.dispersy_id WHERE ChannelMetaData.channel_id = ? ORDER BY -Moderations.time_stamp ASC, ChannelMetaData.inserted DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (channel_id,))

    def getRecentModerationsFromChannel(self, channel_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Moderations, MetaDataTorrent, ChannelMetaData WHERE Moderations.cause = ChannelMetaData.dispersy_id AND ChannelMetaData.id = MetaDataTorrent.metadata_id AND Moderations.channel_id = ? ORDER BY Moderations.inserted DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (channel_id,))

    def getRecentMarkingsFromChannel(self, channel_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM TorrentMarkings, ChannelTorrents WHERE TorrentMarkings.channeltorrent_id = ChannelTorrents.id AND ChannelTorrents.channel_id = ? ORDER BY TorrentMarkings.time_stamp DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (channel_id,))

    def getMostPopularTorrentsFromChannel(self, channel_id, isDispersy, keys, limit=None):
        if isDispersy:
            sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? GROUP BY Torrent.torrent_id ORDER BY ChannelTorrents.time_stamp DESC"
        else:
            sql = "SELECT " + ", ".join(keys) + " FROM CollectedTorrent as Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? GROUP BY Torrent.torrent_id ORDER BY ChannelTorrents.time_stamp DESC"

        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (channel_id,))

    def getTorrentsFromPlaylist(self, playlist_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents, PlaylistTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND playlist_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d" % limit
        results = self._db.fetchall(sql, (playlist_id,))
        return self.__fixTorrents(keys, results)

    def getTorrentFromPlaylist(self, playlist_id, infohash, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents, PlaylistTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND playlist_id = ? AND infohash = ?"
        result = self._db.fetchone(sql, (playlist_id, bin2str(infohash)))

        return self.__fixTorrent(keys, result)

    def getRecentTorrentsFromPlaylist(self, playlist_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents, PlaylistTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND playlist_id = ? ORDER BY inserted DESC"
        if limit:
            sql += " LIMIT %d" % limit
        results = self._db.fetchall(sql, (playlist_id,))
        return self.__fixTorrents(keys, results)

    def getRecentModificationsFromPlaylist(self, playlist_id, keys, limit=None):
        playlistKeys = keys[:]
        if 'MetaDataTorrent.channeltorrent_id' in playlistKeys:
            playlistKeys[playlistKeys.index('MetaDataTorrent.channeltorrent_id')] = '""'

        sql = "SELECT " + ", ".join(playlistKeys) + " FROM MetaDataPlaylist, ChannelMetaData LEFT JOIN Moderations ON Moderations.cause = ChannelMetaData.dispersy_id WHERE MetaDataPlaylist.metadata_id = ChannelMetaData.id AND playlist_id = ?"
        if limit:
            sql += " LIMIT %d" % limit
        playlist_modifications = self._db.fetchall(sql, (playlist_id,))

        sql = "SELECT " + ", ".join(keys) + " FROM MetaDataTorrent, ChannelMetaData, PlaylistTorrents LEFT JOIN Moderations ON Moderations.cause = ChannelMetaData.dispersy_id WHERE MetaDataTorrent.metadata_id = ChannelMetaData.id AND PlaylistTorrents.channeltorrent_id = MetaDataTorrent.channeltorrent_id AND playlist_id = ?"
        if limit:
            sql += " LIMIT %d" % limit
        torrent_modifications = self._db.fetchall(sql, (playlist_id,))

        # merge two lists
        orderIndex = keys.index('ChannelMetaData.time_stamp')
        revertIndex = keys.index('Moderations.time_stamp')
        data = [(row[revertIndex], row[orderIndex], row) for row in playlist_modifications]
        data += [(row[revertIndex], row[orderIndex], row) for row in torrent_modifications]
        data.sort(reverse=True)

        if limit:
            data = data[:limit]
        data = [item for _, _, item in data]
        return data

    def getRecentModerationsFromPlaylist(self, playlist_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Moderations, MetaDataTorrent, ChannelMetaData, PlaylistTorrents WHERE Moderations.cause = ChannelMetaData.dispersy_id AND ChannelMetaData.id = MetaDataTorrent.metadata_id AND MetaDataTorrent.channeltorrent_id = PlaylistTorrents.channeltorrent_id AND PlaylistTorrents.playlist_id = ? ORDER BY Moderations.inserted DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (playlist_id,))

    def getRecentMarkingsFromPlaylist(self, playlist_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM TorrentMarkings, PlaylistTorrents, ChannelTorrents WHERE TorrentMarkings.channeltorrent_id = PlaylistTorrents.channeltorrent_id AND ChannelTorrents.id = PlaylistTorrents.channeltorrent_id AND PlaylistTorrents.playlist_id = ? AND ChannelTorrents.dispersy_id <> -1 ORDER BY TorrentMarkings.time_stamp DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (playlist_id,))

    def getTorrentsNotInPlaylist(self, channel_id, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? And ChannelTorrents.id NOT IN (Select channeltorrent_id From PlaylistTorrents) ORDER BY time_stamp DESC"
        results = self._db.fetchall(sql, (channel_id,))
        return self.__fixTorrents(keys, results)

    def getPlaylistForTorrent(self, channeltorrent_id, keys):
        sql = "SELECT " + ", ".join(keys) + ", count(DISTINCT channeltorrent_id) FROM Playlists, PlaylistTorrents WHERE Playlists.id = PlaylistTorrents.playlist_id AND channeltorrent_id = ?"
        result = self._db.fetchone(sql, (channeltorrent_id,))
        # Niels: 29-02-2012 due to the count this always returns one row, check count to return None if playlist was actually not found.
        if result[-1]:
            return result

    def getPlaylistsForTorrents(self, torrent_ids, keys):
        torrent_ids = " ,".join(map(str, torrent_ids))

        sql = "SELECT channeltorrent_id, " + ", ".join(keys) + ", count(DISTINCT channeltorrent_id) FROM Playlists, PlaylistTorrents WHERE Playlists.id = PlaylistTorrents.playlist_id AND channeltorrent_id IN (" + torrent_ids + ") GROUP BY Playlists.id"
        return self._db.fetchall(sql)

    def __fixTorrent(self, keys, torrent):
        if len(keys) == 1:
            if keys[0] == 'infohash':
                return str2bin(torrent)
            return torrent

        def fix_value(key, torrent):
            if key in keys:
                key_index = keys.index(key)
                if torrent[key_index]:
                    torrent[key_index] = str2bin(torrent[key_index])
        if torrent:
            torrent = list(torrent)
            fix_value('infohash', torrent)
            fix_value('swift_hash', torrent)
            fix_value('swift_torrent_hash', torrent)
        return torrent

    def __fixTorrents(self, keys, results):
        def fix_value(key):
            if key in keys:
                key_index = keys.index(key)
                for i in range(len(results)):
                    result = list(results[i])
                    if result[key_index]:
                        result[key_index] = str2bin(result[key_index])
                        results[i] = result
        fix_value('infohash')
        fix_value('swift_hash')
        fix_value('swift_torrent_hash')
        return results

    def getPlaylistsFromChannelId(self, channel_id, keys):
        sql = "SELECT " + ", ".join(keys) + ", count(DISTINCT ChannelTorrents.id) FROM Playlists LEFT JOIN PlaylistTorrents ON Playlists.id = PlaylistTorrents.playlist_id LEFT JOIN ChannelTorrents ON PlaylistTorrents.channeltorrent_id = ChannelTorrents.id WHERE Playlists.channel_id = ? GROUP BY Playlists.id ORDER BY Playlists.name DESC"
        return self._db.fetchall(sql, (channel_id,))

    def getPlaylist(self, playlist_id, keys):
        sql = "SELECT " + ", ".join(keys) + ", count(DISTINCT ChannelTorrents.id) FROM Playlists LEFT JOIN PlaylistTorrents ON Playlists.id = PlaylistTorrents.playlist_id LEFT JOIN ChannelTorrents ON PlaylistTorrents.channeltorrent_id = ChannelTorrents.id WHERE Playlists.id = ? GROUP BY Playlists.id"
        return self._db.fetchone(sql, (playlist_id,))

    def getCommentsFromChannelId(self, channel_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Comments LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id LEFT JOIN CommentPlaylist ON Comments.id = CommentPlaylist.comment_id LEFT JOIN CommentTorrent ON Comments.id = CommentTorrent.comment_id WHERE channel_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d" % limit
        return self._db.fetchall(sql, (channel_id,))

    def getCommentsFromPlayListId(self, playlist_id, keys, limit=None):
        playlistKeys = keys[:]
        if 'CommentTorrent.channeltorrent_id' in playlistKeys:
            playlistKeys[playlistKeys.index('CommentTorrent.channeltorrent_id')] = '""'

        sql = "SELECT " + ", ".join(playlistKeys) + " FROM Comments LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id LEFT JOIN CommentPlaylist ON Comments.id = CommentPlaylist.comment_id WHERE playlist_id = ?"
        if limit:
            sql += " LIMIT %d" % limit

        playlist_comments = self._db.fetchall(sql, (playlist_id,))

        sql = "SELECT " + ", ".join(keys) + " FROM Comments, CommentTorrent, PlaylistTorrents LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id WHERE Comments.id = CommentTorrent.comment_id AND PlaylistTorrents.channeltorrent_id = CommentTorrent.channeltorrent_id AND playlist_id = ?"
        if limit:
            sql += " LIMIT %d" % limit

        torrent_comments = self._db.fetchall(sql, (playlist_id,))

        # merge two lists
        orderIndex = keys.index('time_stamp')
        data = [(row[orderIndex], row) for row in playlist_comments]
        data += [(row[orderIndex], row) for row in torrent_comments]
        data.sort(reverse=True)

        if limit:
            data = data[:limit]
        data = [item for _, item in data]
        return data

    def getCommentsFromChannelTorrentId(self, channeltorrent_id, keys, limit=None):
        sql = "SELECT " + ", ".join(keys) + " FROM Comments, CommentTorrent LEFT JOIN Peer ON Comments.peer_id = Peer.peer_id WHERE Comments.id = CommentTorrent.comment_id AND channeltorrent_id = ? ORDER BY time_stamp DESC"
        if limit:
            sql += " LIMIT %d" % limit

        return self._db.fetchall(sql, (channeltorrent_id,))

    def searchChannelsTorrent(self, keywords, limitChannels=None, limitTorrents=None, dispersyOnly=False):
        # search channels based on keywords
        keywords = split_into_keywords(keywords)
        keywords = [keyword for keyword in keywords if len(keyword) > 1]

        if len(keywords) > 0:
            sql = "SELECT distinct id, dispersy_cid, name FROM Channels WHERE"
            for keyword in keywords:
                sql += " name like '%" + keyword + "%' and"

            if dispersyOnly:
                sql += " dispersy_cid != '-1'"
            else:
                sql = sql[:-3]

            if limitChannels:
                sql += " LIMIT %d" % limitChannels

            channels = self._db.fetchall(sql)
            select_torrents = "SELECT infohash, ChannelTorrents.name, Torrent.name, time_stamp from Torrent, ChannelTorrents WHERE Torrent.torrent_id = ChannelTorrents.torrent_id AND channel_id = ? ORDER BY num_seeders DESC LIMIT ?"

            limitTorrents = limitTorrents or 20

            results = []
            for channel_id, dispersy_cid, name in channels:
                dispersy_cid = str(dispersy_cid)
                torrents = self._db.fetchall(select_torrents, (channel_id, limitTorrents))
                for infohash, ChTname, CoTname, time_stamp in torrents:
                    infohash = str2bin(infohash)
                    results.append((channel_id, dispersy_cid, name, infohash, ChTname or CoTname, time_stamp))
            return results
        return []

    def searchChannels(self, keywords):
        sql = "SELECT id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE"
        for keyword in keywords:
            sql += " name like '%" + keyword + "%' and"
        sql = sql[:-3]
        return self._getChannels(sql)

    def getChannelNames(self, permids):
        names = {}

        publishers = "','".join(permids)
        sqla = "Select publisher_id, max(ChannelCast.time_stamp) FROM ChannelCast WHERE publisher_id IN ('" + publishers + "') GROUP BY publisher_id"
        sqlb = "Select publisher_name From ChannelCast Where publisher_id = ? And time_stamp = ? LIMIT 1"

        results = self._db.fetchall(sqla)
        for publisher_id, timestamp in results:
            result = self._db.fetchone(sqlb, (publisher_id, timestamp))
            names[publisher_id] = result
        return names

    def getChannel(self, channel_id):
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE id = ?"
        channels = self._getChannels(sql, (channel_id,))
        if len(channels) > 0:
            return channels[0]

    def getChannelByCID(self, channel_cid):
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE dispersy_cid = ?"
        channels = self._getChannels(sql, (buffer(channel_cid),))
        if len(channels) > 0:
            return channels[0]

    def getChannelFromPermid(self, channel_permid):
        sql = "Select C.id, C.name, C.description, C.dispersy_cid, C.modified, C.nr_torrents, C.nr_favorite, C.nr_spam FROM Channels as C, Peer WHERE C.peer_id = Peer.peer_id AND Peer.permid = ?"
        channels = self._getChannels(sql, (channel_permid,))
        if len(channels) > 0:
            return channels[0]

    def getChannels(self, channel_ids):
        channel_ids = "','".join(map(str, channel_ids))
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE id IN ('" + channel_ids + "')"
        return self._getChannels(sql)

    def getChannelsByCID(self, channel_cids):
        parameters = '?,' * len(channel_cids)
        parameters = parameters[:-1]

        channel_cids = map(buffer, channel_cids)
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE dispersy_cid IN (" + parameters + ")"
        return self._getChannels(sql, channel_cids)

    def getAllChannels(self):
        """ Returns all the channels """
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels"
        return self._getChannels(sql)

    def getNewChannels(self, updated_since=0):
        """ Returns all newest unsubscribed channels, ie the ones with no votes (positive or negative)"""
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels WHERE nr_favorite = 0 AND nr_spam = 0 AND modified > ?"
        return self._getChannels(sql, (updated_since,))

    def getLatestUpdated(self, max_nr=20):
        def channel_sort(a, b):
            # first compare local vote, spam -> return -1
            if a[7] == -1:
                return 1
            if b[7] == -1:
                return -1

            # then compare latest update
            if a[8] < b[8]:
                return 1
            if a[8] > b[8]:
                return -1
            # finally compare nr_torrents
            return cmp(a[4], b[4])

        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels Order By modified DESC Limit ?"
        return self._getChannels(sql, (max_nr,), cmpF=channel_sort)

    def getMostPopularChannels(self, max_nr=20):
        sql = "Select id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels ORDER BY nr_favorite DESC, modified DESC LIMIT ?"
        return self._getChannels(sql, (max_nr,), includeSpam=False)

    def getMySubscribedChannels(self, includeDispsersy=False):
        sql = "SELECT id, name, description, dispersy_cid, modified, nr_torrents, nr_favorite, nr_spam FROM Channels, ChannelVotes WHERE Channels.id = ChannelVotes.channel_id AND voter_id ISNULL AND vote == 2"
        if not includeDispsersy:
            sql += " AND dispersy_cid == -1"

        return self._getChannels(sql)

    def _getChannels(self, sql, args=None, cmpF=None, includeSpam=True):
        """Returns the channels based on the input sql, if the number of positive votes is less than maxvotes and the number of torrent > 0"""
        channels = []
        results = self._db.fetchall(sql, args)

        my_votes = self.votecast_db.getMyVotes()
        for id, name, description, dispersy_cid, modified, nr_torrents, nr_favorites, nr_spam in results:
            my_vote = my_votes.get(id, 0)
            if not includeSpam and my_vote < 0:
                continue
            if name.strip() == '':
                continue

            channels.append((id, str(dispersy_cid), name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified, id == self._channel_id))

        def channel_sort(a, b):
            # first compare local vote, spam -> return -1
            if a[7] == -1:
                return 1
            if b[7] == -1:
                return -1

            # then compare nr_favorites
            if a[5] < b[5]:
                return 1
            if a[5] > b[5]:
                return -1

            # then compare latest update
            if a[8] < b[8]:
                return 1
            if a[8] > b[8]:
                return -1

            # finally compare nr_torrents
            return cmp(a[4], b[4])

        if cmpF == None:
            cmpF = channel_sort
        channels.sort(cmpF)
        return channels

    def getMySubscribersCount(self):
        return self.getSubscribersCount(self._channel_id)

    def getMyChannelId(self):
        if self._channel_id:
            return self._channel_id
        return self._db.fetchone('SELECT id FROM Channels WHERE peer_id ISNULL LIMIT 1')

    def getSubscribersCount(self, channel_id):
        """returns the number of subscribers in integer format"""

        nr_favorites, nr_spam = self.votecast_db.getPosNegVotes(channel_id)
        return nr_favorites

    def getTimeframeForChannel(self, channel_id):
        sql = 'Select min(time_stamp), max(time_stamp), count(distinct torrent_id) From ChannelTorrents Where channel_id = ?'
        return self._db.fetchone(sql, (channel_id,))

    def getTorrentMarkings(self, channeltorrent_id):
        counts = {}
        sql = "SELECT type, peer_id FROM TorrentMarkings WHERE channeltorrent_id = ?"
        for type, peer_id in self._db.fetchall(sql, (channeltorrent_id,)):
            if type not in counts:
                counts[type] = [type, 0, False]
            counts[type][1] += 1
            if not peer_id:
                counts[type][2] = True
        return counts.values()

    def getTorrentModifications(self, channeltorrent_id, keys):
        sql = "SELECT " + ", ".join(keys) + " FROM MetaDataTorrent, ChannelMetaData LEFT JOIN Moderations ON Moderations.cause = ChannelMetaData.dispersy_id WHERE metadata_id = ChannelMetaData.id AND channeltorrent_id = ? ORDER BY -Moderations.time_stamp ASC, prev_global_time DESC"
        return self._db.fetchall(sql, (channeltorrent_id,))

    def getMostPopularChannelFromTorrent(self, infohash):
        """Returns channel id, name, nrfavorites of most popular channel if any"""
        sql = "select Channels.id, Channels.dispersy_cid, Channels.name, Channels.description, Channels.nr_torrents, Channels.nr_favorite, Channels.nr_spam, Channels.modified, ChannelTorrents.id from Channels, ChannelTorrents, Torrent where Channels.id = ChannelTorrents.channel_id AND ChannelTorrents.torrent_id = Torrent.torrent_id AND infohash = ?"
        channels = self._db.fetchall(sql, (bin2str(infohash),))

        if len(channels) > 0:
            channel_ids = set()
            for result in channels:
                channel_ids.add(result[0])

            myVotes = self.votecast_db.getMyVotes()

            best_channel = None
            for id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, modified, channeltorrent_id in channels:
                channel = id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, myVotes.get(id, 0), modified, id == self._channel_id, channeltorrent_id

                # allways prefer mychannel
                if channel[-1]:
                    return channel

                if not best_channel or channel[5] > best_channel[5]:
                    best_channel = channel
                elif channel[5] == best_channel[5] and channel[4] > best_channel[4]:
                    best_channel = channel
            return best_channel


class SearchDBHandler(BasicDBHandler):

    def __init__(self):
        if SearchDBHandler._single is not None:
            raise RuntimeError("SearchDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'ClicklogSearch')  # # self,db,'Search'

    def storeKeywords(self, peer_id, torrent_id, terms, commit=True):
        """creates a single entry in Search with peer_id and torrent_id for every term in terms"""
        terms = [term.strip() for term in terms if len(term.strip()) > 0]
        term_ids = self.getTermsIDS(terms)
        if term_ids:
            term_ids = [id for id, term in term_ids]
            self.storeKeywordsByID(peer_id, torrent_id, term_ids, commit)

    def storeKeywordsByID(self, peer_id, torrent_id, term_ids, commit=True):
        sql_insert_search = u"INSERT INTO ClicklogSearch (peer_id, torrent_id, term_id, term_order) values (?, ?, ?, ?)"

        if len(term_ids) > MAX_KEYWORDS_STORED:
            term_ids = term_ids[0:MAX_KEYWORDS_STORED]

        # TODO before we insert, we should delete all potentially existing entries
        # with these exact values
        # otherwise, some strange attacks might become possible
        # and again we cannot assume that user/torrent/term only occurs once

        # vliegendhart: only store 1 query per (peer_id,torrent_id)
        # Step 1: delete (peer_id,torrent_id) records, if any
        self._db.execute_write("DELETE FROM ClicklogSearch WHERE peer_id=? AND torrent_id=?", [peer_id, torrent_id])

        # create insert data
        values = [(peer_id, torrent_id, term_id, term_order)
                  for (term_id, term_order)
                  in zip(term_ids, range(len(term_ids)))]
        self._db.executemany(sql_insert_search, values, commit=commit)

    def getTermID(self, term):
        row = self.getTermsIDS([term])
        if row:
            return row[1]

    def getTermsIDS(self, terms):
        parameters = '?,' * len(terms)
        sql = "SELECT term_id, term FROM TermFrequency WHERE term IN (" + parameters[:-1] + ")"
        return self._db.fetchall(sql, terms)

    def getTorrentSearchTerms(self, torrent_id, peer_id):
        return self.getAll("term_id", "torrent_id=%d AND peer_id=%s" % (torrent_id, peer_id), order_by="term_order")

    def getMyTorrentsSearchTermsStr(self, torrent_ids):
        return_dict = {}
        for torrent_id in torrent_ids:
            return_dict[torrent_id] = set()

        parameters = '?,' * len(torrent_ids)
        sql = "SELECT torrent_id, term FROM ClicklogSearch, TermFrequency WHERE ClicklogSearch.term_id = TermFrequency.term_id AND torrent_id IN (" + parameters[:-1] + ") AND peer_id = ? ORDER BY freq"

        parameters = torrent_ids[:]
        parameters.append(0)
        for torrent_id, term in self._db.fetchall(sql, parameters):
            return_dict[torrent_id].add(term)
        return return_dict


class NetworkBuzzDBHandler(BasicDBHandler):

    """
    The Network Buzz database handler singleton for sampling the TermFrequency table
    and maintaining the TorrentBiTermPhrase table.
    """

    def __init__(self):
        if NetworkBuzzDBHandler._single is not None:
            raise RuntimeError("NetworkBuzzDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'TermFrequency')

        from Tribler.Core.Tag.Extraction import TermExtraction
        self.extractor = TermExtraction.getInstance()

        self.updateBiPhraseCount()

        self.new_terms = {}
        self.update_terms = {}
        self.new_phrases = []

        self.termLock = Lock()
        db.schedule_task(self.__flush_to_database, delay=5.0 if self.nr_bi_phrases < 100 else 20.0)

    def __flush_to_database(self):
        while True:
            with self.termLock:
                try:
                    add_new_terms_sql = "INSERT INTO TermFrequency (term, freq) VALUES (?, ?);"
                    update_exist_terms_sql = "UPDATE OR REPLACE TermFrequency SET freq = ? WHERE term_id = ?;"
                    ins_phrase_sql = u"""INSERT OR REPLACE INTO TorrentBiTermPhrase (torrent_id, term1_id, term2_id)
                                        SELECT ? AS torrent_id, TF1.term_id, TF2.term_id
                                        FROM TermFrequency TF1, TermFrequency TF2
                                        WHERE TF1.term = ? AND TF2.term = ?"""

                    self._db.executemany(add_new_terms_sql, self.new_terms.values(), commit=False)
                    self._db.executemany(update_exist_terms_sql, self.update_terms.values(), commit=False)
                    self._db.executemany(ins_phrase_sql, self.new_phrases, commit=False)
                except:
                    print_exc()
                    print >> sys.stderr, "could not insert terms", self.new_terms.values()

                self.new_terms.clear()
                self.update_terms.clear()
                self.new_phrases = []

            if self.nr_bi_phrases < self.MAX_UNCOLLECTED:
                self.updateBiPhraseCount()

            if self.nr_bi_phrases < 100:
                yield 5.0
            else:
                yield 20.0

    def updateBiPhraseCount(self):
        count_sql = "SELECT COUNT(*) FROM TorrentBiTermPhrase"
        self.nr_bi_phrases = self._db.fetchone(count_sql)

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

    # Only start adding collected torrents at
    MAX_UNCOLLECTED = 5000

    # Tables from which can be sampled:
    TABLES = dict(
        TermFrequency=dict(
            table='TermFrequency',
            selected_fields='term',
            min_freq=2
        ),
        TorrentBiTermPhrase=dict(
            table='''
            (
                SELECT TF1.term || " " || TF2.term AS phrase,
                       COUNT(*) AS freq
                FROM TorrentBiTermPhrase P, TermFrequency TF1, TermFrequency TF2
                WHERE P.term1_id = TF1.term_id AND P.term2_id = TF2.term_id
                GROUP BY term1_id, term2_id
            )
            ''',
            selected_fields='phrase',
            min_freq=1
        )
    )

    def addTorrent(self, torrent_id, torrent_name, collected=False, commit=True):
        """
        Extracts terms and the bi-term phrase from the added Torrent and stores it in
        the TermFrequency and TorrentBiTermPhrase tables, respectively.

        @param torrent_id Identifier of the added Torrent.
        @param torrent_name Name of the added Torrent.
        @param commit Flag to indicate whether database changes should be committed.
        """
        if collected or self.nr_bi_phrases < self.MAX_UNCOLLECTED:
            keywords = split_into_keywords(torrent_name)
            terms = set(self.extractor.extractTerms(keywords))
            phrase = self.extractor.extractBiTermPhrase(keywords)

            parameters = '?,' * len(terms)
            sql = "SELECT * FROM TermFrequency WHERE term IN (" + parameters[:-1] + ")"
            results = self._db.fetchall(sql, terms)

            newterms = terms.copy()
            for term_id, term, freq in results:
                newterms.remove(term)

            with self.termLock:
                for term in newterms:
                    if term in self.new_terms:
                        self.new_terms[term][1] += 1
                    else:
                        self.new_terms[term] = [term, 1]

                for term_id, term, freq in results:
                    if term_id in self.update_terms:
                        self.update_terms[term_id][0] += 1
                    else:
                        self.update_terms[term_id] = [freq + 1, term_id]

                if phrase is not None:
                    self.new_phrases.append((torrent_id,) + phrase)

    def deleteTorrent(self, torrent_id, commit=True):
        """
        Updates the TorrentBiTermPhrase table to reflect the change that a Torrent
        has been deleted.

        Currently, the TermFrequency table remains unaffected.

        @param torrent_id Identifier of the deleted Torrent.
        @param commit Flag to indicate whether database changes should be committed.
        """
        self._db.delete('TorrentBiTermPhrase', commit=commit, torrent_id=torrent_id)

    def getBuzz(self, size=DEFAULT_SAMPLE_SIZE, with_freq=True, flat=False):
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
        num_torrents = self._db.size('CollectedTorrent')
        if num_torrents is None or num_torrents < self.NUM_TORRENTS_THRESHOLD:
            max_freq = None
        else:
            max_freq = int(round(num_torrents * self.STOPWORD_THRESHOLD))

        terms_triple = self.getBuzzForTable('TermFrequency', size, with_freq, max_freq=max_freq)
        # Niels: 29-02-2012 at startup we only request 10 terms
        if not flat or size > 10:
            phrases_triple = self.getBuzzForTable('TorrentBiTermPhrase', size, with_freq)
        else:
            phrases_triple = []

        if not flat:
            return terms_triple, phrases_triple
        else:
            return map(lambda t1, t2: (t1 or []) + (t2 or []), terms_triple, phrases_triple)

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
        a, b = [int(round(math.exp(boundary * lnM))) for boundary in self.PARTITION_AT]
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
        sql += ' LIMIT 1'

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
            whereclause = 'freq BETWEEN %s AND %s' % (minfreq, maxfreq - 1)
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

    def getTermsStartingWith(self, beginning, num=10):
        terms = None

        words = beginning.split()
        if len(words) < 3:
            if beginning[-1] == ' ' or len(words) > 1:
                termid = self.getOne('term_id', term=("=", words[0]))
                if termid:
                    sql = '''SELECT "%s " || TF.term AS phrase
                             FROM TorrentBiTermPhrase P, TermFrequency TF
                             WHERE P.term1_id = ?
                             AND P.term2_id = TF.term_id ''' % words[0]
                    if len(words) > 1:
                        sql += 'AND TF.term like "%s%%" ' % words[1]
                    sql += '''GROUP BY term1_id, term2_id
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
                return filter(lambda term: not catobj.xxx_filter.isXXXTerm(term), terms)[:num]
            else:
                return terms[:num]
        else:
            return []


class UserEventLogDBHandler(BasicDBHandler):

    """
    The database handler for logging user events.
    """
    # maximum number of events to store
    # when this maximum is reached, approx. 50% of the entries are deleted.
    MAX_EVENTS = 2 * 10000

    def __init__(self):
        if UserEventLogDBHandler._single is not None:
            raise RuntimeError("UserEventLogDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'UserEventLog')

        self.count = -1

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

        if self.count == -1:
            self.count = self._db.size(self.table_name)
        else:
            self.count += 1

        if self.count > UserEventLogDBHandler.MAX_EVENTS:
            sql = \
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


class BundlerPreferenceDBHandler(BasicDBHandler):

    """
    The Bundler Preference database handler singleton for
    storing a chosen bundle method for a particular query.
    """

    def __init__(self):
        if BundlerPreferenceDBHandler._single is not None:
            raise RuntimeError("BundlerPreferenceDBHandler is singleton")
        db = SQLiteCacheDB.getInstance()
        BasicDBHandler.__init__(self, db, 'BundlerPreference')

    def storePreference(self, keywords, bundle_mode):
        query = ' '.join(sorted(set(keywords)))
        self._db.execute_write('INSERT OR REPLACE INTO BundlerPreference (query, bundle_mode) VALUES (?,?)',
                               (query, bundle_mode))

    def getPreference(self, keywords):
        # returns None if query not in db
        query = ' '.join(sorted(set(keywords)))
        return self.getOne('bundle_mode', query=query)


def doPeerSearchNames(self, dbname, kws):
    """ Get all peers that have the specified keywords in their name.
    Return a list of dictionaries. Each dict is in the NEWDBSTANDARD format.
    """
    if dbname == 'Peer':
        where = '(Peer.last_connected>0 or Peer.friend=1) and '
    elif dbname == 'Friend':
        where = ''
    else:
        raise Exception('unknown dbname: %s' % dbname)

    # Must come before query
    ranks = self.getRanks()

    for i in range(len(kws)):
        kw = kws[i]
        where += ' name like "%' + kw + '%"'
        if (i + 1) != len(kws):
            where += ' and'

    value_name = PeerDBHandler.gui_value_name

    # print >>sys.stderr,"peer_db: searchNames: sql",where
    res_list = self._db.getAll(dbname, value_name, where)
    # print >>sys.stderr,"peer_db: searchNames: res",res_list

    peer_list = []
    for item in res_list:
        # print >>sys.stderr,"peer_db: searchNames: Got Record",`item`
        peer = dict(zip(value_name, item))
        peer['name'] = dunno2unicode(peer['name'])
        peer['simRank'] = ranksfind(ranks, peer['permid'])
        peer['permid'] = str2bin(peer['permid'])
        peer_list.append(peer)
    return peer_list


def ranksfind(ranks, key):
    if ranks is None:
        return -1
    try:
        return ranks.index(key) + 1
    except:
        return -1
