# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information
import logging
import threading
from time import time
from traceback import print_exc

import wx

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin, forceAndReturnDBThread
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Video.utils import videoextdefaults
from Tribler.Core.simpledefs import (NTFY_TORRENTS, NTFY_MYPREFERENCES, NTFY_VOTECAST, NTFY_CHANNELCAST,
                                     NTFY_METADATA, DLSTATUS_METADATA, DLSTATUS_WAITING4HASHCHECK,
                                     SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT)
from Tribler.Core.Utilities.sort_utils import sort_torrent_fulltext
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import (Torrent, ChannelTorrent, CollectedTorrent, RemoteTorrent,
                                              NotCollectedTorrent, LibraryTorrent, Comment, Modification, Channel,
                                              RemoteChannel, Playlist, Moderation, RemoteChannelTorrent, Marking,
                                              MetadataModification)
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI import (warnWxThread, forceWxThread, TORRENT_REQ_COLUMNS,
                                 CHANNEL_REQ_COLUMNS, PLAYLIST_REQ_COLUMNS, MODIFICATION_REQ_COLUMNS,
                                 MODERATION_REQ_COLUMNS, MARKING_REQ_COLUMNS, COMMENT_REQ_COLUMNS,
                                 TUMBNAILTORRENT_REQ_COLUMNS)
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import (ChannelCommunity, warnIfNotDispersyThread)
from Tribler.community.metadata.community import MetadataCommunity
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.util import call_on_reactor_thread


