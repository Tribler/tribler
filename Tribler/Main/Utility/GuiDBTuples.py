import binascii
import logging
import os.path
import sys
from time import time

from datetime import date

from Tribler.Core.Utilities.search_utils import split_into_keywords
from Tribler.Core.Video.utils import videoextdefaults
from Tribler.Core.simpledefs import (DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED, DLSTATUS_SEEDING, DLSTATUS_HASHCHECKING,
                                     DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE,
                                     DLSTATUS_STOPPED_ON_ERROR, DLSTATUS_METADATA, DLSTATUS_CIRCUITS)
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Core.osutils import is_android


# Niels: from http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize


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
    __slots__ = ('_logger', '_cache')

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._cache = {}

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return key in self.__slots__

    def __eq__(self, other):
        if other and hasattr(self, 'id') and hasattr(other, 'id'):
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
    __slots__ = ('infohash', 'name', 'length', 'category', 'status', 'num_seeders',
                 'num_leechers', '_channel', 'channeltorrents_id', 'torrent_db', 'channelcast_db', 'metadata_dict',
                 'download_state', 'relevance_score', 'query_candidates', 'magnetstatus')

    def __init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers, channel, metadata_dict=None):
        Helper.__init__(self)

        assert isinstance(infohash, str), type(infohash)
        assert isinstance(name, basestring), type(name)

        self.infohash = infohash
        self.name = name
        self.length = length or 0
        self.category = category
        self.status = status

        self.num_seeders = num_seeders or 0
        self.num_leechers = num_leechers or 0

        self.update_torrent_id(torrent_id)
        self.updateChannel(channel)

        self.channeltorrents_id = None
        self.torrent_db = None
        self.channelcast_db = None
        self.metadata_dict = metadata_dict

        self.relevance_score = None
        self.query_candidates = None
        self.download_state = None
        self.magnetstatus = None

    @cacheProperty
    def torrent_id(self):
        self._logger.debug("Torrent: fetching getTorrentID from DB %s", self)
        return self.torrent_db.getTorrentID(self.infohash)

    def update_torrent_id(self, torrent_id):
        self._cache['torrent_id'] = torrent_id

    @cacheProperty
    def infohash_as_hex(self):
        return binascii.hexlify(self.infohash).upper()

    @cacheProperty
    def channel(self):
        self._logger.debug("Torrent: fetching getMostPopularChannelFromTorrent from DB %s", self)

        channel = self.channelcast_db.getMostPopularChannelFromTorrent(self.infohash)
        if channel:
            self.channeltorrents_id = channel[-1]
            return Channel(*channel[:-1])

    def updateChannel(self, c):
        self._cache['channel'] = c

    def hasChannel(self):
        return self.channel

    @cacheProperty
    def metadata(self):
        if not self.metadata_dict:
            channel = self.channelcast_db.getMostPopularChannelFromTorrent(self.infohash)
            if channel:
                self.channeltorrents_id = channel[-1]
            self.metadata_dict = self.channelcast_db.get_torrent_metadata(self.channeltorrents_id)
        return self.metadata_dict

    @property
    def swarminfo(self):
        return self.num_seeders, self.num_leechers, sys.maxint

    def updateSwarminfo(self, swarminfo):
        self.num_seeders, self.num_leechers, _ = swarminfo
        self.num_seeders = self.num_seeders or 0
        self.num_leechers = self.num_leechers or 0

    @property
    def state(self):
        stateList = []
        if self.ds:
            status = self.ds.get_status()
            if status == DLSTATUS_CIRCUITS:
                stateList.append('circuits')

            if status == DLSTATUS_STOPPED:
                stateList.append('stopped')

            if status == DLSTATUS_STOPPED_ON_ERROR:
                stateList.append('error')

            if status in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
                stateList.append('active')

            if status in [DLSTATUS_METADATA]:
                stateList.append('metadata')

            if status in [DLSTATUS_HASHCHECKING, DLSTATUS_WAITING4HASHCHECK]:
                stateList.append('checking')

            if status == DLSTATUS_ALLOCATING_DISKSPACE:
                stateList.append('allocating')

            if status == DLSTATUS_SEEDING:
                stateList.append('seeding')

            if status == DLSTATUS_DOWNLOADING:
                stateList.append('downloading')

            if self.ds.progress == 1.0:
                stateList.append('completed')

        return stateList

    @property
    def magnetState(self):
        if self.magnetstatus:
            if self.magnetstatus[2]:
                return 3
            if self.magnetstatus[1]:
                return 2
            return 1
        return 0

    @property
    def progress(self):
        if self.ds:
            return self.ds.get_progress()
        return 0.0

    @property
    def ds(self):
        return self.download_state

    def addDs(self, ds):
        if ds:
            tdef = ds.get_download().get_def()
            if self.infohash and self.infohash == tdef.get_infohash():
                self.download_state = ds
                return True
        return False

    def clearDs(self):
        self.download_state = None

    def assignRelevance(self, matches):
        """
        Assigns a relevance score to this Torrent.
        @param matches A dict containing sets stored under the keys 'swarmname', 'filenames' and 'fileextensions'.
        """

        # Find the lowest term position of the matching keywords
        pos_score = None
        if matches['swarmname']:
            swarmnameTerms = split_into_keywords(self.name)
            swarmnameMatches = matches['swarmname']

            for i, term in enumerate(swarmnameTerms):
                if term in swarmnameMatches:
                    pos_score = -i
                    break

        self.relevance_score = [len(matches['swarmname']), pos_score, len(
            matches['filenames']), len(matches['fileextensions']), 0]

    def exactCopy(self, other):
        if other and isinstance(other, Torrent):
            ids = self.torrent_id == other.torrent_id
            hashes = self.infohash == other.infohash
            readableProps = self.name == other.name and self.length == other.length and self.category == other.category
            return ids and hashes and readableProps
        return False

    def __eq__(self, other):
        if other and isinstance(other, Torrent):
            return self.infohash == other.infohash
        return False

    def __str__(self):
        return self.name

    # Required for drag and drop
    def __getstate__(self):
        statedict = {}
        for key in Torrent.__slots__:
            if key not in ['download_state', 'channelcast_db', 'torrent_db', 'metadata_dict']:
                statedict[key] = getattr(self, key, None)
        return statedict

    @staticmethod
    def fromTorrentDef(tdef):
        return Torrent(-1, tdef.get_infohash(), tdef.get_name(), tdef.get_length(), None, None, 0, 0, False)


