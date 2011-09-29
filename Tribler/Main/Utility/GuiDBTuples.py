#Niels: getValidArgs based on http://stackoverflow.com/questions/196960/can-you-list-the-keyword-arguments-a-python-function-receives
import sys
import os.path
from inspect import getargspec
from Tribler.Video.utils import videoextdefaults
from Tribler.Main.vwxGUI import VLC_SUPPORTED_SUBTITLES
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED
from Tribler.Main.vwxGUI.IconsManager import data2wxBitmap, IconsManager, SMALL_ICON_MAX_DIM
from Tribler.community.channel.community import ChannelCommunity

def getValidArgs(func, argsDict):
    args, _, _, defaults = getargspec(func)
    try:
        args.remove('self')
    except:
        pass
    
    argsDict = dict((key, value) for key, value in argsDict.iteritems() if key in args)
    if defaults:
        args = args[:-len(defaults)]
        
    notOk = set(args).difference(argsDict)
    if notOk:
        print >> sys.stderr, "Missing",notOk,"arguments for",func 
    return argsDict

#Niels: from http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize

def cache(func):
    def _get(self):
        key = func.__name__
        try:
            return self._cache[key]
        except AttributeError:
            self._cache = {}
            x = self._cache[key] = func(self)
            return x
        except KeyError:
            x = self._cache[key] = func(self)
            return x
    return _get

def cacheProperty(func):
    
    def _get(self):
        key = func.__name__
        try:
            return self._cache[key]
        
        except AttributeError:
            self._cache = {}
            x = self._cache[key] = func(self)
            return x
        
        except KeyError:
            x = self._cache[key] = func(self)
            return x
        return func(self)
    
    def _del(self):
        key = func.__name__
        try:
            del self._cache[key]
        except:
            pass
    return property(_get, None, _del)

class Helper(object):
    __slots__ = ('_cache')
    def get(self, key, default = None):
        return getattr(self, key, default)
    
    def __contains__(self, key):
        return key in self.__slots__
    
    def __eq__(self, other):
        if other:
            return self.id == other.id
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __getstate__(self):
        statedict = {}
        for key in self.__slots__:
            statedict[key] = getattr(self, key, None)
        return statedict
    
    def __setstate__(self, statedict):
        for key, value in statedict.iteritems():
            setattr(self, key, value)

class Torrent(Helper):
    __slots__ = ('_torrent_id', 'infohash', 'name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers' ,'_channel', 'torrent_db', 'channelcast_db', 'ds', 'progress')
    def __init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, channel):
        self._torrent_id = torrent_id
        self.infohash = infohash
        self.name = name
        self.length = length
        self.category_id = category_id
        self.status_id = status_id
        
        self.num_seeders = num_seeders or 0
        self.num_leechers = num_leechers or 0
        
        self._channel = channel
             
        self.torrent_db = None
        self.channelcast_db = None
        self.ds = None
   
    @cacheProperty
    def categories(self):
        if self.category_id:
            return [self.torrent_db.id2category[self.category_id]]
    
    @cacheProperty
    def status(self):
        if self.status_id:
            return self.torrent_db.id2status[self.status_id]
    
    @cacheProperty
    def torrent_id(self):
        if not self._torrent_id:
            self._torrent_id = self.torrent_db.getTorrentID(self.infohash)
        return self._torrent_id
    
    @cacheProperty
    def channel(self):
        if self._channel is not None:
            return self._channel
        
        channel = self.channelcast_db.getMostPopularChannelFromTorrent(self.infohash)
        if channel:
            return Channel(*channel)
        return False
    
    def updateChannel(self, c):
        self._channel = c
        try:
            del self._cache['channel']
        except:
            pass
    
    def hasChannel(self):
        return self.channel
    
    @property
    def state(self):
        if self.ds:
            if self.ds.progress == 1.0:
                return 'completed'
            
            if self.ds.get_status() == DLSTATUS_DOWNLOADING:
                return 'active'
            
            if self.ds.get_status() == DLSTATUS_STOPPED:
                return 'stopped'
            
    def __eq__(self, other):
        return self.infohash == other.infohash
    
    def __str__(self):
        return self.name
    
    def __getstate__(self):
        statedict = {}
        for key in Torrent.__slots__:
            if key not in ['ds', 'channelcast_db', 'torrent_db']:
                statedict[key] = getattr(self, key, None)
        return statedict
    
class RemoteTorrent(Torrent):
    __slots__ = ('query_permids')
    def __init__(self, torrent_id, infohash, name, length = 0, category_id = None, status_id = None, num_seeders = 0, num_leechers = 0, query_permids = [], channel_id = -1, channel_permid = -1, channel_name = '', subscriptions = 0, neg_votes = 0):
        if channel_name != "":
            c = RemoteChannel(channel_id, channel_permid, channel_name, subscriptions, neg_votes)
        else:
            c = False
        Torrent.__init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, c)
        
        self.query_permids = query_permids