class TorrentManager(object):
    # Code to make this a singleton
    __single = None

    def __init__(self, guiUtility):
        if TorrentManager.__single:
            raise RuntimeError("TorrentManager is singleton")

        self._logger = logging.getLogger(self.__class__.__name__)

        self.guiUtility = guiUtility
        self.dispersy = None
        self.connected = False

        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.hitsLock = threading.Lock()

        # Remote results for current keywords
        self.remoteHits = []
        self.gotRemoteHits = False
        self.remoteLock = threading.Lock()

        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.searchkeywords = []
        self.oldsearchkeywords = None

        self.filteredResults = 0

        self.category = Category.getInstance()

    def getInstance(*args, **kw):
        if TorrentManager.__single is None:
            TorrentManager.__single = TorrentManager(*args, **kw)
        return TorrentManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        TorrentManager.__single = None
    delInstance = staticmethod(delInstance)

    def downloadTorrentfileFromPeers(self, torrent, callback, duplicate=True, prio=0):
        """
        TORRENT is a GuiDBTuple containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored
        As a first argument the filename of the torrent is passed

        DUPLICATE can be True: the file will be downloaded from peers
        regardless of a previous/current download attempt (returns
        True). Or DUPLICATE can be False: the file will only be
        downloaded when it was not yet attempted to download (when
        False is returned no callback will be made)

        PRIO is the priority, default is 0 which means we need this torrent now.
        If PRIO != 0, then a rate limiter could be used by the remotetorrentrequester

        Returns True or False
        """

        # return False when duplicate
        if not duplicate and self.session.has_download(torrent.infohash):
            return False

        if torrent.query_candidates is None or len(torrent.query_candidates) == 0:
            self.session.download_torrentfile(torrent.infohash, callback, prio)

        else:
            for candidate in torrent.query_candidates:
                self.session.download_torrentfile_from_peer(candidate, torrent.infohash, callback, prio)

        return True

    def downloadTorrent(self, torrent):
        torrent_data = self.session.get_collected_torrent(torrent.infohash)
        if torrent_data is not None:
            tdef = TorrentDef.load_from_memory(torrent_data)
        else:
            tdef = TorrentDefNoMetainfo(torrent.infohash, torrent.name)

        # Api download
        def do_gui():
            self.guiUtility.frame.startDownload(tdef=tdef)
        wx.CallAfter(do_gui)

    def loadTorrent(self, torrent, callback=None):
        if not isinstance(torrent, CollectedTorrent):
            if torrent.torrent_id <= 0:
                torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

            if not self.session.has_collected_torrent(torrent.infohash):
                files = []
                trackers = []

                # see if we have most info in our tables
                if isinstance(torrent, RemoteTorrent):
                    torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                else:
                    torrent_id = torrent.torrent_id

                trackers.extend(self.torrent_db.getTrackerListByTorrentID(torrent_id))

                if 'DHT' in trackers:
                    trackers.remove('DHT')
                if 'no-DHT' in trackers:
                    trackers.remove('no-DHT')

                # We still call getTorrent to fetch .torrent
                self.downloadTorrentfileFromPeers(torrent, None)

                torrent = NotCollectedTorrent(torrent, files, trackers)

            else:
                tdef = TorrentDef.load_from_memory(self.session.get_collected_torrent(torrent.infohash))

                if torrent.torrent_id <= 0:
                    del torrent.torrent_id

                torrent = CollectedTorrent(torrent, tdef)

        self.library_manager.addDownloadState(torrent)
        if callback is not None:
            callback(torrent)
        else:
            return torrent

    def getTorrentByInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash, keys=['C.torrent_id', 'infohash', 'name',
                                                          'length', 'category', 'status', 'num_seeders',
                                                          'num_leechers'])
        if dict:
            t = Torrent(dict['C.torrent_id'], dict['infohash'], dict['name'], dict['length'],
                        dict['category'], dict['status'], dict['num_seeders'], dict['num_leechers'], None)
            t.torrent_db = self.torrent_db
            t.channelcast_db = self.channelcast_db
            t.metadata_db = self.metadata_db

            # prefetching channel, metadata
            _ = t.channel
            _ = t.metadata
            return t

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def connect(self, session, library_manager, channel_manager):
        if not self.connected:
            self.connected = True
            self.session = session

            self.metadata_db = session.open_dbhandler(NTFY_METADATA)
            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
            self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
            self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)

            self.library_manager = library_manager
            self.channel_manager = channel_manager

            self.dispersy = session.lm.dispersy

            self.session.add_observer(self.gotDispersyRemoteHits, SIGNAL_TORRENT, [SIGNAL_ON_SEARCH_RESULTS])
        else:
            raise RuntimeError('TorrentManager already connected')

    def getSearchSuggestion(self, keywords, limit=1):
        return self.torrent_db.getSearchSuggestion(keywords, limit)

    @warnIfNotDispersyThread
    def searchDispersy(self):
        if self.session.get_enable_torrent_search():
            return self.session.search_remote_torrents(self.searchkeywords)
        return 0

    def getHitsInCategory(self, categorykey='all'):
        begintime = time()
        # categorykey can be 'all', 'Video', 'Document', ...

        self._logger.debug("TorrentSearchManager: getHitsInCategory: %s", categorykey)

        try:
            # locking hits variable
            self.hitsLock.acquire()

            # 1. Local search puts hits in self.hits
            beginlocalsearch = time()
            new_local_hits = self.searchLocalDatabase()

            self._logger.debug(
                'TorrentSearchGridManager: getHitsInCat: search found: %d items took %s',
                len(self.hits),
                time() - beginlocalsearch)

            # 2. Add remote hits that may apply.
            new_remote_hits, modified_hits = self.addStoredRemoteResults()

            self._logger.debug(
                'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items',
                len(self.hits))

            beginsort = time()

            if new_local_hits or new_remote_hits:
                sort_torrent_fulltext(self.hits)

                self.hits = self.library_manager.addDownloadStates(self.hits)

                # boudewijn: now that we have sorted the search results we
                # want to prefetch the top N torrents.
                startWorker(None, self.prefetch_hits, delay=1, uId=u"PREFETCH_RESULTS", workerType="guiTaskQueue")

        finally:
            self.hitsLock.release()

        # Niels: important, we should not change self.hits otherwise prefetching will not work
        returned_hits = self.hits

        self._logger.debug('getHitsInCat took: %s of which sort took %s', time() - begintime, time() - beginsort)

        return [len(returned_hits), self.filteredResults, new_local_hits or new_remote_hits, returned_hits, modified_hits]

    def prefetch_hits(self):
        """
        Prefetching attempts to reduce the time required to get the
        user the data it wants.

        We assume the torrent at the beginning of self.hits are more
        likely to be selected by the user than the ones at the
        end. This allows us to perform prefetching operations on a
        subselection of these items.

        The prefetch_hits function can be called multiple times. It
        will only attempt to prefetch every PREFETCH_DELAY
        seconds. This gives search results from multiple sources the
        chance to be received and sorted before prefetching a subset.
        """
        begin_time = time()

        def sesscb_prefetch_done(torrent_fn):
            try:
                tdef = TorrentDef.load(torrent_fn)

                # find the original hit
                for hit in self.hits:
                    if hit.infohash == tdef.get_infohash():
                        self._logger.debug("Prefetch: in %.1fs %s", time() - begin_time, hit.name)
                        return
                self._logger.debug("Prefetch BUG. We got a hit from something we didn't ask for")
            except:
                pass

        # we will prefetch 2 types of torrents, full .torrent files and torrentmessages (only containing the info dict)
        hit_counter_limit = [25, 150]
        prefetch_counter = [0, 0]
        prefetch_counter_limit = [5, 10]

        for i, hit in enumerate(self.hits):
            if not self.guiUtility.utility.session.has_collected_torrent(hit.infohash):
                # this .torrent is not collected, decide if we want to collect it, or only collect torrentmessage
                if prefetch_counter[0] < prefetch_counter_limit[0] and i < hit_counter_limit[0]:
                    if self.downloadTorrentfileFromPeers(hit, lambda _, infohash=hit.infohash: sesscb_prefetch_done(infohash), duplicate=False, prio=1):
                        self._logger.debug("Prefetch: attempting to download actual torrent %s", hit.name)
                        prefetch_counter[0] += 1

                elif prefetch_counter[1] < prefetch_counter_limit[1] and i < hit_counter_limit[1]:
                    if hit.query_candidates is None or len(hit.query_candidates) == 0:
                        continue

                    for candidate in hit.query_candidates:
                        self.session.download_torrentmessage_from_peer(candidate, hit.infohash, None, 1)
                        self._logger.debug("Prefetch: attempting to download torrent message %s", hit.name)
                        prefetch_counter[1] += 1

                else:
                    break

            else:
                # schedule health check
                self.session.check_torrent_health(hit.infohash)

    def getSearchKeywords(self):
        return self.searchkeywords, len(self.hits), self.filteredResults

    def setSearchKeywords(self, wantkeywords):
        if wantkeywords != self.searchkeywords:
            try:
                self.hitsLock.acquire()
                self.remoteLock.acquire()

                self.searchkeywords = [kw for kw in wantkeywords if kw != '']
                self._logger.debug("TorrentSearchGridManager: keywords: %s; time: %s", self.searchkeywords, time())

                self.filteredResults = 0

                self.hits = []
                self.remoteHits = []
                self.gotRemoteHits = False
                self.oldsearchkeywords = None
            finally:
                self.hitsLock.release()
                self.remoteLock.release()

    def searchLocalDatabase(self):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            self._logger.debug("TorrentSearchGridManager: searchLocalDB: returning old hit list %s", len(self.hits))
            return False
        self.oldsearchkeywords = self.searchkeywords

        self._logger.debug("TorrentSearchGridManager: searchLocalDB: Want %s", self.searchkeywords)

        if len(self.searchkeywords) == 0:
            return False

        return self._doSearchLocalDatabase()

    @forceAndReturnDBThread
    def _doSearchLocalDatabase(self):
        begintime = time()

        results = self.torrent_db.searchNames(self.searchkeywords, doSort=False, keys=TORRENT_REQ_COLUMNS)

        begintuples = time()

        if len(results) > 0:
            def create_channel(a):
                return Channel(*a)

            channels = {}
            for a in results:
                channel_details = a[17:]
                if channel_details[0] and channel_details[0] not in channels:
                    channels[channel_details[0]] = create_channel(channel_details)

            def create_torrent(a):
                channel = channels.get(a[17], False)
                if channel and (channel.isFavorite() or channel.isMyChannel()):
                    t = ChannelTorrent(*a[:15] + [channel, None])
                else:
                    t = Torrent(*a[:8] + [False])

                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                t.metadata_db = self.metadata_db
                t.assignRelevance(a[16])
                return t

            results = map(create_torrent, results)
        self.hits = results

        self._logger.debug(
            'TorrentSearchGridManager: _doSearchLocalDatabase took: %s of which tuple creation took %s',
            time() - begintime,
            time() - begintuples)
        return True

    def addStoredRemoteResults(self):
        """ Called by GetHitsInCategory() to add remote results to self.hits """
        begintime = time()
        try:
            hitsUpdated = False
            hitsModified = set()

            with self.remoteLock:
                hits = self.remoteHits
                self.remoteHits = []

            for remoteItem in hits:
                known = False

                for item in self.hits:
                    if item.infohash == remoteItem.infohash:
                        if item.query_candidates is None:
                            item.query_candidates = set()
                        item.query_candidates.update(remoteItem.query_candidates)

                        if remoteItem.hasChannel():
                            if isinstance(item, RemoteTorrent):
                                self.hits.remove(item)  # Replace this item with a new result with a channel
                                break

                            # Maybe update channel?
                            if isinstance(item, RemoteChannelTorrent):
                                this_rating = remoteItem.channel.nr_favorites - remoteItem.channel.nr_spam

                                if item.hasChannel():
                                    current_rating = item.channel.nr_favorites - item.channel.nr_spam
                                else:
                                    current_rating = this_rating - 1

                                if this_rating > current_rating:
                                    item.updateChannel(remoteItem.channel)
                                    hitsModified.add(item.infohash)

                        known = True
                        break

                if not known:
                    # Niels 26-10-2012: override category if name is xxx
                    if remoteItem.category.lower() != u'xxx':
                        local_category = self.category.calculateCategoryNonDict([], remoteItem.name, '', '')
                        if local_category == 'xxx':
                            self._logger.debug('TorrentSearchGridManager: %s is xxx', remoteItem.name)
                            remoteItem.category = u'XXX'

                    self.hits.append(remoteItem)
                    hitsUpdated = True

            return hitsUpdated, hitsModified
        except:
            raise

        finally:
            self.remoteRefresh = False

            self._logger.debug("TorrentSearchGridManager: addStoredRemoteResults: %s", time() - begintime)

        return False, []

    def gotDispersyRemoteHits(self, subject, changetype, objectID, search_results):
        refreshGrid = False

        try:
            keywords = search_results['keywords']
            result_list = search_results['result_list']

            self._logger.debug("Got results: %s, keywords: %s", len(result_list), keywords)

            if self.searchkeywords == keywords:
                # get all channel information
                channel_cache_dict = {}
                channel_cid_list = []
                for result in result_list:
                    if result['channel'] is not None:
                        channel_cid_list.append(result['channel']['dispersy_cid'])

                if len(channel_cid_list) > 0:
                    _, channels = self.channel_manager.getChannelsByCID(channel_cid_list)
                    for channel in channels:
                        channel_cache_dict[channel.dispersy_cid] = channel

                # create Torrent Tuples from the results
                for result in result_list:
                    channel_tuple = None
                    if result['channel'] is not None:
                        channel_tuple = channel_cache_dict.get(result['channel']['dispersy_cid'])

                    if channel_tuple is not None:
                        remoteHit = RemoteChannelTorrent(result['torrent_id'],
                                                         result['infohash'],
                                                         result['name'],
                                                         result['length'],
                                                         result['category'],
                                                         result['status'],
                                                         result['num_seeders'],
                                                         result['num_leechers'],
                                                         channel_tuple,
                                                         result['query_candidates'])
                    else:
                        remoteHit = RemoteTorrent(result['torrent_id'],
                                                  result['infohash'],
                                                  result['name'],
                                                  result['length'],
                                                  result['category'],
                                                  result['status'],
                                                  result['num_seeders'],
                                                  result['num_leechers'],
                                                  result['query_candidates'])

                    remoteHit.relevance_score = result['relevance_score']

                    remoteHit.torrent_db = self.torrent_db
                    remoteHit.channelcast_db = self.channelcast_db

                    with self.remoteLock:
                        self.remoteHits.append(remoteHit)
                    refreshGrid = True

                self.gotRemoteHits = True
        finally:
            if self.gridmgr:
                self.gridmgr.NewResult(keywords)

            if refreshGrid:
                self._logger.debug("TorrentSearchGridManager: gotRemoteHist: scheduling refresh")
                self.refreshGrid(remote=True)
            else:
                self._logger.debug("TorrentSearchGridManager: gotRemoteHist: not scheduling refresh")

    def refreshGrid(self, remote=False):
        if self.gridmgr:
            self.gridmgr.refresh(remote)

    @call_on_reactor_thread
    def modifyTorrent(self, torrent, modifications):
        for community in self.dispersy.get_communities():
            if isinstance(community, MetadataCommunity):
                community.create_metadata_message(torrent.infohash, modifications)
                break

    def getTorrentModifications(self, torrent):
        message_list = self.metadata_db.getMetadataMessageList(torrent.infohash, columns=("message_id",))
        if not message_list:
            return []

        metadata_mod_list = []
        for message_id, in message_list:
            data_list = self.metadata_db.getMetadataData(message_id)
            for key, value in data_list:
                metadata_mod_list.append(MetadataModification(torrent, message_id, key, value))

        return metadata_mod_list

    def createMetadataModificationFromDef(self, channel_id, tdef, extraInfo={}, forward=True, guitorrent=None):
        torrent = guitorrent if guitorrent else Torrent.fromTorrentDef(tdef)

        modifications = []
        for key, value in extraInfo.iteritems():
            if key == 'thumbnail-file':
                continue
            modifications.append((key, value))

        # handle the downloaded thumbnails
        if extraInfo.get('thumbnail-file'):
            from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager
            TorrentStateManager.getInstance().create_and_seed_metadata_thumbnail(extraInfo['thumbnail-file'],
                                                                                 torrent, modifications)

        return True

    def getThumbnailTorrents(self, limit=20):
        result = []
        for t in self.metadata_db.getThumbnailTorrents(TUMBNAILTORRENT_REQ_COLUMNS, limit=limit):
            t = Torrent(*(list(t) + [None]))
            t.torrent_db = self.torrent_db
            result.append(t)

        return result

    def getNotCollectedThumbnailTorrents(self, limit=20):
        result = []
        for t in self.metadata_db.getNotCollectedThumbnailTorrents(TUMBNAILTORRENT_REQ_COLUMNS, limit=limit):
            if t[0] is None:
                continue
            t = Torrent(*(list(t) + [None]))
            t.torrent_db = self.torrent_db
            result.append(t)

        return result