class RemoteTorrent(Torrent):
    __slots__ = ()

    def __init__(self, torrent_id, infohash, name, length=0, category=None, status=None, num_seeders=0, num_leechers=0, query_candidates=set()):
        Torrent.__init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers, channel=False)
        self.query_candidates = query_candidates


class CollectedTorrent(Helper):
    __slots__ = ('comment', 'trackers', 'creation_date', 'files', 'last_check', 'torrent')

    def __init__(self, torrent, torrentdef):
        assert isinstance(torrent, Torrent)

        self.torrent = torrent
        if self.torrent_id <= 0:
            raise RuntimeError("self.torrent_id is too low, %d" % self.torrent_id)

        self.comment = torrentdef.get_comment_as_unicode()
        self.trackers = torrentdef.get_trackers_as_single_tuple()
        self.creation_date = min(long(time()), torrentdef.get_creation_date())
        self.files = torrentdef.get_files_as_unicode_with_length()
        self.last_check = -1

    def __getattr__(self, name):
        return getattr(self.torrent, name)

    def __setattr__(self, name, value):
        try:
            Helper.__setattr__(self, name, value)
        except:
            setattr(self.torrent, name, value)

    def __delattr__(self, name):
        try:
            Helper.__delattr__(self, name)
        except:
            delattr(self.torrent, name)

    def __contains__(self, key):
        if key in self.__slots__:
            return True
        return key in self.torrent

    @cacheProperty
    def swarminfo(self):
        self._logger.debug("CollectedTorrent: fetching getTorrent from DB %s", self)

        swarminfo = self.torrent_db.getTorrent(self.infohash,
                                               keys=(u'num_seeders', u'num_leechers', u'last_tracker_check'),
                                               include_mypref=False)
        swarminfo_tuple = None
        if swarminfo:
            swarminfo_tuple = (swarminfo.get(u'num_seeders', 0),
                               swarminfo.get(u'num_leechers', 0),
                               swarminfo.get(u'last_tracker_check', 0))
            self.torrent.num_seeders = swarminfo_tuple[0]
            self.torrent.num_leechers = swarminfo_tuple[1]
            self.last_check = swarminfo_tuple[2]
        return swarminfo_tuple

    def updateSwarminfo(self, swarminfo):
        self.torrent.num_seeders, self.torrent.num_leechers, self.last_check = swarminfo
        self.torrent.num_seeders = self.torrent.num_seeders or 0
        self.torrent.num_leechers = self.torrent.num_leechers or 0
        self._cache['swarminfo'] = swarminfo

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
        if len(self.videofiles) > 0:
            _, filename = max([(size, filename) for filename, size in self.files if filename in self.videofiles])
            return filename

    @cacheProperty
    def subtitlefiles(self):
        if is_android():
            return []

        from Tribler.Main.vwxGUI import VLC_SUPPORTED_SUBTITLES
        subtitles = []
        for filename, length in self.files:
            prefix, ext = os.path.splitext(filename)
            if not ext.startswith('.'):
                ext = '.' + ext
            if ext in VLC_SUPPORTED_SUBTITLES:
                subtitles.append(filename)
        return subtitles

    @cache
    def isPlayable(self):
        return len(self.videofiles) > 0

    def formatCreationDate(self, format='%Y-%m-%d'):
        if self.creation_date > 0:
            return date.fromtimestamp(self.creation_date).strftime(format)
        return 'Unknown'