class CollectedTorrent(Helper):
    __slots__ = ('comment', 'trackers', 'creation_date', 'files', 'last_check', 'torrent')
    def __init__(self, torrent, torrentdef):
        self.torrent = torrent
        
        self.comment = torrentdef.get_comment_as_unicode()
        if torrentdef.get_tracker_hierarchy():
            self.trackers = torrentdef.get_tracker_hierarchy()
        else:
            self.trackers = [[torrentdef.get_tracker()]]
        self.creation_date = torrentdef.get_creation_date()
        self.files = torrentdef.get_files_as_unicode_with_length()
        self.last_check = -1

    def __getattr__(self, name):
        try:
            Helper.__getattr__(self, name)
        except:
            return getattr(self.torrent, name)
    
    def __setattr__(self, name, value):
        try:
            Helper.__setattr__(self, name, value)
        except:
            setattr(self.torrent, name, value)
    
    @cacheProperty
    def swarminfo(self):
        swarminfo = self.torrent_db.getSwarmInfo(self.torrent_id)
        
        if swarminfo:
            self.torrent.num_seeders = swarminfo[1] or 0
            self.torrent.num_leechers = swarminfo[2] or 0
            self.last_check = swarminfo[4] or -1
        return swarminfo
    
    @cacheProperty
    def videofiles(self):
        videofiles = []
        for filename, _ in self.files:
            _, ext = os.path.splitext(filename)
            if ext.startswith('.'):
                ext = ext[1:] 
            
            if ext in videoextdefaults:
                videofiles.append(filename)
        return videofiles
    
    @cacheProperty
    def largestvideofile(self):
        _, filename = max([(size, filename) for filename, size in self.files if filename in self.videofiles])
        return filename
    
    @cacheProperty
    def subtitlefiles(self):
        subtitles = []
        for filename, length in self.files:
            prefix, ext = os.path.splitext(filename)
            if ext.startswith('.'):
                ext = ext[1:]
            if ext in VLC_SUPPORTED_SUBTITLES:
                subtitles.append(filename)
        return subtitles
    
    @cache
    def isPlayable(self):
        return len(self.videofiles) > 0
    
class NotCollectedTorrent(CollectedTorrent):
    def __init__(self, torrent, files, trackers):
        self.torrent = torrent
        self.comment = None
        self.trackers = trackers
        self.creation_date = -1
        self.files = files
        self.last_check = -1
        
class LibraryTorrent(Torrent):
    __slots__ = ()
    def __init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, progress):
        Torrent.__init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, None)
        self.progress = progress
    
class ChannelTorrent(Torrent):
    __slots__ = ('channeltorrent_id', 'dispersy_id', 'colt_name', 'chant_name', 'description', 'time_stamp', 'inserted', 'playlist')
    def __init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, channeltorrent_id, dispersy_id, chant_name, colt_name, description, time_stamp, inserted, channel, playlist):
        Torrent.__init__(self, torrent_id, infohash, name, length, category_id, status_id, num_seeders, num_leechers, channel)
        
        self.channeltorrent_id = channeltorrent_id
        self.dispersy_id = dispersy_id
        self.colt_name = colt_name
        self.chant_name = chant_name
        self.description = description
        self.time_stamp = time_stamp
        self.inserted = inserted
        self.playlist = playlist
        
    @property
    def name(self):
        return self.chant_name or self.colt_name
    
    @name.setter
    def name(self, name):
        pass
    
    def __getstate__(self):
        statedict = Torrent.__getstate__(self)
        for key in self.__slots__:
            statedict[key] = getattr(self, key, None)
        return statedict
    
class Channel(Helper):
    __slots__ = ('id', 'dispersy_cid', 'name', 'description', 'nr_torrents', 'nr_favorites', 'nr_spam', 'my_vote', 'modified', 'my_channel')
    def __init__(self, id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified, my_channel):
        self.id = id
        self.dispersy_cid = str(dispersy_cid)
        
        self.name = name[:40]
        self.description = description[:1024]
        
        self.nr_torrents = nr_torrents
        self.nr_favorites = nr_favorites
        self.nr_spam = nr_spam
        self.my_vote = my_vote
        self.modified = modified
        self.my_channel = my_channel
    
    def isDispersy(self):
        return len(self.dispersy_cid) == 20
    
    def isFavorite(self):
        return self.my_vote == 2
    
    def isSpam(self):
        return self.my_vote == -1
    
    def isMyChannel(self):
        return self.my_channel
    
    def isEmpty(self):
        return self.nr_torrents == 0
    
    @cache
    def getState(self):
        if self.isDispersy():
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelSearchGridManager
            
            searchManager = ChannelSearchGridManager.getInstance()
            return searchManager.getChannelStateByCID(self.dispersy_cid)
        
        return ChannelCommunity.CHANNEL_CLOSED, self.isMyChannel()
    
    def refreshState(self):
        try:
            del self._cache['getState']
        except:
            pass
        return self.getState()

