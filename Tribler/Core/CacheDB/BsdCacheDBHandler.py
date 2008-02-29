# Written by Jie Yang
# see LICENSE.txt for license information

from cachedb import *
from copy import deepcopy
from sets import Set
from traceback import print_exc
from threading import currentThread
from time import time
import base64, socket

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from sets import Set

from Tribler.Core.Utilities.utilities import show_permid_shorter, validIP, validPort, validPermid, validName
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import *
from Tribler.Main.Dialogs.MugshotManager import MugshotManager # move to peerDBHandler

DEBUG = False

class BasicDBHandler:
    __single = None
    
    def __init__(self):
        self.dbs = []    # don't include read only database
        self._single = self
        
    def getInstance(*args, **kw):
        if BasicDBHandler.__single is None:
            BasicDBHandler(*args, **kw)
        return BasicDBHandler.__single
    getInstance = staticmethod(getInstance)

    def __del__(self):
        try:
            self.sync()
        except:
            # Arno: on windows it may happen that tribler_done() is called
            # before these __del__ statements. tribler_done() closes the
            # databases, so this indirect call to db._sync() will throw
            # an exception saying the database has already been closed.
            pass
            #print_exc()
        
    def close(self):
        for db in self.dbs:
            db.close()
        
    def size(self):
        return self.dbs[0]._size()

    def iteritems(self):
        return self.dbs[0]._iteritems()

    def sync(self):
        for db in self.dbs:
            db._sync()
            
    def clear(self):
        for db in self.dbs:
            db._clear()

    def printList(self):
        records = self.dbs[0]._items()
        for key, value in records:
            print key, value 

            
      
    
class SuperPeerDBHandler(BasicDBHandler):
    """
    Jelle: now superpeers are read from file and then kept in memory only.
    Necessary to pickle?
    """
    def __init__(self, config, db_dir=''):
        BasicDBHandler.__init__(self)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.peer_db]
        self.notifier = Notifier.getInstance()
        filename = os.path.join(config['install_dir'], config['superpeer_file'])
        self.superpeer_list = self.readSuperPeerList(filename)
        #print 'sp list: %s' % self.superpeer_list
        self.updatePeerDB()   
    
    __single = None    
    def getInstance(*args, **kw):
        if SuperPeerDBHandler.__single is None:
            SuperPeerDBHandler.__single = SuperPeerDBHandler(*args, **kw)
        return SuperPeerDBHandler.__single
    getInstance = staticmethod(getInstance)
      
        
    def clear(self):    # clean database
        self.superpeer_list = {}
            

    def getSuperPeers(self):
        # return only permids
        return [a['permid'] for a in self.superpeer_list]
    
    def size(self):
        return len(self.getSuperPeers())
    
    def printList(self):
        print self.getSuperPeers()
        
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
            if self.validSuperPeerList(superpeer_info):
                try:
                    ip = socket.gethostbyname(superpeer_info[0])
                    superpeer = {'ip':ip, 'port':superpeer_info[1], 
                              'permid':superpeer_info[2]}
                    if len(superpeer_info) > 3:
                        superpeer['name'] = superpeer_info[3]
                    superpeers_info.append(superpeer)
                except:
                    print_exc()
                    pass
                    
        return superpeers_info
    
    def validSuperPeerList(self, superpeer_info):
        try:
            if len(superpeer_info) < 3:
                raise RuntimeError, "one line in superpeers.txt contains at least 3 elements"
            #validIP(superpeer_info[0])
            validPort(int(superpeer_info[1]))
            validPermid(superpeer_info[2])
        except Exception:
            if DEBUG:
                print >>sys.stderr,"superpeer: Parse error reading",superpeer_info
                print_exc(file=sys.stderr)
            return False
        else:
            return True
    
    def updatePeerDB(self):
        print 'superpeers: updating db'
        for superpeer in self.superpeer_list:
            superpeer = deepcopy(superpeer)
            if not isinstance(superpeer, dict) or 'permid' not in superpeer:
                continue
            permid = superpeer.pop('permid')
            self.peer_db.updateItem(permid, superpeer)
            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid)
      