class NotCollectedTorrent(CollectedTorrent):
    __slots__ = ()

    def __init__(self, torrent, files, trackers):
        assert isinstance(torrent, Torrent)

        self.torrent = torrent
        self.comment = None
        self.trackers = trackers
        self.creation_date = -1
        self.files = files
        self.last_check = -1

        if self.torrent_id <= 0:
            raise RuntimeError("self.torrent_id is too low, %d" % self.torrent_id)


class LibraryTorrent(Torrent):
    __slots__ = ()

    def __init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers):
        Torrent.__init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers, None)


class ChannelTorrent(Torrent):
    __slots__ = ('channeltorrent_id', 'dispersy_id', 'colt_name',
                 'chant_name', 'description', 'time_stamp', 'inserted', 'playlist')

    def __init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers,
                 channeltorrent_id, dispersy_id, chant_name, colt_name, description, time_stamp, inserted, channel,
                 playlist):
        Torrent.__init__(self, torrent_id, infohash, name, length, category, status, num_seeders, num_leechers,
                         channel)

        self.channeltorrent_id = channeltorrent_id
        self.dispersy_id = dispersy_id
        self.colt_name = colt_name
        self.chant_name = chant_name
        self.description = description
        self.time_stamp = time_stamp
        self.inserted = inserted
        self.playlist = playlist

    # @property
    def __get_name(self):
        return self.chant_name or self.colt_name or ''
    # @property

    def __set_name(self, name):
        pass
    # .setter was introduced in Python 2.6
    name = property(__get_name, __set_name)

    @cacheProperty
    def getPlaylist(self):
        if is_android():
            return

        from Tribler.Main.vwxGUI import PLAYLIST_REQ_COLUMNS
        self._logger.debug("ChannelTorrent: fetching getPlaylistForTorrent from DB %s", self)

        playlist = self.channelcast_db.getPlaylistForTorrent(self.channeltorrent_id, PLAYLIST_REQ_COLUMNS)
        if playlist:
            return Playlist(*playlist + (self.channel,))

    # Required for drag and drop
    def __getstate__(self):
        statedict = Torrent.__getstate__(self)
        for key in self.__slots__:
            statedict[key] = getattr(self, key, None)
        return statedict


class RemoteChannelTorrent(ChannelTorrent):
    __slots__ = ()

    def __init__(self, torrent_id, infohash, name, length=0, category=None, status=None, num_seeders=0,
                 num_leechers=0, channel=False, query_candidates=set()):
        ChannelTorrent.__init__(self, torrent_id, infohash, name, length, category, status, num_seeders,
                                num_leechers, -1, '-1', '', name, '', None, None, channel, None)
        self.query_candidates = query_candidates