class LibraryManager(object):
    # Code to make this a singleton
    __single = None

    def __init__(self, guiUtility):
        if LibraryManager.__single:
            raise RuntimeError("LibraryManager is singleton")

        self._logger = logging.getLogger(self.__class__.__name__)

        self.guiUtility = guiUtility
        self.connected = False

        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.dslist = []
        self.magnetlist = {}

        # current progress of download states
        self.cache_progress = {}

        # For asking for a refresh when remote results came in
        self.gridmgr = None

        # Gui callbacks
        self.gui_callback = []
        self.user_download_choice = UserDownloadChoice.get_singleton()
        self.wantpeers = []

        self.last_vod_torrent = None

    def getInstance(*args, **kw):
        if LibraryManager.__single is None:
            LibraryManager.__single = LibraryManager(*args, **kw)
        return LibraryManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        LibraryManager.__single = None
    delInstance = staticmethod(delInstance)

    @warnWxThread
    def _get_videoplayer(self):
        """
        Returns the VideoPlayer instance.
        """
        return self.guiUtility.videoplayer

    def download_state_callback(self, dslist):
        """
        Called by any thread
        """
        self.dslist = dslist
        startWorker(None, self._do_gui_callback, uId=u"LibraryManager_refresh_callbacks", workerType="guiTaskQueue")

        return self.wantpeers

    def magnet_started(self, infohash):
        self.magnetlist[infohash] = [long(time()), 0, 0]

    def magnet_got_peers(self, infohash, total_peers):
        if infohash not in self.magnetlist:
            self.magnet_started(infohash)
        self.magnetlist[infohash][1] = total_peers

    def magnet_close(self, infohash):
        if infohash in self.magnetlist:
            del self.magnetlist[infohash]

        return self.wantpeers

    @forceWxThread
    def _do_gui_callback(self):
        dslist = self.dslist[:]
        magnetlist = self.magnetlist.copy()

        for callback in self.gui_callback:
            try:
                callback(dslist, magnetlist)
            except:
                print_exc()

    def add_download_state_callback(self, callback):
        if callback not in self.gui_callback:
            self.gui_callback.append(callback)

    def remove_download_state_callback(self, callback):
        if callback in self.gui_callback:
            self.gui_callback.remove(callback)

    def set_want_peers(self, hashes, enable=True):
        if not enable:
            for h in hashes:
                if h in self.wantpeers:
                    self.wantpeers.remove(h)
        else:
            for h in hashes:
                if hash not in self.wantpeers:
                    self.wantpeers.append(h)

    def addDownloadState(self, torrent):
        # Add downloadstate data to a torrent instance
        for ds in self.dslist:
            torrent.addDs(ds)
        if torrent.infohash in self.magnetlist:
            torrent.magnetstatus = self.magnetlist[torrent.infohash]
        return torrent

    def addDownloadStates(self, torrentlist):
        for torrent in torrentlist:
            for ds in self.dslist:
                torrent.addDs(ds)
            if torrent.infohash in self.magnetlist:
                torrent.magnetstatus = self.magnetlist[torrent.infohash]
        return torrentlist

    def startLastVODTorrent(self):
        if self.last_vod_torrent:
            self.playTorrent(*self.last_vod_torrent)

    def stopLastVODTorrent(self):
        if self.last_vod_torrent:
            self.stopTorrent(self.last_vod_torrent[0])

    @forceWxThread
    def playTorrent(self, infohash, selectedinfilename=None):
        # Videoplayer calls should be on GUI thread, hence forceWxThread

        download = self.session.get_download(infohash)
        if download:
            self.last_vod_torrent = [infohash, selectedinfilename]
            self.guiUtility.ShowPlayer()
            self.stopPlayback()
            self.guiUtility.frame.actlist.expandedPanel_videoplayer.Reset()

            # Call _playDownload when download is ready
            wait_state = [DLSTATUS_METADATA, DLSTATUS_WAITING4HASHCHECK]
            status = download.get_status()
            if status in wait_state:
                fetch_msg = "Fetching torrent..."
                if status == DLSTATUS_METADATA:
                    self.guiUtility.frame.actlist.expandedPanel_videoplayer.SetMessage(fetch_msg, True)

                def wait_until_collected(ds):
                    # Try to kill callbacks from previous calls
                    if [infohash, selectedinfilename] != self.last_vod_torrent:
                        return (0, False)
                    # Wait until we know for sure that the download has metadata
                    elif ds.get_status() in wait_state:
                        if ds.get_status() == DLSTATUS_METADATA:
                            self.guiUtility.frame.actlist.expandedPanel_videoplayer.SetMessage(fetch_msg, True)
                        return (1.0, False)
                    # Play the download
                    self._playDownload(infohash, selectedinfilename)
                    return (0, False)
                download.set_state_callback(wait_until_collected)
            else:
                self._playDownload(infohash, selectedinfilename)
        else:
            def do_db():
                torrent_data = self.guiUtility.utility.session.get_collected_torrent(infohash)
                if torrent_data is not None:
                    tdef = TorrentDef.load_from_memory(torrent_data)
                else:
                    torrent = self.guiUtility.torrentsearch_manager.getTorrentByInfohash(infohash)
                    tdef = TorrentDefNoMetainfo(infohash, torrent.name)
                return tdef

            def do_gui(delayedResult):
                tdef = delayedResult.get()
                download = self.guiUtility.frame.startDownload(
                    tdef=tdef,
                    destdir=DefaultDownloadStartupConfig.getInstance().get_dest_dir(),
                    vodmode=True)

            startWorker(do_gui, do_db, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _playDownload(self, infohash, selectedinfilename):
        download = self.session.get_download(infohash)
        tdef = download.get_def()

        # Default: pick largest videofile
        if not selectedinfilename:
            videofiles = tdef.get_files_as_unicode(exts=videoextdefaults)

            if not videofiles:
                if self.guiUtility.frame.videoparentpanel:
                    self.guiUtility.frame.actlist.expandedPanel_videoplayer.SetMessage("Torrent has no video files.")
                return

            if self.guiUtility.frame.videoparentpanel:
                selectedinfilename = sorted(videofiles, key=lambda x: tdef.get_length(selectedfiles=[x]))[-1]
            else:
                selectedinfilename = self.guiUtility.SelectVideo(videofiles, selectedinfilename)

            if not selectedinfilename:
                return

        fileindex = tdef.get_files_as_unicode().index(selectedinfilename)
        videoplayer = self._get_videoplayer()
        videoplayer.play(download, fileindex)

        # Notify playlist panel
        if self.guiUtility.frame.videoparentpanel:
            self.guiUtility.frame.actlist.expandedPanel_videoplayer.SetTorrentDef(tdef, fileindex)

    def stopPlayback(self):
        if self.guiUtility.frame.videoframe:
            # Recreate the VLC window first, then reset. Otherwise VLC sometimes crashes.
            self.guiUtility.frame.videoframe.recreate_vlc_window()
            self.guiUtility.frame.videoframe.get_videopanel().Reset()

        videoplayer = self._get_videoplayer()
        videoplayer.set_vod_download(None)

    def resumeTorrent(self, torrent, force_seed=False):
        download = self.session.get_download(torrent.infohash)
        resumed = False

        if download:
            download.restart()
            resumed = True

            infohash = download.get_def().get_infohash()
            self.user_download_choice.set_download_state(
                infohash,
                "restartseed" if force_seed and download.get_progress(
                ) == 1.0 else "restart")

        if not resumed:
            torrent_data = self.guiUtility.utility.session.get_collected_torrent(torrent.infohash)
            if torrent_data is not None:
                tdef = TorrentDef.load_from_memory(torrent_data)

                destdirs = self.mypref_db.getMyPrefStats(torrent.torrent_id)
                destdir = destdirs.get(torrent.torrent_id, None)
                self.guiUtility.frame.startDownload(tdef=tdef, destdir=destdir)
            else:
                callback = lambda torrentfilename: self.resumeTorrent(torrent)
                self.torrentsearch_manager.downloadTorrentfileFromPeers(torrent, callback)

    def stopTorrent(self, infohash):
        assert isinstance(infohash, str), "infohash is of type %s" % type(infohash)
        assert len(infohash) == 20, "infohash length is not 20: %s, %s" % (len(infohash), infohash)

        download = self.session.get_download(infohash)
        if download:
            self.stopVideoIfEqual(download)
            download.stop()

            infohash = download.get_def().get_infohash()
            self.user_download_choice.set_download_state(infohash, "stop")

    def deleteTorrent(self, torrent, removecontent=False):
        ds = torrent.download_state
        infohash = torrent.infohash

        if ds is not None:
            self.stopVideoIfEqual(ds.download, reset_playlist=True)

        self.session.remove_download_by_id(infohash, removecontent, removestate=True)
        self.user_download_choice.remove_download_state(infohash)

    def stopVideoIfEqual(self, download, reset_playlist=False):
        videoplayer = self._get_videoplayer()
        playd = videoplayer.get_vod_download()

        if playd == download:
            self.stopPlayback()

            if reset_playlist:
                self.guiUtility.frame.actlist.expandedPanel_videoplayer.Reset()

    def connect(self, session, torrentsearch_manager, channelsearch_manager):
        if not self.connected:
            self.session = session
            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
            self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)

            self.torrentsearch_manager = torrentsearch_manager
            self.channelsearch_manager = channelsearch_manager
            self.connected = True
        else:
            raise RuntimeError('LibrarySearchGridManager is already connected')

    def getHitsInCategory(self):
        begintime = time()

        results = self.torrent_db.getLibraryTorrents(CHANNEL_REQ_COLUMNS)

        if len(results) > 0:
            channelDict = {}
            channels = set((result[0] for result in results))
            if len(channels) > 0:
                _, channels = self.channelsearch_manager.getChannels(channels)
                for channel in channels:
                    channelDict[channel.id] = channel

            def create_torrent(a):
                t = ChannelTorrent(*a[1:] + [channelDict.get(a[0], False), None])

                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                return t

            results = map(create_torrent, results)

            # use best channel torrent
            torrentdict = {}
            for torrent in results:
                if torrent.infohash not in torrentdict:
                    torrentdict[torrent.infohash] = torrent
                else:
                    competitor = torrentdict[torrent.infohash]
                    if competitor.channel and torrent.channel:
                        if competitor.channel.nr_favorites < torrent.channel.nr_favorites:
                            torrentdict[torrent.infohash] = torrent

                        elif competitor.channel.nr_favorites == torrent.channel.nr_favorites and competitor.channel.nr_spam > torrent.channel.nr_spam:
                            torrentdict[torrent.infohash] = torrent
                    elif torrent.channel:
                        torrentdict[torrent.infohash] = torrent

            results = torrentdict.values()

        def sort_by_name(a, b):
            return cmp(a.name.lower(), b.name.lower())

        results.sort(cmp=sort_by_name)

        self._logger.debug('getHitsInCat took: %s', time() - begintime)

        self.hits = self.addDownloadStates(results)
        return [len(self.hits), self.hits]

    def getTorrentFromInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash,
                                          keys=['C.torrent_id',
                                                'infohash', 'name', 'length',
                                                'category', 'status',
                                                'num_seeders', 'num_leechers'])
        if dict and dict['myDownloadHistory']:
            t = LibraryTorrent(dict['C.torrent_id'], dict['infohash'],
                               dict['name'], dict['length'], dict['category'], dict['status'],
                               dict['num_seeders'], dict['num_leechers'])
            t.torrent_db = self.torrent_db
            t.channelcast_db = self.channelcast_db

            # touch channel to force load
            t.channel
            self.addDownloadState(t)
            return t

    def exists(self, infohashes):
        prefrerences = self.mypref_db.getMyPrefListInfohash(returnDeleted=False)
        for infohash in infohashes:
            if infohash in prefrerences:
                self._logger.info("%s missing in library", bin2str(infohash))
                return True
        return False

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()