class FriendDBHandler(BasicDBHandler):

    def __init__(self, db_dir=''):
        BasicDBHandler.__init__(self)
        #self.my_db = MyDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.peer_db]
    
    __single = None    
    def getInstance(*args, **kw):
        if FriendDBHandler.__single is None:
            FriendDBHandler.__single = FriendDBHandler(*args, **kw)
        return FriendDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def size(self):
        return len(self.my_db.getFriends())

    def printList(self):
        print self.my_db.getFriends()
        
    def addFriend(self, permid):
        self.my_db.addFriend(permid)
        #self.my_db._sync()
        
    def addExternalFriend(self, friend):
        if not isinstance(friend, dict) or 'permid' not in friend:
            return
        permid = friend.pop('permid')
        if permid not in self.getFriends():
            self.peer_db.updateItem(permid, friend)
            #self.peer_db._sync()
            #self.my_db.addFriend(permid) # Fixme
            #self.my_db._sync()
        else:
            self.peer_db.updateItem(permid, friend, update_time=False)
            #self.peer_db._sync()
            
    def getFriendList(self):
        """returns a list of permids"""
        return [] # FIXME, no friendsdb yet
            
    def getFriends(self):
        """returns a list of peer infos including permid"""
        return [] # Fixme
    
    def isFriend(self, permid):
        return False # Fixme
            
    def deleteFriend(self,permid):
        pass
        
    def updateFriendIcon(self, permid, icon_path):
        self.peer_db.updatePeer(permid, 'icon', icon_path)
        
class PeerDBHandler(BasicDBHandler):
        
    def __init__(self, config, db_dir=''):
        BasicDBHandler.__init__(self)
        self.notifier = Notifier.getInstance()
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.friends_db_handler = FriendDBHandler.getInstance()
        self.pref_db_handler = PreferenceDBHandler(db_dir=db_dir)
        self.ip_db = IP2PermIDDB.getInstance(db_dir=db_dir)
        self.mm = MugshotManager.getInstance()
        self.mm.register(config)
        self.dbs = [self.peer_db, self.ip_db]
    
    __single = None    
    def getInstance(*args, **kw):
        if PeerDBHandler.__single is None:
            PeerDBHandler.__single = PeerDBHandler(*args, **kw)
        return PeerDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __len__(self):
        return self.peer_db._size()
        
    def getPeer(self, permid, default=False):
        return self.peer_db.getItem(permid, default)
        
    def getPeerSim(self, permid):
        x = self.peer_db.getItem(permid)
        if not x:
            return 0
        return x.get('similarity', 0)
        
    def getPeerList(self):    # get the list of all peers' permid
        return self.peer_db._keys()
        
    def getTasteBuddyList(self):
        return self.pref_db._keys()

    def getRandomPeerList(self):    # Expensive
        # TODO: improve performance 
        return list(Set(self.peer_db._keys()) - Set(self.pref_db._keys()))
        
    def getPeers(self, peer_list, keys):    # get a list of dictionaries given peer list
        peers = []
        if 'permid' in keys:
            permid = True
            keys.remove('permid')
        else:
            permid = False
            
        count = 0
        for peer in peer_list:
            p = self.peer_db.getItem(peer)
            if not p:
                break    # database is closed
            if permid:
                d = {'permid':peer}
            else:
                d = {}
            for key in keys:
                d[key] = p[key]
            peers.append(d)
            
            count += 1
            if count % 1000 == 0:
                print >>sys.stderr,"peerdb: Read items",count,currentThread().getName() 
        
        return peers
        
    def getPeersValue(self, peer_list, keys=None):    # get a list of values given peer list 
        if not keys:
            keys = self.peer_db.default_item.keys()
        values = []
        for peer in peer_list:
            p = self.peer_db.getItem(peer, default=True)
            if len(keys) == 1:
                values.append(p[keys[0]])
            else:
                d = []
                for key in keys:
                    d.append(p[key])
                values.append(d)
        
        return values
    
    def addPeer(self, permid, value, update_dns=True, updateFlag = True):
        
        if value.has_key('last_seen'):    # get the latest last_seen
            old_last_seen = 0
            old_data = self.getPeer(permid)
            if old_data:
                old_last_seen = old_data.get('last_seen', 0)
            last_seen = value['last_seen']
            now = int(time())
            value['last_seen'] = min(now, max(last_seen, old_last_seen))

        self.peer_db.updateItem(permid, value, update_dns)

        if value.has_key('ip') and update_dns:
            self.updatePeerIP(permid, value['ip'])
        
        if updateFlag:
            self.notifier.notify(NTFY_PEERS, NTFY_INSERT, permid)
        
    def hasPeer(self, permid):
        return self.peer_db.hasItem(permid)        

    def findPeers(self, key, value):    
        # Warning: if key is not 'permid', then it is a very EXPENSIVE operation. 
        res = []
        if key == 'permid':
            peer = self.getPeer(value)
            if peer:
                peer.update({'permid':value})
                res.append(peer)
        else:
            for permid, peer in self.peer_db._items():
                try:
                    if peer[key] == value:
                        peer.update({'permid':permid})
                        res.append(peer)
                except KeyError:
                    pass
        return res
    
    def updatePeer(self, permid, key, value, updateFlag = True):
        self.peer_db.updateItem(permid, {key:value})
        if key == 'ip':
            self.updatePeerIP(permid, value)
        if updateFlag:
            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid, key)
    
    def updatePeerIcon(self, permid, icontype, icondata, updateFlag = True):
        self.mm.save_data(permid, icontype, icondata)
        if updateFlag:
            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid, 'icon')
    
        
    def getPeerIcon(self, permid, name = ''):
        return self.mm.load_data(permid, name)
        
    def updatePeerIP(self, permid, ip):
        peer_data = self.peer_db._get(permid, {})
        old_ip = peer_data.get('ip', None)
        if not old_ip:    # not exist in peer_db, don't touch it either
            return
        
        if old_ip != ip:    # changed ip
            old_permid = self.ip_db.getPermIDByIP(old_ip)   
            if old_permid == permid:    # ip_db is consistent with peer_db
                self.ip_db.deleteItem(old_ip)    # delete the old map
        permid2 = self.ip_db.getPermIDByIP(ip)
        if permid2 != permid:
            self.ip_db.addIP(ip,permid)
        
        
    def deletePeer(self, permid, updateFlag = True):
        if self.friends_db_handler.isFriend(permid):
            return False
        self.peer_db._delete(permid)
        self.pref_db_handler.deletePeer(permid)
        self.ip_db.deletePermID(permid)
        
        if updateFlag:
            self.notifier.notify(NTFY_PEERS, NTFY_DELETE, permid)

        return True
        
    def updateTimes(self, permid, key, change, updateFlag = True):
        item = self.peer_db.getItem(permid)
        if not item:
            return
        if not item.has_key(key):
            value = 0
        else:
            value = item[key]
        value += change
        self.peer_db.updateItem(permid, {key:value})
        
        if updateFlag:
            self.notifier.notify(NTFY_PEERS, NTFY_UPDATE, permid, key)
        
    def getPermIDByIP(self,ip):
        return self.ip_db.getPermIDByIP(ip)    
        
class PreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        BasicDBHandler.__init__(self)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.dbs = [self.pref_db, self.owner_db]
        
    __single = None    
    def getInstance(*args, **kw):
        if PreferenceDBHandler.__single is None:
            PreferenceDBHandler.__single = PreferenceDBHandler(*args, **kw)
        return PreferenceDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def getPreferences(self, permid):
        return self.pref_db.getItem(permid)
        
    def getPrefList(self, permid):
        return self.pref_db._get(permid,{}).keys()
    
    def addPreference(self, permid, infohash, data={}):
        self.pref_db.addPreference(permid, infohash, data)
        self.owner_db.addOwner(infohash, permid)

    def deletePeer(self, permid):   # delete a peer from pref_db
        prefs = self.pref_db.getItem(permid)
        for infohash in prefs:
            self.owner_db.deleteOwner(infohash, permid)
        self.pref_db.deleteItem(permid)

    def deletePreference(self, permid, infohash):
        self.pref_db.deletePreference(permid, infohash)
        self.owner_db.deleteOwner(infohash, permid)
        
    def hasPreference(self, permid):
        return self.pref_db._has_key(permid)
        
    def getNumPrefs(self, permid):
        if not self.pref_db._has_key(permid):
            return 0
        x = self.pref_db.getItem(permid)
        return len(x)
        
class TorrentDBHandler(BasicDBHandler):

    def __init__(self, db_dir=''):
        BasicDBHandler.__init__(self)
        self.notifier = Notifier.getInstance()
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.torrent_db]
        
    __single = None    
    def getInstance(*args, **kw):
        if TorrentDBHandler.__single is None:
            TorrentDBHandler.__single = TorrentDBHandler(*args, **kw)
        return TorrentDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def addTorrent(self, infohash, torrent={}, new_metadata=False, updateFlag = True):
        # add a new torrent or update an old torrent's info
        if not torrent and self.hasTorrent(infohash):    # no need to add
            return False
        self.torrent_db.updateItem(infohash, torrent)

        if updateFlag:
            self.notifier.notify(NTFY_TORRENTS, NTFY_INSERT, infohash)
            
        try:
            # Arno: PARANOID SYNC
            self.sync()
        except:
            print_exc()
        return True
        
    def updateTorrent(self, infohash, **kw):    # watch the schema of database
        updateFlag = kw.get('updateFlag', True)
        if kw.has_key('updateFlag'):
            del kw['updateFlag']
        self.torrent_db.updateItem(infohash, kw)
          
        if updateFlag:
            self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash, kw.keys())
            
        
    def deleteTorrent(self, infohash, delete_file=False, updateFlag = True):
        if self.mypref_db.hasPreference(infohash):  # don't remove torrents in my pref
            return False

        if delete_file:
#            data = self.torrent_db._get(infohash)
#            if data and data['torrent_name']:
#                live = data.get('status', 'unknown')
#                if live != 'dead' and live != 'unknown':
            deleted = self.eraseTorrentFile(infohash)
#            if deleted:
#                # may remove dead torrents, so this number is not consistent
#                self.torrent_db.num_metadatalive -= 1    
        else:
            deleted = True
        
        if deleted:
            self.torrent_db._delete(infohash)
            if updateFlag:
                self.notifier.notify(NTFY_TORRENTS, NTFY_DELETE, infohash)
                
        return deleted
            
    def eraseTorrentFile(self, infohash):
        data = self.torrent_db._get(infohash)
        if not data or not data['torrent_name'] or not data['info']:
            return False
        src = os.path.join(data['torrent_dir'], data['torrent_name'])
        if not os.path.exists(src):    # already removed
            return True
        
        try:
            os.remove(src)
        except Exception, msg:
            print >> sys.stderr, "cachedbhandler: failed to erase torrent", src, Exception, msg
            return False
        
        return True
                
    def getTorrent(self, infohash, num_owners=False,savemem=False):
        torrent = self.torrent_db.getItem(infohash,savemem=savemem)
        if torrent and num_owners:
            torrent['num_owners'] = self.owner_db.getNumOwners(infohash)
        return torrent
        
    def getTorrents(self, torrent_list, keys=None):    # get a list of dictionaries given torrent list
        if not keys:
            keys = self.torrent_db.default_item.keys()
            keys += ['infohash']
        torrents = []
        if 'infohash' in keys:
            infohash = True
            keys.remove('infohash')
        else:
            infohash = False
        if 'num_owners' in keys:
            num_owners = True
        else:
            num_owners = False
        for torrent in torrent_list:
            p = self.torrent_db.getItem(torrent, default=True)
            if num_owners:
                p['num_owners'] = self.owner_db.getNumOwners(torrent)
            if infohash:
                p['infohash'] = torrent
            torrents.append(p)
        return torrents
        
    def getAllTorrents(self):
        return self.torrent_db._keys()
        
        
    def getRecommendedTorrents(self, light=True, all=False, myprefs=False, countcallback=None):     
        """ get torrents on disk but not in my pref
           BE AWARE: the returned object of this call may consume lots of memory.
           You should delete the object when possible
        """
        
        #print '>>>>>>'*5, "getRecommendedTorrents", currentThread().getName()
        #print_stack()
        #loaded by DataLoadingThread
        
        start_time = time()
        mypref_set = Set(self.mypref_db._keys())

        if myprefs:
            all_list = mypref_set
        else:
            if all:
                all_list = self.torrent_db._keys()
            else:
                all_list = Set(self.torrent_db._keys()) - mypref_set
            

        # Arno: save memory by reusing dict keys
        key_infohash = 'infohash'
        key_myDownloadHistory = 'myDownloadHistory'
        key_download_started = 'download_started'
        key_num_owners = 'key_num_owners'
        
        torrents = []
        count = 0
#        num_live_torrents = 0 
        setOfInfohashes = Set()
        for torrent in all_list:
            if torrent in setOfInfohashes: # do not add 2 torrents with same infohash
                continue
            p = self.torrent_db.getItem(torrent,savemem=True)
            if not p:
                break #database not available any more
            if not type(p) == dict or not p.get('torrent_name', None) or not p.get('info', None):
                deleted = self.deleteTorrent(torrent)     # remove infohashes without torrent
                print >> sys.stderr, "TorrentDBHandler: deleted empty torrent", deleted, p.get('torrent_name', None), p.get('info', None)
            
#            if torrent not in mypref_set:
#                live = p.get('status', 'unknown')
#                if live != 'dead' and live != 'unknown':
#                    num_live_torrents += 1
                    
            if torrent in mypref_set:
                p[key_myDownloadHistory] = True
                mypref_obj = self.mypref_db.getItem(torrent)
                if mypref_obj:
                    p[key_download_started] = mypref_obj['created_time']
                    
            p[key_infohash] = torrent
            setOfInfohashes.add(torrent)
            if not light:    # set light as ture to be faster
                p[key_num_owners] = self.owner_db.getNumOwners(torrent)
                
            torrents.append(p)
            
            count += 1
            if count % 1000 == 0:
                print >>sys.stderr,"torrentdb: Read items",count,currentThread().getName()
                if countcallback is not None:
                    countcallback(count)
            
        del all_list
        del setOfInfohashes
        