class Channel(Helper):
    __slots__ = ('id', 'dispersy_cid', 'name', 'description', 'nr_torrents', 'nr_favorites',
                 'nr_spam', 'my_vote', 'modified', 'my_channel', 'torrents', 'popular_torrents')

    def __init__(self, id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified, my_channel):
        Helper.__init__(self)

        self.id = id
        self.dispersy_cid = str(dispersy_cid)

        self.name = name[:40]
        self.description = description[:1024]

        self.nr_torrents = nr_torrents
        self.nr_favorites = nr_favorites or 0
        self.nr_spam = nr_spam or 0
        self.my_vote = my_vote
        self.modified = modified
        self.my_channel = my_channel
        self.torrents = None
        self.popular_torrents = None

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

    def isOpen(self):
        state, myChannel = self.getState()
        return state >= ChannelCommunity.CHANNEL_OPEN

    def isSemiOpen(self):
        state, myChannel = self.getState()
        return state >= ChannelCommunity.CHANNEL_SEMI_OPEN

    @property
    def iamModerator(self):
        return self.getState()[1]

    @cache
    def getState(self):
        if self.isDispersy():
            @blocking_call_on_reactor_thread
            def do_dispersy():
                from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager

                self._logger.debug("Channel: fetching getChannelStateByCID from DB %s", self)

                searchManager = ChannelManager.getInstance()
                result = searchManager.getChannelStateByCID(self.dispersy_cid)
                return result

            return do_dispersy()

        return ChannelCommunity.CHANNEL_CLOSED, self.isMyChannel()

    def setState(self, state, iamModerator):
        self._cache['getState'] = (state, iamModerator)

    def refreshState(self):
        try:
            del self._cache['getState']
        except:
            pass
        return self.getState()

    def addTorrent(self, torrent):
        if not self.torrents:
            self.torrents = set()
        self.torrents.add(torrent)

    def getTorrent(self, infohash):
        if self.torrents:
            for torrent in self.torrents:
                if torrent.infohash == infohash:
                    return torrent

    def __eq__(self, other):
        if other:
            if isinstance(other, Channel):
                return self.id == other.id
            if isinstance(other, int):
                return self.id == other
        return False

    def __str__(self):
        return 'Channel name=%s\nid=%d\ndispersy_cid=%s' % (self.name.encode('utf8'), self.id, self.dispersy_cid.encode("HEX"))


class RemoteChannel(Channel):
    __slots__ = ('permid')

    def __init__(self, permid, name):
        Channel.__init__(self, 0, '-1', name, '', 0, 0, 0, 0, 0, False)
        self.permid = permid


class Comment(Helper):
    __slots__ = ('id', 'dispersy_id', 'channeltorrent_id', '_name', 'peer_id', 'comment', 'reply_to_id',
                 'replies', 'inserted', 'time_stamp', 'playlist', '_torrent', 'channel', 'get_nickname', 'get_mugshot')

    def __init__(self, id, dispersy_id, channeltorrent_id, name, peer_id, comment, reply_to_id, inserted, time_stamp, channel, playlist, torrent):
        Helper.__init__(self)

        self.id = id
        self.dispersy_id = dispersy_id
        self.channeltorrent_id = channeltorrent_id

        self._name = name
        self.peer_id = peer_id
        self.comment = comment
        self.reply_to_id = reply_to_id
        self.replies = []
        self.inserted = inserted
        self.time_stamp = time_stamp

        self.playlist = playlist
        self._torrent = torrent
        self.channel = channel

    @cacheProperty
    def name(self):
        if self.peer_id is None:
            return self.get_nickname()
        if not self._name:
            return 'Peer %d' % self.peer_id
        return self._name

    def isMyComment(self):
        return self.peer_id is None

    @cacheProperty
    def avantar(self):
        if is_android():
            return None

        from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager, SMALL_ICON_MAX_DIM, data2wxBitmap
        gui_image_manager = GuiImageManager.getInstance()

        data = None
        if self.peer_id is None:
            mime, data = self.get_mugshot()
            if data:
                data = data2wxBitmap(mime, data, SMALL_ICON_MAX_DIM)

        if data is None:
            data = gui_image_manager.getImage(u"PEER_THUMB", SMALL_ICON_MAX_DIM)
        return data

    @cacheProperty
    def torrent(self):
        if self._torrent is not None:
            return self._torrent

        if self.channeltorrent_id:
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager

            self._logger.debug("Comment: fetching getTorrentFromChannelTorrentId from DB %s", self)

            searchManager = ChannelManager.getInstance()
            return searchManager.getTorrentFromChannelTorrentId(self.channel, self.channeltorrent_id, False)