class ChannelManager(object):
    # Code to make this a singleton
    __single = None

    def __init__(self):
        if ChannelManager.__single:
            raise RuntimeError("ChannelManager is singleton")
        self.connected = False

        self._logger = logging.getLogger(self.__class__.__name__)

        # Contains all matches for keywords in DB, not filtered by category
        self.hits = {}
        self.remoteHits = []
        self.remoteLock = threading.Lock()
        self.remoteRefresh = False

        self.channelcast_db = None
        self.votecastdb = None
        self.dispersy = None

        # For asking for a refresh when remote results came in
        self.gridmgr = None

        self.searchkeywords = []
        self.oldsearchkeywords = []

        self.category = Category.getInstance()

    def getInstance(*args, **kw):
        if ChannelManager.__single is None:
            ChannelManager.__single = ChannelManager(*args, **kw)
        return ChannelManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        ChannelManager.__single = None
    delInstance = staticmethod(delInstance)

    def connect(self, session, library_manager, torrentsearch_manager):
        if not self.connected:
            self.connected = True
            self.session = session
            self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
            self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
            self.votecastdb = self.session.open_dbhandler(NTFY_VOTECAST)
            self.torrentsearch_manager = torrentsearch_manager
            self.library_manager = library_manager
            self.remote_th = session.lm.rtorrent_handler

            self.dispersy = session.lm.dispersy

            self.session.add_observer(self.gotDispersyRemoteHits, SIGNAL_CHANNEL, [SIGNAL_ON_SEARCH_RESULTS])
        else:
            raise RuntimeError('ChannelManager already connected')

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def getChannel(self, channel_id):
        channel = self.channelcast_db.getChannel(channel_id)
        return self._getChannel(channel)

    def _getChannel(self, channel):
        if channel:
            channel = self._createChannel(channel)

            # check if we need to convert our vote
            if channel.isDispersy() and channel.my_vote != 0:
                dispersy_id = self.votecastdb.getDispersyId(channel.id, None) or ''
                if dispersy_id <= 0:
                    timestamp = self.votecastdb.getTimestamp(channel.id, None)
                    self.do_vote(channel.id, channel.my_vote, timestamp)

        return channel

    def getChannels(self, channel_ids):
        channels = self.channelcast_db.getChannels(channel_ids)
        return self._createChannels(channels)

    def getChannelsByCID(self, channel_cids):
        channels = self.channelcast_db.getChannelsByCID(channel_cids)
        return self._createChannels(channels)

    def getChannelState(self, channel_id):
        community = self._disp_get_community_from_channel_id(channel_id)
        return community.get_channel_mode()

    def getChannelStateByCID(self, dispersy_cid):
        community = self._disp_get_community_from_cid(dispersy_cid)
        if community:
            return community.get_channel_mode()

    def setChannelState(self, channel_id, channel_mode):
        community = self._disp_get_community_from_channel_id(channel_id)
        return community.set_channel_mode(channel_mode)

    def getNewChannels(self):
        two_months = time() - 5259487

        newchannels = self.channelcast_db.getNewChannels(two_months)
        return self._createChannels(newchannels)

    def getAllChannels(self):
        allchannels = self.channelcast_db.getAllChannels()
        return self._createChannels(allchannels)

    def getMySubscriptions(self):
        subscriptions = self.channelcast_db.getMySubscribedChannels(includeDispsersy=True)
        return self._createChannels(subscriptions)

    def getPopularChannels(self):
        pchannels = self.channelcast_db.getMostPopularChannels()
        return self._createChannels(pchannels)

    def getUpdatedChannels(self):
        lchannels = self.channelcast_db.getLatestUpdated()
        return self._createChannels(lchannels)

    def getMyChannels(self):
        if self.channelcast_db._channel_id:
            return 1, [self.getChannel(self.channelcast_db._channel_id)]
        return 0, []

    def _createChannel(self, hit):
        return Channel(*hit)

    def _createChannels(self, hits, filterTorrents=True):
        channels = []
        for hit in hits:
            channel = Channel(*hit)
            channels.append(channel)

        return len(channels), channels

    def getTorrentMarkings(self, channeltorrent_id):
        return self.channelcast_db.getTorrentMarkings(channeltorrent_id)

    def getTorrentFromChannel(self, channel, infohash, collectedOnly=True):
        data = self.channelcast_db.getTorrentFromChannelId(channel.id, infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel, collectedOnly=collectedOnly)

    def getTorrentFromChannelTorrentId(self, channel, channeltorrent_id, collectedOnly=True):
        data = self.channelcast_db.getTorrentFromChannelTorrentId(channeltorrent_id, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel, collectedOnly=collectedOnly)

    def getTorrentsFromChannel(self, channel, filterTorrents=True, limit=None):
        hits = self.channelcast_db.getTorrentsFromChannelId(
            channel.id,
            channel.isDispersy(),
            CHANNEL_REQ_COLUMNS,
            limit)
        return self._createTorrents(hits, filterTorrents, {channel.id: channel})

    def getRecentReceivedTorrentsFromChannel(self, channel, filterTorrents=True, limit=None):
        hits = self.channelcast_db.getRecentReceivedTorrentsFromChannelId(channel.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {channel.id: channel})

    def getTorrentsNotInPlaylist(self, channel, filterTorrents=True):
        hits = self.channelcast_db.getTorrentsNotInPlaylist(channel.id, CHANNEL_REQ_COLUMNS)
        results = self._createTorrents(hits, filterTorrents, {channel.id: channel})

        if isinstance(channel, RemoteChannel):
            if len(results) == 0:
                return channel.torrents
        return results

    def getTorrentsFromPlaylist(self, playlist, filterTorrents=True, limit=None):
        hits = self.channelcast_db.getTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id: playlist.channel}, playlist)

    def getTorrentFromPlaylist(self, playlist, infohash):
        data = self.channelcast_db.getTorrentFromPlaylist(playlist.id, infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, playlist.channel, playlist)

    def getRecentTorrentsFromPlaylist(self, playlist, filterTorrents=True, limit=None):
        hits = self.channelcast_db.getRecentTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id: playlist.channel}, playlist)

    def populateWithPlaylists(self, torrents):
        torrentdict = {}
        for torrent in torrents:
            torrentdict[torrent.channeltorrent_id] = torrent

        hits = self.channelcast_db.getPlaylistsForTorrents(torrentdict.keys(), PLAYLIST_REQ_COLUMNS)
        for hit in hits:
            torrent = torrentdict[hit[0]]
            playlist = Playlist(*hit[1:] + (torrent.channel,))
            torrent.playlist = playlist

    def _createTorrent(self, tuple, channel, playlist=None, collectedOnly=True, addDs=True):
        if tuple:
            ct = ChannelTorrent(*tuple[1:] + [channel, playlist])
            ct.torrent_db = self.torrent_db
            ct.channelcast_db = self.channelcast_db

            if addDs:
                self.library_manager.addDownloadState(ct)

            # Only return ChannelTorrent with a name, old not-collected torrents
            # will be filtered due to this
            if not collectedOnly or ct.name:
                return ct

    def _createTorrents(self, hits, filterTorrents, channel_dict={}, playlist=None):
        fetch_channels = set(hit[0] for hit in hits if hit[0] not in channel_dict)
        if len(fetch_channels) > 0:
            _, channels = self.getChannels(fetch_channels)
            for channel in channels:
                channel_dict[channel.id] = channel

        torrents = []
        for hit in hits:
            torrent = self._createTorrent(hit, channel_dict.get(hit[0], None), playlist, addDs=False)
            if torrent:
                torrents.append(torrent)

        self.library_manager.addDownloadStates(torrents)

        self.filteredResults = 0
        if filterTorrents:
            torrents = self._applyFF(torrents)
        return len(torrents), self.filteredResults, torrents

    def getTorrentModifications(self, torrent):
        data = self.channelcast_db.getTorrentModifications(torrent.channeltorrent_id, MODIFICATION_REQ_COLUMNS)
        return self._createModifications(data)

    def getRecentModificationsFromChannel(self, channel, limit=None):
        data = self.channelcast_db.getRecentModificationsFromChannelId(channel.id, MODIFICATION_REQ_COLUMNS, limit)
        return self._createModifications(data)

    def getRecentModificationsFromPlaylist(self, playlist, limit=None):
        data = self.channelcast_db.getRecentModificationsFromPlaylist(playlist.id, MODIFICATION_REQ_COLUMNS, limit)
        return self._createModifications(data)

    def _createModifications(self, hits):
        returnList = []
        for hit in hits:
            mod = Modification(*hit[:8])
            mod.channelcast_db = self.channelcast_db
            mod.get_nickname = self.session.get_nickname

            moderation = hit[8:]
            if moderation[0] is not None:
                moderation = Moderation(*moderation)
                moderation.channelcast_db = self.channelcast_db
                moderation.get_nickname = self.session.get_nickname

                mod.moderation = moderation
            # touch torrent property to load torrent
            mod.torrent

            returnList.append(mod)

        return returnList

    def getRecentModerationsFromChannel(self, channel, limit=None):
        data = self.channelcast_db.getRecentModerationsFromChannel(channel.id, MODERATION_REQ_COLUMNS, limit)
        return self._createModerations(data)

    def getRecentModerationsFromPlaylist(self, playlist, limit=None):
        data = self.channelcast_db.getRecentModerationsFromPlaylist(playlist.id, MODERATION_REQ_COLUMNS, limit)
        return self._createModerations(data)

    def _createModerations(self, hits):
        returnList = []
        for hit in hits:
            mod = Moderation(*hit[:8])
            mod.channelcast_db = self.channelcast_db
            mod.get_nickname = self.session.get_nickname

            modification = hit[8:]
            if modification[0] is not None:
                modification = Modification(*modification)
                modification.channelcast_db = self.channelcast_db
                modification.get_nickname = self.session.get_nickname

                # touch torrent property to load torrent
                modification.torrent

                mod.modification = modification
            returnList.append(mod)

        return returnList

    def getRecentMarkingsFromChannel(self, channel, limit=None):
        data = self.channelcast_db.getRecentMarkingsFromChannel(channel.id, MARKING_REQ_COLUMNS, limit)
        return self._createMarkings(data)

    def getRecentMarkingsFromPlaylist(self, playlist, limit=None):
        data = self.channelcast_db.getRecentMarkingsFromPlaylist(playlist.id, MARKING_REQ_COLUMNS, limit)
        return self._createMarkings(data)

    def _createMarkings(self, hits):
        returnList = []
        for hit in hits:
            mar = Marking(*hit[:5])
            mar.get_nickname = self.session.get_nickname

            # touch torrent property to load torrent
            mar.torrent

            returnList.append(mar)

        return returnList

    def getCommentsFromChannel(self, channel, limit=None):
        hits = self.channelcast_db.getCommentsFromChannelId(channel.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel=channel)

    def getCommentsFromPlayList(self, playlist, limit=None):
        hits = self.channelcast_db.getCommentsFromPlayListId(playlist.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel=playlist.channel, playlist=playlist)

    def getCommentsFromChannelTorrent(self, channel_torrent, limit=None):
        hits = self.channelcast_db.getCommentsFromChannelTorrentId(
            channel_torrent.channeltorrent_id,
            COMMENT_REQ_COLUMNS,
            limit)
        return self._createComments(hits, channel=channel_torrent.channel, channel_torrent=channel_torrent)

    def _createComments(self, hits, channel=None, playlist=None, channel_torrent=None):
        hitsDict = {}
        hitsSequence = []
        for hit in hits:
            comment = Comment(*(hit + (channel, playlist, channel_torrent)))

            comment.get_nickname = self.session.get_nickname
            comment.get_mugshot = self.session.get_mugshot

            # touch torrent property to load torrent
            comment.torrent

            hitsSequence.append(comment.dispersy_id)
            hitsDict[comment.dispersy_id] = comment

        for comment in hitsDict.itervalues():
            if comment.reply_to_id and isinstance(comment.reply_to_id, (long, int)) and comment.reply_to_id in hitsDict:
                replyAfter = hitsDict[comment.reply_to_id]
                replyAfter.replies.append(comment)
                hitsSequence.remove(comment.dispersy_id)

        return [hitsDict[id] for id in hitsSequence if id in hitsDict]

    def getPlaylist(self, channel, playlist_id):
        hit = self.channelcast_db.getPlaylist(playlist_id, PLAYLIST_REQ_COLUMNS)
        return self._createPlaylist(hit, channel)

    def getPlaylistsFromChannel(self, channel):
        hits = self.channelcast_db.getPlaylistsFromChannelId(channel.id, PLAYLIST_REQ_COLUMNS)
        return len(hits), self._createPlaylists(hits, channel=channel)

    def _createPlaylist(self, hit, channel=None):
        if hit:
            pl = Playlist(*(hit + (channel,)))

            # touch extended_description property to possibly load torrents
            pl.extended_description
            return pl

    def _createPlaylists(self, hits, channel=None):
        returnList = []
        for hit in hits:
            playlist = self._createPlaylist(hit, channel)
            returnList.append(playlist)

        return returnList

    def _applyFF(self, hits):
        enabled_category_keys = [key for key, _ in self.category.getCategoryNames()]

        def torrentFilter(torrent):
            okCategory = False

            category = torrent.get("category", u"unknown")

            if category in enabled_category_keys:
                okCategory = True

            if not okCategory:
                self.filteredResults += 1

            okGood = torrent.status != u'dead'
            return okCategory and okGood

        return filter(torrentFilter, hits)

    @warnIfNotDispersyThread
    def _disp_get_community_from_channel_id(self, channel_id):
        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()

        if channel_id:
            # 1. get the dispersy identifier from the channel_id
            dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
            dispersy_cid = str(dispersy_cid)

            return self._disp_get_community_from_cid(dispersy_cid)

        self._logger.info("Could not find channel %s", channel_id)

    @warnIfNotDispersyThread
    def _disp_get_community_from_cid(self, dispersy_cid):
        try:
            return self.dispersy.get_community(dispersy_cid)
        except CommunityNotFoundException:
            return None

    @call_on_reactor_thread
    def createChannel(self, name, description):
        community = ChannelCommunity.create_community(self.dispersy, self.session.dispersy_member,
                                                      tribler_session=self.session)
        community.set_channel_mode(ChannelCommunity.CHANNEL_OPEN)
        community.create_channel(name, description)

    @call_on_reactor_thread
    def createPlaylist(self, channel_id, name, description, infohashes=[]):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.create_playlist(name, description, infohashes)

    @call_on_reactor_thread
    def savePlaylistTorrents(self, channel_id, playlist_id, infohashes):
        # detect changesmodification
        to_be_created = set(infohashes)
        to_be_removed = set()

        sql = "SELECT distinct infohash, PL.dispersy_id FROM PlaylistTorrents PL, ChannelTorrents CT, Torrent T WHERE PL.channeltorrent_id = CT.id AND CT.torrent_id = T.torrent_id AND playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql, (playlist_id,))
        for infohash, dispersy_id in records:
            infohash = str2bin(infohash)
            if infohash in to_be_created:
                to_be_created.remove(infohash)
            else:
                to_be_removed.add(dispersy_id)

        if len(to_be_created) > 0 or len(to_be_removed) > 0:
            community = self._disp_get_community_from_channel_id(channel_id)

            if len(to_be_created) > 0:
                community.create_playlist_torrents(playlist_id, to_be_created)

            if len(to_be_removed) > 0:
                community.remove_playlist_torrents(playlist_id, to_be_removed)

    @call_on_reactor_thread
    def addPlaylistTorrent(self, playlist, torrent):
        if not self.channelcast_db.playlistHasTorrent(playlist.id, torrent.channeltorrent_id):
            community = self._disp_get_community_from_channel_id(playlist.channel.id)
            community.create_playlist_torrents(playlist.id, [torrent.infohash])

    @call_on_reactor_thread
    def createTorrent(self, channel, torrent):
        if not isinstance(torrent, CollectedTorrent):
            def torrent_loaded(loaded_torrent):
                self.createTorrent(channel, loaded_torrent)
            self.torrentsearch_manager.loadTorrent(torrent, torrent_loaded)
            return True

        if not channel:
            channel_id = self.channelcast_db.getMyChannelId()
            if not channel_id:
                self.createChannel(self.session.get_nickname(), '')
                channel_id = self.channelcast_db.getMyChannelId()
        else:
            channel_id = channel.id

        if len(torrent.files) == 0:
            self._logger.info(
                "Could not create torrent, no files? %s %s %s",
                torrent.name,
                torrent.files,
                torrent.trackers)
            return False

        if not self.channelcast_db.hasTorrent(channel_id, torrent.infohash):
            community = self._disp_get_community_from_channel_id(channel_id)
            community._disp_create_torrent(
                torrent.infohash,
                long(time()),
                torrent.name,
                tuple(torrent.files),
                tuple(torrent.trackers))
            return True
        return False

    @call_on_reactor_thread
    def createTorrentFromDef(self, channel_id, tdef, extraInfo={}, forward=True):
        # Make sure that this new tdef is also in collected torrents
        self.remote_th.save_torrent(tdef)

        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()

        if channel_id and not self.channelcast_db.hasTorrent(channel_id, tdef.infohash):
            community = self._disp_get_community_from_channel_id(channel_id)

            files = tdef.get_files_as_unicode_with_length()
            if len(files) == 0:
                self._logger.info(
                    "Could not create torrent, no files? %s %s %s",
                    tdef.get_name_as_unicode(),
                    files,
                    tdef.get_trackers_as_single_tuple())
                return False

            community._disp_create_torrent(
                tdef.infohash,
                long(time()),
                tdef.get_name_as_unicode(),
                tuple(files),
                tdef.get_trackers_as_single_tuple(),
                forward=forward)

            if 'description' in extraInfo:
                desc = extraInfo['description']
                desc = desc.strip()

                if desc != '':
                    data = self.channelcast_db.getTorrentFromChannelId(channel_id, tdef.infohash, CHANNEL_REQ_COLUMNS)
                    torrent = self._createTorrent(data, False)

                    self.modifyTorrent(channel_id, torrent.channeltorrent_id, {'description': desc}, forward=forward)
            return True
        return False

    @call_on_reactor_thread
    def removeTorrent(self, channel, infohash):
        torrent = self.getTorrentFromChannel(channel, infohash, collectedOnly=False)
        if torrent:
            community = self._disp_get_community_from_channel_id(channel.id)
            community.remove_torrents([torrent.dispersy_id])

    @call_on_reactor_thread
    def removeAllTorrents(self, channel):
        _, _, torrents = self.getTorrentsFromChannel(channel, filterTorrents=False)
        dispersy_ids = [torrent.dispersy_id for torrent in torrents if torrent]

        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_torrents(dispersy_ids)

    @call_on_reactor_thread
    def removePlaylist(self, channel, playlist_id):
        playlist = self.getPlaylist(channel, playlist_id)
        if playlist:
            community = self._disp_get_community_from_channel_id(channel.id)
            community.remove_playlists([playlist.dispersy_id])

            self.removeAllPlaylistTorrents(community, playlist)

    @call_on_reactor_thread
    def removeAllPlaylists(self, channel):
        _, playlists = self.dispersy_id(channel)
        dispersy_ids = [playlist.dispersy_id for playlist in playlists if playlist]

        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_playlists(dispersy_ids)
        for playlist in playlists:
            self.removeAllPlaylistTorrents(community, playlist)

    @call_on_reactor_thread
    def removeAllPlaylistTorrents(self, community, playlist):
        sql = "SELECT dispersy_id FROM PlaylistTorrents WHERE playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql, (playlist.id,))
        to_be_removed = [dispersy_id for dispersy_id, in records]

        community.remove_playlist_torrents(playlist.dispersy_id, to_be_removed)

    @call_on_reactor_thread
    def createComment(self, comment, channel, reply_to=None, reply_after=None, playlist=None, infohash=None):
        comment = comment.strip()
        comment = comment[:1023]
        if len(comment) > 0:
            playlist_id = None
            if playlist:
                playlist_id = playlist.id

            community = self._disp_get_community_from_channel_id(channel.id)
            community.create_comment(comment, long(time()), reply_to, reply_after, playlist_id, infohash)

    @call_on_reactor_thread
    def removeComment(self, comment, channel):
        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_comment(comment.dispersy_id)

    @call_on_reactor_thread
    def modifyChannel(self, channel_id, changes):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyChannel(changes)

    @call_on_reactor_thread
    def modifyPlaylist(self, channel_id, playlist_id, name, description):
        dict = {'name': name, 'description': description}

        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyPlaylist(playlist_id, dict)

    @call_on_reactor_thread
    def modifyTorrent(self, channel_id, channeltorrent_id, dict_changes, forward=True):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyTorrent(channeltorrent_id, dict_changes, forward=forward)

    def spam(self, channel_id):
        self.do_vote(channel_id, -1)

    def favorite(self, channel_id):
        self.do_vote(channel_id, 2)

    def remove_vote(self, channel_id):
        self.do_vote(channel_id, 0)

    def do_vote(self, channel_id, vote, timestamp=None):
        dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
        dispersy_cid = str(dispersy_cid)

        if len(dispersy_cid) == 20:
            self.do_vote_cid(dispersy_cid, vote, timestamp)

        elif vote == 2:
            self.votecastdb.subscribe(channel_id)
        elif vote == -1:
            self.votecastdb.spam(channel_id)
        else:
            self.votecastdb.unsubscribe(channel_id)

    @call_on_reactor_thread
    def do_vote_cid(self, dispersy_cid, vote, timestamp=None):
        if not timestamp:
            timestamp = int(time())

        if len(dispersy_cid) == 20:
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    community.disp_create_votecast(dispersy_cid, vote, timestamp)
                    break

    @call_on_reactor_thread
    def markTorrent(self, channel_id, infohash, type):
        community = self._disp_get_community_from_channel_id(channel_id)
        community._disp_create_mark_torrent(infohash, type, long(time()))

    @call_on_reactor_thread
    def revertModification(self, channel, moderation, text, severity, revert_to):
        cause = moderation.dispersy_id

        community = self._disp_get_community_from_channel_id(channel.id)
        community._disp_create_moderation(text, long(time()), severity, cause)

    def getNrTorrentsDownloaded(self, publisher_id):
        return self.channelcast_db.getNrTorrentsDownloaded(publisher_id)

    def setSearchKeywords(self, wantkeywords):
        if wantkeywords != self.searchkeywords:
            try:
                self.remoteLock.acquire()

                self.searchkeywords = wantkeywords
                self.remoteHits = []
                self.remoteRefresh = False

            finally:
                self.remoteLock.release()

    def getChannelHits(self):
        begintime = time()

        hitsUpdated = self.searchLocalDatabase()
        self._logger.debug('ChannelManager: getChannelHits: search found: %d items', len(self.hits))

        with self.remoteLock:
            # merge remoteHits
            if len(self.remoteHits) > 0:
                for channel in self.remoteHits:
                    if channel and channel.id not in self.hits:
                        self.hits[channel.id] = channel
                        hitsUpdated = True

            self.remoteRefresh = False

        self._logger.debug("ChannelManager: getChannelHits took %s", time() - begintime)

        if len(self.hits) == 0:
            return [0, hitsUpdated, None]
        else:
            return [len(self.hits), hitsUpdated, self.hits]

    @warnIfNotDispersyThread
    def searchDispersy(self):
        if self.session.get_enable_channel_search():
            return self.session.search_remote_channels(self.searchkeywords)
        return 0

    def searchLocalDatabase(self):
        """ Called by GetChannelHits() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            self._logger.debug("ChannelManager: searchLocalDB: returning old hit list %s", len(self.hits))
            return False

        self.oldsearchkeywords = self.searchkeywords

        ("ChannelManager: searchLocalDB: Want %s", self.searchkeywords)

        if len(self.searchkeywords) == 0 or len(self.searchkeywords) == 1 and self.searchkeywords[0] == '':
            return False
        return self._searchLocalDatabase()

    @forceAndReturnDBThread
    def _searchLocalDatabase(self):
        self.hits = {}
        hits = self.channelcast_db.searchChannels(self.searchkeywords)
        _, channels = self._createChannels(hits)

        for channel in channels:
            self.hits[channel.id] = channel
        return True

    def gotDispersyRemoteHits(self, subject, changetype, objectID, results):
        kws = results['keywords']
        result_list = results['result_list']
        if self.searchkeywords == kws:
            channels = result_list
            _, dispersyChannels = self._createChannels(channels)

            with self.remoteLock:
                for channel in dispersyChannels:
                    self.remoteHits.append(channel)

                refreshGrid = len(self.remoteHits) > 0
                if refreshGrid:
                    # if already scheduled, dont schedule another
                    if self.remoteRefresh:
                        refreshGrid = False
                    else:
                        self.remoteRefresh = True

            if refreshGrid:
                self.refreshGrid()

    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh_channel()