#        from traceback import print_stack
#        print_stack()
#        print >> sys.stderr, '[StartUpDebug]----------- from getRecommendedTorrents ----------', time()-start_time, currentThread().getName(), '\n\n'
        
#        self.torrent_db.num_metadatalive = num_live_torrents
        #print 'Returning %d torrents' % len(torrents)
        
        return torrents
        
        
        
    def getCollectedTorrentHashes(self): 
        """ get infohashes of torrents on disk, used by torrent checking, 
            and metadata handler
        """
        all_list = Set(self.torrent_db._keys())
        all_list -= Set(self.mypref_db._keys())

        return all_list
    
    def hasTorrent(self, infohash):
        return self.torrent_db._has_key(infohash)
    
    def getLiveTorrents(self, peerlist):
        ret = []
        for infohash in peerlist:
            data = self.torrent_db._get(infohash)
            if isinstance(data, dict):
                live = data.get('status', 'unknown')
                if live != 'dead':
                    ret.append(infohash)
        return ret
    
    def getOthersTorrentList(self, num=-1, sorted=True):    # get the list of torrents which are not in my preference
        all_list = list(Set(self.torrent_db._keys()) - Set(self.mypref_db._keys()))
        if num < 0:
            return all_list
        if not sorted:        #TODO: seperate sort function from getOthersTorrentList
            return all_list
        values = []
        for torrent in all_list:
            t = self.torrent_db.getItem(torrent, default=True)
            values.append(t['relevance'])
        nlist = len(all_list)
        aux = [(values[i], i) for i in xrange(nlist)]
        aux.sort()
        aux.reverse()
        return [all_list[i] for k, i in aux[:num]]
            
    def getTorrentsValue(self, torrent_list, keys=None):    # get a list of values given peer list 
        if not keys:
            keys = self.torrent_db.default_item.keys()
        if not isinstance(keys, list):
            keys = [str(keys)]
        values = []
        for torrent in torrent_list:
            t = self.torrent_db.getItem(torrent, default=True)
            if len(keys) == 1:
                values.append(t[keys[0]])
            else:
                d = []
                for key in keys:
                    d.append(t[key])
                values.append(d)
        
        return values
        
    def getNoMetaTorrents(self):    # get the list of torrents which only have an infohash without the metadata
        def hasNoTorrentFile(key):
            data = self.torrent_db._get(key)
            if not data:    # if no record, ignore
                return False
            if not data['torrent_name'] or not data['info']:    # if no info, selected
                return True
            return False    # if has info but no file, it means the torrent file has been removed. ignore
        
        all_keys = self.torrent_db._keys()
        no_metadata_list = filter(hasNoTorrentFile, all_keys)
        return no_metadata_list
        
    def hasMetaData(self, infohash):
        value = self.torrent_db._get(infohash)
        if not value:
            return False
        name = value.get('torrent_name', None)
        if not name:
            return False
        return True
            
    def getOwners(self, infohash):
        return self.owner_db.getItem(infohash)
        
    def updateTorrentRelevance(self, infohash, relevance, updateFlag = True):
        self.torrent_db.updateItem(infohash, {'relevance':relevance})
        if updateFlag:
            self.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash, 'relevance')
            
#===============================================================================
#    def getNumMetadataAndLive(self):    # TODO
#        return self.torrent_db.num_metadatalive
#===============================================================================
    
class MyPreferenceDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        BasicDBHandler.__init__(self)
        self.notifier = Notifier.getInstance()
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.dbs = [self.mypref_db, self.torrent_db]
    
    __single = None    
    def getInstance(*args, **kw):
        if MyPreferenceDBHandler.__single is None:
            MyPreferenceDBHandler.__single = MyPreferenceDBHandler(*args, **kw)
        return MyPreferenceDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def getPreferences(self, key=None):
        all_items = self.mypref_db._items()
        if key is None:
            ret = []
            for item in all_items:
                item[1].update({'infohash':item[0]})
                ret.append(item[1])
            return ret
        else:
            return [all_items[i][1][key] for i in xrange(len(all_items))]
            
    def getPrefList(self):
        return self.mypref_db._keys()
        
    def getCreationTime(self, infohash):
        "Return creation time. Used for sorting in library view"
        item = self.mypref_db.getItem(infohash, default=False)
        if item:
            return item.get('created_time')
        else:
            return None
        
    def getPrefs(self, pref_list, keys):    # get a list of dictionaries given peer list
        peers = []
        for torrent in pref_list:
            d = self.mypref_db.getItem(torrent, default=True)
            t = self.torrent_db.getItem(torrent, default=True)
            try:
                d.update(t)
            except:
                continue
            if 'infohash' in keys:
                d.update({'infohash':torrent})
            for key in d.keys():
                if key not in keys:
                    d.pop(key)
            peers.append(d)
        
        return peers
        
    def removeFakeAndDeadTorrents(self, items):
        def fakeFilter(item):
            infohash = item[0] # infohash
            valid = self.mypref_db.getRank(infohash) >= 0
            torrentdata = self.torrent_db.getItem(infohash, default=True) # defaulttorrent has status 'unknown'
            alive = torrentdata.get('status', 'unknown') != 'dead'
            secret = torrentdata.get('secret', False) # exclude secret downloads.
            return alive and valid and not secret
        return filter(fakeFilter, items)
    
            
    def getRecentPrefList(self, num=0):    # num = 0: all files
        all_items = self.mypref_db._items()
        valid_items = self.removeFakeAndDeadTorrents(all_items)
        prefs = [(item[1]['last_seen'], item[0]) for item in valid_items]
        prefs.sort()
        prefs.reverse()
        if num > 0:
            return [item[1] for item in prefs[:num]]
        else:
            return [item[1] for item in prefs]

    def hasPreference(self, infohash):
        return self.mypref_db._has_key(infohash)
            
    def addPreference(self, infohash, data={}):
        if not data and self.hasPreference(infohash):
            return False
        self.mypref_db.updateItem(infohash, data)
        return True

    def deletePreference(self, infohash):
        self.mypref_db.deleteItem(infohash)
        
    def updateRank(self, infohash, rank):
        self.mypref_db.updateItem(infohash, {'rank':rank})
        self.sync()


class OwnerDBHandler(BasicDBHandler):
    
    def __init__(self, db_dir=''):
        BasicDBHandler.__init__(self)
        self.owner_db = OwnerDB.getInstance(db_dir=db_dir)
        self.pref_db = PreferenceDB.getInstance(db_dir=db_dir)
        self.mypref_db = MyPreferenceDB.getInstance(db_dir=db_dir)
        self.torrent_db = TorrentDB.getInstance(db_dir=db_dir)
        self.dbs = [self.owner_db]
        self.sim_cache = {}    # used to cache the getSimItems
        
    __single = None    
    def getInstance(*args, **kw):
        if OwnerDBHandler.__single is None:
            OwnerDBHandler.__single = OwnerDBHandler(*args, **kw)
        return OwnerDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def getTorrents(self):
        return self.owner_db._keys()
        
    def getSimItems(self, torrent_hash, num=15):
        """ Get a list of similar torrents given a torrent hash. The torrents
        must exist and be not dead.
        Input
           torrent_hash: the infohash of a torrent
           num: the number of similar torrents to get
        output: 
           returns a list of infohashes, sorted by similarity,
        """

        start = time()
        mypref_list = self.mypref_db._keys()
        if torrent_hash in self.sim_cache:
            mypref_set = Set(mypref_list)
            oldrec = self.sim_cache[torrent_hash]
            for item in oldrec[:]:    # remove common torrents
                if item in mypref_set:
                    oldrec.remove(item)
            return oldrec
        
        owners = self.owner_db._get(torrent_hash, {})
        nowners = len(owners)
        if not owners or nowners < 1:
            return []
        co_torrents = {}    # torrents have co
        for owner in owners:
            prefs = self.pref_db.getItem(owner)
            for torrent in prefs:
                if torrent not in co_torrents:
                    co_torrents[torrent] = 1
                else:
                    co_torrents[torrent] += 1
        if torrent_hash in co_torrents:
            co_torrents.pop(torrent_hash)
        for infohash in mypref_list:
            if infohash in co_torrents:
                co_torrents.pop(infohash)
        
        sim_items = []
        
        for torrent in co_torrents:
            co = co_torrents[torrent]
#            if co <= 1:
#                continue
            
            # check if the torrent is collected and live
            has_key = self.torrent_db._has_key(torrent)
            if has_key == False:
                continue
            elif has_key == None:
                break
            value = self.torrent_db._get(torrent)
            if not value:    # sth. is wrong
                print >> sys.stderr, "cachedbhandler: getSimItems meets error in getting data"
                break
            info = value.get('info', {})
            name = info.get('name', None)
            if not name:
                continue
            live = value.get('status', 'unknown')
            if live == 'dead':
                continue
            
            nowners2 = self.owner_db.getNumOwners(torrent)
            if nowners2 == 0:    # sth. is wrong
                continue
            sim = co/(nowners*nowners2)**0.5
            sim_items.append((sim, torrent))
            
        sim_items.sort()
        sim_items.reverse()
        sim_torrents = [torrent for sim, torrent in sim_items[:num]]
        
        self.sim_cache[torrent_hash] = sim_torrents
        return sim_torrents
        
        
        