class RemoteChannel(Channel):
    __slots__ = ('permid', 'torrents')
    def __init__(self, id, permid, name, subscriptions, neg_votes):
        Channel.__init__(self, id, '-1', name, '', 0, subscriptions, neg_votes, 0, 0, False)
        self.permid = permid
        
    def getState(self):
        return ChannelCommunity.CHANNEL_CLOSED, False
    
    def addTorrent(self, torrent):
        torrents = getattr(self, 'torrent', set())
        torrents.add(torrent)
        self.torrents = torrents
        
    def getTorrent(self, infohash):
        torrents = getattr(self, 'torrent', set())
        for torrent in torrents:
            if torrent.infohash == infohash:
                return torrent
        
class Comment(Helper):
    __slots__ = ('id', 'dispersy_id', 'channeltorrent_id', '_name', 'peer_id', 'comment', 'inserted', 'time_stamp', 'playlist', '_torrent', 'channel', 'get_nickname', 'get_mugshot')
    def __init__(self, id, dispersy_id, channeltorrent_id, name, peer_id, comment, inserted, time_stamp, channel, playlist, torrent):
        self.id = id
        self.dispersy_id = dispersy_id
        self.channeltorrent_id = channeltorrent_id
        
        self._name = name
        self.peer_id = peer_id
        self.comment = comment
        self.inserted = inserted
        self.time_stamp = time_stamp
        
        self.playlist = playlist
        self._torrent = torrent
        self.channel = channel
        
    @cacheProperty
    def name(self):
        if self.peer_id == None:
            return self.get_nickname()
        if not self._name:
            return 'Peer %d'%self.peer_id
        return self._name
    
    @cacheProperty
    def avantar(self):
        im = IconsManager.getInstance()
        
        if self.peer_id == None:
            mime, data = self.get_mugshot()
            if data:
                data = data2wxBitmap(mime, data, SMALL_ICON_MAX_DIM)
        else:
            data = im.load_wxBitmapByPeerId(self.peer_id, SMALL_ICON_MAX_DIM)

        if data is None:
            data = im.get_default('PEER_THUMB',SMALL_ICON_MAX_DIM)
        return data
    
    @cacheProperty
    def torrent(self):
        if self._torrent is not None:
            return self._torrent
        
        if self.channeltorrent_id:
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelSearchGridManager
            
            searchManager = ChannelSearchGridManager.getInstance()
            return searchManager.getTorrentFromChannelTorrentId(self.channel, self.channeltorrent_id)
    
class Playlist(Helper):
    __slots__ = ('id', 'channel_id', 'name', 'description', 'nr_torrents', 'channel')
    def __init__(self, id, channel_id, name, description, nr_torrents, channel):
        self.id = id
        self.channel_id = channel_id
        self.name = name
        self.description = description
        self.nr_torrents = nr_torrents
        
        self.channel = channel
        
    @cacheProperty
    def extended_description(self):
        if self.description:
            return self.description
        
        from Tribler.Main.vwxGUI.SearchGridManager import ChannelSearchGridManager
        
        #No description, get swarmnames
        searchManager = ChannelSearchGridManager.getInstance()
        _,_, torrents =  searchManager.getTorrentsFromPlaylist(self, limit = 3)
        names = [torrent.name for torrent in torrents]
        return "Contents: '"+"'    '".join(names)+"'"
                
class Modification(Helper):
    __slots__ = ('id', 'dispersy_id', 'peer_id', 'type_id', 'value', 'time_stamp', 'inserted', 'moderation', 'channeltorrent_id', 'channelcast_db', 'get_nickname')
    def __init__(self, id, dispersy_id, peer_id, type_id, value, time_stamp, inserted, channeltorrent_id):
        self.id = id
        self.dispersy_id = dispersy_id
        self.peer_id = peer_id
        self.type_id = type_id
        self.value = value
        self.time_stamp = time_stamp
        self.inserted = inserted
        self.channeltorrent_id = channeltorrent_id
        
        self.moderation = None
        
    @cacheProperty
    def name(self):
        return self.channelcast_db.id2modification[self.type_id]
    
    @cacheProperty
    def peer_name(self):
        if self.peer_id == None:
            return self.get_nickname()
        return 'Peer %d'%self.peer_id
    
    @cacheProperty
    def torrent(self):
        if self.channeltorrent_id:
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelSearchGridManager
            
            searchManager = ChannelSearchGridManager.getInstance()
            return searchManager.getTorrentFromChannelTorrentId(None, self.channeltorrent_id)

class Moderation(Helper):
    __slots__ = ('id', 'channel_id', 'peer_id', 'by_peer_id', 'severity', 'message', 'time_stamp', 'inserted', 'modification', 'channelcast_db', 'get_nickname')
    def __init__(self, id, channel_id, peer_id, by_peer_id, severity, message, time_stamp, inserted):
        self.id = id
        self.channel_id = channel_id
        self.peer_id = peer_id
        self.by_peer_id = by_peer_id
        self.severity = severity
        self.message = message
        self.time_stamp = time_stamp
        self.inserted = inserted
        self.modification = None
        
    @cacheProperty
    def peer_name(self):
        if self.peer_id == None:
            return self.get_nickname()
        return 'Peer %d'%self.peer_id
    
    @cacheProperty
    def by_peer_name(self):
        if self.by_peer_id == None:
            return self.get_nickname()
        return 'Peer %d'%self.by_peer_id