class Playlist(Helper):
    __slots__ = ('id', 'dispersy_id', 'channel_id', 'name', 'description', 'nr_torrents', 'channel')

    def __init__(self, id, dispersy_id, channel_id, name, description, nr_torrents, channel):
        Helper.__init__(self)

        self.id = id
        self.dispersy_id = dispersy_id
        self.channel_id = channel_id
        self.name = name
        self.description = description
        self.nr_torrents = nr_torrents

        self.channel = channel

    @cacheProperty
    def extended_description(self):
        if self.description:
            return self.description

        from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager

        # No description, get swarmnames
        searchManager = ChannelManager.getInstance()
        _, _, torrents = searchManager.getTorrentsFromPlaylist(self, limit=3)
        names = [torrent.name for torrent in torrents]
        if len(names) > 0:
            return "Contents: '" + "'    '".join(names) + "'"
        elif self.channel.isOpen():
            return 'This playlist is currently empty, drag and drop any .torrent to add it to this playlist.'
        elif self.channel.isMyChannel():
            return 'This playlist is currently empty, you are the only one who can add torrents to it.'
        return 'This playlist is currently empty, the channel owner has restricted anyone but himself to add torrents to it.'

    def __eq__(self, other):
        if other:
            if isinstance(other, Playlist):
                return self.id == other.id

            if isinstance(other, int):
                return self.id == other
        return False


class MetadataModification(Helper):
    __slots__ = ('torrent', 'message_id', 'key', 'value')

    def __init__(self, torrent, message_id, key, value):
        Helper.__init__(self)

        self.torrent = torrent
        self.message_id = message_id
        self.key = key
        self.value = value

    @property
    def name(self):
        return self.key


class Modification(Helper):
    __slots__ = ('id', 'dispersy_id', 'peer_id', 'type', 'value', 'time_stamp',
                 'inserted', 'moderation', 'channeltorrent_id', 'channelcast_db', 'get_nickname')

    def __init__(self, id, dispersy_id, peer_id, type, value, time_stamp, inserted, channeltorrent_id):
        Helper.__init__(self)

        self.id = id
        self.dispersy_id = dispersy_id
        self.peer_id = peer_id
        self.type = type
        self.value = value
        self.time_stamp = time_stamp
        self.inserted = inserted
        self.channeltorrent_id = channeltorrent_id

        self.moderation = None

    @property
    def name(self):
        return self.type

    @cacheProperty
    def peer_name(self):
        if self.peer_id is None:
            return self.get_nickname()
        return 'Peer %d' % self.peer_id

    @cacheProperty
    def torrent(self):
        if self.channeltorrent_id:
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager

            self._logger.debug("Modification: fetching getTorrentFromChannelTorrentId from DB %s", self)

            searchManager = ChannelManager.getInstance()
            return searchManager.getTorrentFromChannelTorrentId(None, self.channeltorrent_id, False)


class Moderation(Helper):
    __slots__ = ('id', 'channel_id', 'peer_id', 'by_peer_id', 'severity', 'message',
                 'time_stamp', 'inserted', 'modification', 'channelcast_db', 'get_nickname')

    def __init__(self, id, channel_id, peer_id, by_peer_id, severity, message, time_stamp, inserted):
        Helper.__init__(self)

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
        if self.peer_id is None:
            return self.get_nickname()
        return 'Peer %d' % self.peer_id

    @cacheProperty
    def by_peer_name(self):
        if self.by_peer_id is None:
            return self.get_nickname()
        return 'Peer %d' % self.by_peer_id


class Marking(Helper):
    __slots__ = ('dispersy_id', 'channeltorrent_id', 'peer_id', 'type', 'time_stamp', 'get_nickname')

    def __init__(self, dispersy_id, channeltorrent_id, peer_id, type, time_stamp):
        Helper.__init__(self)

        self.dispersy_id = dispersy_id
        self.channeltorrent_id = channeltorrent_id
        self.peer_id = peer_id
        self.type = type
        self.time_stamp = time_stamp

    @cacheProperty
    def peer_name(self):
        if self.peer_id is None:
            return self.get_nickname()
        return 'Peer %d' % self.peer_id

    @cacheProperty
    def torrent(self):
        if self.channeltorrent_id:
            from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager

            self._logger.debug("Marking: fetching getTorrentFromChannelTorrentId from DB %s", self)

            searchManager = ChannelManager.getInstance()
            return searchManager.getTorrentFromChannelTorrentId(None, self.channeltorrent_id, False)