class BarterCastDBHandler(BasicDBHandler):

    def __init__(self, session, db_dir=''):
        BasicDBHandler.__init__(self)
        self.bartercast_db = BarterCastDB.getInstance(db_dir=db_dir)
        self.peer_db = PeerDB.getInstance(db_dir=db_dir)
        self.dbs = [self.bartercast_db]
        self.my_permid = session.get_permid()

    __single = None
    def getInstance(*args, **kw):
        if BarterCastDBHandler.__single is None:
            BarterCastDBHandler.__single = BarterCastDBHandler(*args, **kw)
        return BarterCastDBHandler.__single
    getInstance = staticmethod(getInstance)
    
    def __len__(self):
        return self.bartercast_db._size()

    def getName(self, permid):

        if permid == 'testpermid_1':
            return "Test_1"
        elif permid == 'testpermid_2':
            return "Test_2"
        elif permid == 'non-tribler':
            return "Non-tribler"

        peer = self.peer_db.getItem(permid, False)
        if peer == None:
            return 'peer %s' % show_permid_shorter(permid) 
        else:
            name = peer.get('name', '')
            if name == '':
                name = 'peer %s' % show_permid_shorter(permid)
            return name

    def getItem(self, (permid_1, permid_2), default=False):

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            reverse = True
            permid_from = permid_2
            permid_to = permid_1
        else:
            reverse = False
            permid_from = permid_1
            permid_to = permid_2

        item = self.bartercast_db.getItem((permid_from, permid_to), default)

        # if peer in peerdb but not in bartercastdb: add peer
        if item == None: # and peerdb_peer != None:

            if DEBUG:
                print 'Item (%s, %s) added to BarterCastDB' % (self.getName(permid_from), self.getName(permid_to))
            
            self.addItem((permid_from, permid_to), self.bartercast_db.default_item)

            # get item again now it exists
            item = self.bartercast_db.getItem((permid_from, permid_to), default)

        # if reverse: exchange up and down so that the caller doesnt have to worry
        # about the order of permids in the tuple
        if reverse:
            down = item['downloaded']
            up = item['uploaded']
            item['downloaded'] = up
            item['uploaded'] = down

        return item


    def getItemList(self):    # get the list of all peers' permid
        keys = map(lambda key: bdecode(key), self.bartercast_db._keys())
        return keys

    # Return (sorted) list of the top N peers with the highest (combined) values for the given keys    
    def getTopNPeers(self, n, local_only = False):
        n = max(1, n)
        itemlist = self.getItemList()

        if local_only:
            # get only items of my local dealings
            itemlist = filter(lambda (permid_from, permid_to): permid_to == self.my_permid or permid_from == self.my_permid, itemlist)
            
        total_up = {}
        total_down = {}
        
        
        for (permid_1, permid_2) in itemlist:
            
            item = self.getItem((permid_1, permid_2))
            
            up = item['uploaded'] *1024 # make into bytes
            down = item['downloaded'] *1024

            if DEBUG:
                print "BarterCast DB entry: (%s, %s) up = %d down = %d" % (self.getName(permid_1), self.getName(permid_2), up, down)
            
            # process permid_1
            total_up[permid_1] = total_up.get(permid_1, 0) + up
            total_down[permid_1] = total_down.get(permid_1, 0) + down
            
            # process permid_2
            total_up[permid_2] = total_up.get(permid_2, 0) + down
            total_down[permid_2] = total_down.get(permid_2, 0) +  up
            
        
        # create top N peers
        top = []
        min = 0
        
        for peer in total_up.keys():

            up = total_up[peer]
            down = total_down[peer]
            
            if DEBUG:
                print "BarterCast: total of %s: up = %d down = %d" % (self.getName(peer), up, down)
            
            # we know rank on total upload?
            value = up

            # check if peer belongs to current top N
            if peer != 'non-tribler' and peer != self.my_permid and (len(top) < n or value > min):

                top.append((peer, up, down))

                # sort based on value
                top.sort(cmp = lambda (p1, u1, d1), (p2, u2, d2): cmp(u2, u1))

                # if list contains more than N elements: remove the last (=lowest value)
                if len(top) > n:
                    del top[-1]
                    
                # determine new minimum of values    
                min = top[-1][1]


        
        result = {}
        
        result['top'] = top
        
        # My total up and download, including interaction with non-tribler peers
        result['total_up'] = total_up.get(self.my_permid, 0)
        result['total_down'] = total_down.get(self.my_permid, 0)
        
        # My up and download with tribler peers only
        result['tribler_up'] = result['total_up'] - total_down.get('non-tribler', 0)
        result['tribler_down'] = result['total_down'] - total_up.get('non-tribler', 0)
        
        return result

    def addItem(self, (permid_1, permid_2), item):

#        if value.has_key('last_seen'):    # get the latest last_seen
#            old_last_seen = 0
#            old_data = self.getPeer(permid)
#            if old_data:
#                old_last_seen = old_data.get('last_seen', 0)
#            last_seen = value['last_seen']
#            value['last_seen'] = max(last_seen, old_last_seen)

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            reverse = True
            permid_from = permid_2
            permid_to = permid_1
        else:
            reverse = False
            permid_from = permid_1
            permid_to = permid_2

        # if reverse: exchange up and down
        if reverse:
            down = item['downloaded']
            up = item['uploaded']
            item['downloaded'] = up
            item['uploaded'] = down

        self.bartercast_db.updateItem((permid_from, permid_to), item)


    def hasItem(self, (permid_1, permid_2)):

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            reverse = True
            permid_from = permid_2
            permid_to = permid_1
        else:
            reverse = False
            permid_from = permid_1
            permid_to = permid_2

        item = self.bartercast_db.hasItem((permid_from, permid_to))        

        if reverse:
            down = item['downloaded']
            up = item['uploaded']
            item['downloaded'] = up
            item['uploaded'] = down

        return item


    def updateItem(self, (permid_1, permid_2), key, value):

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            permid_from = permid_2
            permid_to = permid_1
            if key == 'uploaded':
                key = 'downloaded'
            elif key == 'downloaded':
                key = 'uploaded'
        else:
            permid_from = permid_1
            permid_to = permid_2

        if DEBUG:
            print "BarterCast: update (%s, %s) [%s] += %s" % (self.getName(permid_from), self.getName(permid_to), key, str(value))

        self.bartercast_db.updateItem((permid_from, permid_to), {key:value})


    def incrementItem(self, (permid_1, permid_2), key, value):

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            permid_from = permid_2
            permid_to = permid_1
            if key == 'uploaded':
                key = 'downloaded'
            elif key == 'downloaded':
                key = 'uploaded'
        else:
            permid_from = permid_1
            permid_to = permid_2

        if DEBUG:
            print "BarterCast: increment (%s, %s) [%s] += %s" % (self.getName(permid_from), self.getName(permid_to), key, str(value))

        item = self.getItem((permid_from, permid_to))

        if key in item.keys():
            old_value = item[key]
            new_value = old_value + value
            self.bartercast_db.updateItem((permid_from, permid_to), {key:new_value})
            return new_value

        return None


    # TODO: include this functionality in PeerDB?
    def deleteItem(self, (permid_1, permid_2)):

        # in the database, permid-tuple is always sorted
        # to ensure unique entries for each permid combination
        if permid_1 > permid_2:
            permid_from = permid_2
            permid_to = permid_1
        else:
            permid_from = permid_1
            permid_to = permid_2

        self.bartercast_db._delete((permid_from, permid_to))

        return True


        

    
def test_myprefDB():
    myprefdb = MyPreferenceDBHandler.getInstance()
    print myprefdb.getRecentPrefList()
    
def test_all():
    test_myprefDB()
    
def test_getSimItems(db_dir):
    owner_db = OwnerDBHandler(db_dir)
    torrent_db = TorrentDBHandler(db_dir)
    torrents = owner_db.getTorrents()
    for torrent in torrents:
        value = torrent_db.getTorrent(torrent)
        if not value:
                continue
        info = value.get('info', {})
        name = info.get('name', None)
        if not name:
            continue
        live = value.get('status', 'unknown')
        if live == 'dead':
            continue
        start = time()
        simtorrents = owner_db.getSimItems(torrent)
        if len(simtorrents) > 0:
            try:
                print "------", name, "------"
            except:
                print "------", `name`, "------"
        for infohash, torrent_name, sim in simtorrents:
            print "  ",
            try:
                print torrent_name, sim, time()-start
            except:
                print `torrent_name`
    
if __name__ == '__main__':
    db_dir = sys.argv[1]
    test_getSimItems(db_dir)

    
