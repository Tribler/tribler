# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information

import sys
import wx
import os
from binascii import hexlify
from traceback import print_exc, print_stack
from time import time

from Tribler.Category.Category import Category
from Tribler.Core.Search.SearchManager import SearchManager, split_into_keywords
from Tribler.Core.Search.Reranking import getTorrentReranker, DefaultTorrentReranker
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin, NULL, forceAndReturnDBThread
from Tribler.Core.simpledefs import *
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY

from Tribler.community.channel.community import ChannelCommunity, \
    forceDispersyThread, forceAndReturnDispersyThread, forcePrioDispersyThread

from Tribler.Core.Utilities.utilities import get_collected_torrent_filename, parse_magnetlink
from Tribler.Core.Session import Session
from Tribler.Video.VideoPlayer import VideoPlayer

from math import sqrt
from __init__ import *
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.Core.Search.Bundler import Bundler
from Tribler.Main.Utility.GuiDBTuples import Torrent, ChannelTorrent, CollectedTorrent, RemoteTorrent, getValidArgs, NotCollectedTorrent, LibraryTorrent, \
    Comment, Modification, Channel, RemoteChannel, Playlist, Moderation, \
    RemoteChannelTorrent, Marking
import threading
from copy import copy
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.community.search.community import SearchCommunity
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

DEBUG = False

SEARCHMODE_STOPPED = 1
SEARCHMODE_SEARCHING = 2
SEARCHMODE_NONE = 3
VOTE_LIMIT = -5


class TorrentManager:
    # Code to make this a singleton
    __single = None

    def __init__(self, guiUtility):
        if TorrentManager.__single:
            raise RuntimeError("TorrentManager is singleton")
        self.guiUtility = guiUtility
        self.dispersy = None
        self.col_torrent_dir = None
        self.connected = False

        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.hitsLock = threading.Lock()

        # Remote results for current keywords
        self.remoteHits = []
        self.gotRemoteHits = False
        self.remoteLock = threading.Lock()

        # Requests for torrents
        self.requestedTorrents = set()

        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.guiserver = GUITaskQueue.getInstance()

        self.searchkeywords = []
        self.rerankingStrategy = DefaultTorrentReranker()
        self.oldsearchkeywords = None

        self.filteredResults = 0

        self.bundler = Bundler()
        self.bundle_mode = None
        self.bundle_mode_changed = True

        self.category = Category.getInstance()
        self.xxx_category = 0

    def getInstance(*args, **kw):
        if TorrentManager.__single is None:
            TorrentManager.__single = TorrentManager(*args, **kw)
        return TorrentManager.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        TorrentManager.__single = None
    delInstance = staticmethod(delInstance)

    def getCollectedFilename(self, torrent, retried=False):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        Returns a filename, if filename is known
        """
        torrent_filename = torrent.torrent_file_name
        if torrent_filename and os.path.isfile(torrent_filename):
            return torrent_filename

        # .torrent not found
        if torrent.swift_torrent_hash:
            sdef = SwiftDef(torrent.swift_torrent_hash)
            torrent_filename = torrent_filename = os.path.join(self.col_torrent_dir, sdef.get_roothash_as_hex())

            if os.path.isfile(torrent_filename):
                try:
                    tdef = TorrentDef.load(torrent_filename)
                    if self.torrent_db.hasTorrent(torrent.infohash):
                        self.torrent_db.updateTorrent(torrent.infohash, torrent_file_name=torrent_filename)
                    else:
                        self.torrent_db._addTorrentToDB(tdef, source="BC", extra_info={'filename': torrent_filename, 'status': 'good'}, commit=True)

                    return torrent_filename

                except ValueError:
                    pass  # bad bedecoded torrent, ie not complete yet

        if not retried:
            # reload torrent to see if database contains any changes
            dict = self.torrent_db.getTorrent(torrent.infohash, keys=['swift_torrent_hash', 'torrent_file_name'], include_mypref=False)
            if dict:
                torrent.swift_torrent_hash = dict['swift_torrent_hash']
                torrent.torrent_file_name = dict['torrent_file_name']
                return self.getCollectedFilename(torrent, retried=True)

    def getCollectedFilenameFromDef(self, torrentdef):
        torrent = self.getTorrentByInfohash(torrentdef.infohash)
        if torrent:
            return self.getCollectedFilename(torrent)

    def getTorrent(self, torrent, callback, prio=0):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored

        Returns a boolean + request_type
        describing if the torrent is requested
        """

        torrent_filename = self.getCollectedFilename(torrent)
        if torrent_filename:
            return torrent_filename

        if self.downloadTorrentfileFromPeers(torrent, callback, duplicate=True, prio=prio):
            candidates = torrent.query_candidates
            if candidates and len(candidates) > 0:
                return (True, "from peers")
            return (True, "from the dht")

        return False

    def downloadTorrentfileFromPeers(self, torrent, callback, duplicate=True, prio=0):
        """
        TORRENT is a GuiDBTuple containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored

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
        if not duplicate and torrent.infohash in self.requestedTorrents:
            return False

        if torrent.query_candidates == None or len(torrent.query_candidates) == 0:
            self.session.download_torrentfile(torrent.infohash, torrent.swift_torrent_hash, callback, prio)

        else:
            # only add to requestedTorrents if we have peers
            self.requestedTorrents.add(torrent.infohash)

            candidates = list(torrent.query_candidates)
            for candidate in candidates:
                self.session.download_torrentfile_from_peer(candidate, torrent.infohash, torrent.swift_torrent_hash, callback, prio)

        return True

    def downloadTorrentmessagesFromPeer(self, candidate, torrents, callback=None, prio=0):
        """
        TORRENT is a GuiDBTuple containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored

        DUPLICATE can be True: the file will be downloaded from peers
        regardless of a previous/current download attempt (returns
        True). Or DUPLICATE can be False: the file will only be
        downloaded when it was not yet attempted to download (when
        False is returned no callback will be made)

        PRIO is the priority, default is 0 which means we need this torrent now.
        If PRIO != 0, then a rate limiter could be used by the remotetorrentrequester

        Returns True or False
        """
        infohashes = set([torrent.infohash for torrent in torrents])
        self.session.download_torrentmessages_from_peer(candidate, infohashes, callback, prio)
        return True

    def downloadTorrent(self, torrent, dest=None, secret=False, vodmode=False, selectedFiles=None):
        torrent_filename = self.getCollectedFilename(torrent)

        name = torrent.get('name', torrent.infohash)
        clicklog = {'keywords': self.searchkeywords,
                    'reranking_strategy': self.rerankingStrategy.getID()}

        if "click_position" in torrent:
            clicklog["click_position"] = torrent["click_position"]

        sdef = SwiftDef(torrent.swift_hash, "127.0.0.1:%d" % self.session.get_swift_dht_listen_port()) if torrent.swift_hash else None
        tdef = TorrentDefNoMetainfo(torrent.infohash, torrent.name) if not isinstance(torrent_filename, basestring) else None

        # Api download
        def do_gui():
            d = self.guiUtility.frame.startDownload(torrent_filename, sdef=sdef, tdef=tdef, destdir=dest, clicklog=clicklog, name=name, vodmode=vodmode, selectedFiles=selectedFiles)  # # remove name=name
            if d:
                if secret:
                    self.torrent_db.setSecret(torrent.infohash, secret)

                if DEBUG:
                    print >> sys.stderr, 'standardDetails: download: download started'
        wx.CallAfter(do_gui)

        return bool(tdef)

    def loadTorrent(self, torrent, callback=None):
        if not isinstance(torrent, CollectedTorrent):

            torrent_filename = self.getCollectedFilename(torrent)
            if not torrent_filename:
                files = []
                trackers = []

                # see if we have most info in our tables
                if isinstance(torrent, RemoteTorrent):
                    torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                else:
                    torrent_id = torrent.torrent_id

                if torrent_id and torrent_id != -1:
                    files = self.torrent_db.getTorrentFiles(torrent_id)

                    collectingSources = self.torrent_db.getTorrentCollecting(torrent_id)
                    for source, in collectingSources:
                        if source.startswith('magnet'):
                            _, _, trs = parse_magnetlink(source)
                            trackers.extend(trs)

                if len(files) > 0:
                    # We still call getTorrent to fetch .torrent
                    self.getTorrent(torrent, None, prio=1)

                    torrent = NotCollectedTorrent(torrent, files, trackers)
                else:
                    torrent_callback = lambda: self.loadTorrent(torrent, callback)
                    torrent_filename = self.getTorrent(torrent, torrent_callback)

                    if torrent_filename[0]:
                        return torrent_filename[1]
            else:
                try:
                    tdef = TorrentDef.load(torrent_filename)

                except ValueError:
                    # we should move fixTorrent to this object
                    if self.guiUtility.frame.fixTorrent(torrent_filename):
                        tdef = TorrentDef.load(torrent_filename)

                    else:
                        # cannot repair torrent, removing
                        os.remove(torrent_filename)
                        return self.loadTorrent(torrent, callback)

                torrent = CollectedTorrent(torrent, tdef)

        self.library_manager.addDownloadState(torrent)
        if not callback is None:
            callback(torrent)
        else:
            return torrent

    def getSwarmInfo(self, infohash):
        return self.torrent_db.getSwarmInfoByInfohash(infohash)

    def getTorrentByInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash, keys=['C.torrent_id', 'infohash', 'swift_hash', 'swift_torrent_hash', 'name', 'torrent_file_name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers'])
        if dict:
            t = Torrent(dict['C.torrent_id'], dict['infohash'], dict['swift_hash'], dict['swift_torrent_hash'], dict['name'], dict['torrent_file_name'], dict['length'], dict['category_id'], dict['status_id'], dict['num_seeders'], dict['num_leechers'], None)
            t.torrent_db = self.torrent_db
            t.channelcast_db = self.channelcast_db

            _ = t.channel
            return t

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def connect(self, session, library_manager, channel_manager):
        if not self.connected:
            self.connected = True
            self.session = session
            self.col_torrent_dir = self.session.get_torrent_collecting_dir()

            self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
            self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
            self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
            self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)

            self.library_manager = library_manager
            self.channel_manager = channel_manager

            self.dispersy = session.lm.dispersy
            self.xxx_category = self.torrent_db.category_table.get('xxx', 0)
        else:
            raise RuntimeError('TorrentManager already connected')

    def getSearchSuggestion(self, keywords, limit=1):
        return self.torrent_db.getSearchSuggestion(keywords, limit)

    @forceAndReturnDispersyThread
    def searchDispersy(self):
        nr_requests_made = 0
        if self.dispersy:
            for community in self.dispersy.get_communities():
                if isinstance(community, SearchCommunity):
                    nr_requests_made = community.create_search(self.searchkeywords, self.gotDispersyRemoteHits)
                    break

        if not nr_requests_made:
            print >> sys.stderr, "Could not send search, SearchCommunity not found?"
        return nr_requests_made

    def getHitsInCategory(self, categorykey='all', sort='fulltextmetric'):
        if DEBUG:
            begintime = time()
        # categorykey can be 'all', 'Video', 'Document', ...
        bundle_mode = self.bundle_mode

        if DEBUG:
            print >> sys.stderr, "TorrentSearchManager: getHitsInCategory:", categorykey

        try:
            # locking hits variable
            self.hitsLock.acquire()

            # 1. Local search puts hits in self.hits
            if DEBUG:
                beginlocalsearch = time()
            new_local_hits = self.searchLocalDatabase()

            if DEBUG:
                print >> sys.stderr, 'TorrentSearchGridManager: getHitsInCat: search found: %d items took %s' % (len(self.hits), time() - beginlocalsearch)

            # 2. Add remote hits that may apply.
            new_remote_hits, modified_hits = self.addStoredRemoteResults()

            if DEBUG:
                print >> sys.stderr, 'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items' % len(self.hits)

            if DEBUG:
                beginsort = time()

            if new_local_hits or new_remote_hits:
                if sort == 'rameezmetric':
                    self.rameezSort()

                elif sort == 'fulltextmetric':
                    self.fulltextSort()

                self.hits = self.rerankingStrategy.rerank(self.hits, self.searchkeywords, self.torrent_db,
                                                         None, self.mypref_db, None)

                self.hits = self.library_manager.addDownloadStates(self.hits)

                # boudewijn: now that we have sorted the search results we
                # want to prefetch the top N torrents.
                self.guiserver.add_task(self.prefetch_hits, t=1, id="PREFETCH_RESULTS")

            if DEBUG:
                beginbundle = time()

        finally:
            self.hitsLock.release()

        # Niels: important, we should not change self.hits otherwise prefetching will not work
        returned_hits, selected_bundle_mode = self.bundler.bundle(self.hits, bundle_mode, self.searchkeywords)

        if DEBUG:
            print >> sys.stderr, 'TorrentSearchGridManager: getHitsInCat took: %s of which sort took %s, bundle took %s' % (time() - begintime, beginbundle - beginsort, time() - beginbundle)

        bundle_mode_changed = self.bundle_mode_changed or (selected_bundle_mode != bundle_mode)
        self.bundle_mode_changed = False

        return [len(returned_hits), self.filteredResults, new_local_hits or new_remote_hits or bundle_mode_changed, selected_bundle_mode, returned_hits, modified_hits]

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
        if DEBUG:
            begin_time = time()

        def sesscb_prefetch_done(infohash):
            if DEBUG:
                # find the original hit
                for hit in self.hits:
                    if hit.infohash == infohash:
                        print >> sys.stderr, "Prefetch: in", "%.1fs" % (time() - begin_time), hit.name
                        return
                print >> sys.stderr, "Prefetch BUG. We got a hit from something we didn't ask for"

        # we will prefetch 2 types of torrents, full .torrent files and torrentmessages (only containing the info dict)
        hit_counter_limit = [25, 150]
        prefetch_counter = [0, 0]
        prefetch_counter_limit = [3, 15]

        to_be_prefetched = {}

        for i, hit in enumerate(self.hits):
            torrent_filename = self.getCollectedFilename(hit, retried=True)
            if not torrent_filename:
                # this .torrent is not collected, decide if we want to collect it, or only collect torrentmessage
                if prefetch_counter[0] < prefetch_counter_limit[0] and i < hit_counter_limit[0]:
                    if self.downloadTorrentfileFromPeers(hit, lambda infohash=hit.infohash: sesscb_prefetch_done(infohash), duplicate=False, prio=1):
                        if DEBUG:
                            print >> sys.stderr, "Prefetch: attempting to download actual torrent", hit.name
                        prefetch_counter[0] += 1

                elif prefetch_counter[1] < prefetch_counter_limit[1] and i < hit_counter_limit[1]:
                    if hit.query_candidates and len(hit.query_candidates) > 0:
                        for candidate in hit.query_candidates:
                            if candidate not in to_be_prefetched:
                                to_be_prefetched[candidate] = set()
                            to_be_prefetched[candidate].add(hit)
                        prefetch_counter[1] += 1
                else:
                    break

            else:
                # schedule health check
                TorrentChecking.getInstance().addTorrentToQueue(hit)

        for candidate, torrents in to_be_prefetched.iteritems():
            self.downloadTorrentmessagesFromPeer(candidate, torrents, sesscb_prefetch_done, prio=1)

    def getSearchKeywords(self):
        return self.searchkeywords, len(self.hits), self.filteredResults

    def setSearchKeywords(self, wantkeywords):
        if wantkeywords != self.searchkeywords:
            try:
                self.hitsLock.acquire()
                self.remoteLock.acquire()

                self.bundle_mode = None
                self.searchkeywords = [kw for kw in wantkeywords if kw != '']
                if DEBUG:
                    print >> sys.stderr, "TorrentSearchGridManager: keywords:", self.searchkeywords, ";time:%", time()

                self.filteredResults = 0

                self.hits = []
                self.remoteHits = []
                self.gotRemoteHits = False
                self.oldsearchkeywords = None
            finally:
                self.hitsLock.release()
                self.remoteLock.release()

    def setBundleMode(self, bundle_mode, refresh=True):
        if bundle_mode != self.bundle_mode:
            self.bundle_mode = bundle_mode
            self.bundle_mode_changed = True
            if refresh:
                self.refreshGrid()

    def searchLocalDatabase(self):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            if DEBUG:
                print >> sys.stderr, "TorrentSearchGridManager: searchLocalDB: returning old hit list", len(self.hits)
            return False
        self.oldsearchkeywords = self.searchkeywords

        if DEBUG:
            print >> sys.stderr, "TorrentSearchGridManager: searchLocalDB: Want", self.searchkeywords

        if len(self.searchkeywords) == 0:
            return False

        return self._doSearchLocalDatabase()

    @forceAndReturnDBThread
    def _doSearchLocalDatabase(self):
        if DEBUG:
            begintime = time()

        results = self.torrent_db.searchNames(self.searchkeywords, doSort=False, keys=TORRENT_REQ_COLUMNS)

        if DEBUG:
            begintuples = time()

        if len(results) > 0:
            def create_channel(a):
                return Channel(*a)

            channels = {}
            for a in results:
                channel_details = a[-10:]
                if channel_details[0] and channel_details[0] not in channels:
                    channels[channel_details[0]] = create_channel(channel_details)

            def create_torrent(a):
                channel = channels.get(a[-10], False)
                if channel and (channel.isFavorite() or channel.isMyChannel()):
                    t = ChannelTorrent(*a[:-12] + [channel, None])
                else:
                    t = Torrent(*a[:11] + [False])

                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                t.assignRelevance(a[-11])
                return t

            results = map(create_torrent, results)
        self.hits = results

        if DEBUG:
            print >> sys.stderr, 'TorrentSearchGridManager: _doSearchLocalDatabase took: %s of which tuple creation took %s' % (time() - begintime, time() - begintuples)
        return True

    def addStoredRemoteResults(self):
        """ Called by GetHitsInCategory() to add remote results to self.hits """
        if DEBUG:
            begintime = time()
        try:
            self.remoteLock.acquire()

            hitsUpdated = False
            hitsModified = set()
            for remoteItem in self.remoteHits:
                known = False

                for item in self.hits:
                    if item.infohash == remoteItem.infohash:
                        if item.query_candidates == None:
                            item.query_candidates = set()
                        item.query_candidates.update(remoteItem.query_candidates)

                        if item.swift_hash == None:
                            item.swift_hash = remoteItem.swift_hash
                            hitsModified.add(item.infohash)

                        if item.swift_torrent_hash == None:
                            item.swift_torrent_hash = remoteItem.swift_torrent_hash
                            hitsModified.add(item.infohash)

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
                    if remoteItem.category_id != self.xxx_category:
                        local_category = self.category.calculateCategoryNonDict([], remoteItem.name, '', '')[0]
                        if local_category == 'xxx':
                            if DEBUG:
                                print >> sys.stderr, 'TorrentSearchGridManager:', remoteItem.name, "is xxx"
                            remoteItem.category_id = self.xxx_category

                    self.hits.append(remoteItem)
                    hitsUpdated = True

            self.remoteHits = []
            return hitsUpdated, hitsModified
        except:
            raise

        finally:
            self.remoteRefresh = False
            self.remoteLock.release()

            if DEBUG:
                print >> sys.stderr, "TorrentSearchGridManager: addStoredRemoteResults: ", time() - begintime

        return False, []

    def gotDispersyRemoteHits(self, keywords, results, candidate):
        refreshGrid = False
        try:
            if DEBUG:
                print >> sys.stderr, "TorrentSearchGridManager: gotRemoteHist: got", len(results), "unfiltered results for", keywords, candidate, time()
            self.remoteLock.acquire()

            if self.searchkeywords == keywords:
                self.gotRemoteHits = True

                channeldict = {}
                channels = set([result[-1] for result in results if result[-1]])
                if len(channels) > 0:
                    _, channels = self.channel_manager.getChannelsByCID(channels)

                    for channel in channels:
                        channeldict[channel.dispersy_cid] = channel

                for result in results:
                    categories = result[4]
                    category_id = self.torrent_db.category_table.get(categories[0], 0)

                    channel = channeldict.get(result[-1], False)
                    if channel:
                        remoteHit = RemoteChannelTorrent(-1, result[0], result[8], result[9], result[1], result[2], category_id, self.torrent_db.status_table['good'], result[6], result[7], channel, set([candidate]))
                    else:
                        remoteHit = RemoteTorrent(-1, result[0], result[8], result[9], result[1], result[2], category_id, self.torrent_db.status_table['good'], result[6], result[7], set([candidate]))

                    # Guess matches
                    keywordset = set(keywords)
                    swarmnameset = set(split_into_keywords(remoteHit.name))
                    matches = {'fileextensions': set()}
                    matches['swarmname'] = swarmnameset & keywordset  # all keywords matching in swarmname
                    matches['filenames'] = keywordset - matches['swarmname']  # remaining keywords should thus me matching in filenames or fileextensions

                    if len(matches['filenames']) == 0:
                        _, ext = os.path.splitext(result[0])
                        ext = ext[1:]

                        matches['filenames'] = matches['swarmname']
                        matches['filenames'].discard(ext)

                        if ext in keywordset:
                            matches['fileextensions'].add(ext)
                    remoteHit.assignRelevance(matches)
                    remoteHit.torrent_db = self.torrent_db
                    remoteHit.channelcast_db = self.channelcast_db

                    self.remoteHits.append(remoteHit)
                    refreshGrid = True
        finally:
            self.remoteLock.release()

            if self.gridmgr:
                self.gridmgr.NewResult(keywords)

            if refreshGrid:
                if DEBUG:
                    print >> sys.stderr, "TorrentSearchGridManager: gotRemoteHist: scheduling refresh"
                self.refreshGrid(remote=True)
            elif DEBUG:
                print >> sys.stderr, "TorrentSearchGridManager: gotRemoteHist: not scheduling refresh"

    def refreshGrid(self, remote=False):
        if self.gridmgr:
            self.gridmgr.refresh(remote)

    # Rameez: The following code will call normalization functions and then
    # sort and merge the torrent results
    def rameezSort(self):
        norm_num_seeders = self.doStatNormalization(self.hits, 'num_seeders')
        norm_neg_votes = self.doStatNormalization(self.hits, 'neg_votes')
        norm_subscriptions = self.doStatNormalization(self.hits, 'subscriptions')

        def score_cmp(a, b):
            info_a = a.infohash
            info_b = b.infohash

            # normScores can be small, so multiply
            score_a = 0.8 * norm_num_seeders[info_a] - 0.1 * norm_neg_votes[info_a] + 0.1 * norm_subscriptions[info_a]
            score_b = 0.8 * norm_num_seeders[info_b] - 0.1 * norm_neg_votes[info_b] + 0.1 * norm_subscriptions[info_b]

            return cmp(score_a, score_b)

        self.hits.sort(cmp, reverse=True)

    def fulltextSort(self):
        norm_num_seeders = self.doStatNormalization(self.hits, 'num_seeders')
        norm_neg_votes = self.doStatNormalization(self.hits, 'neg_votes')
        norm_subscriptions = self.doStatNormalization(self.hits, 'subscriptions')

        for hit in self.hits:
            score = 0.8 * norm_num_seeders[hit.infohash] - 0.1 * norm_neg_votes[hit.infohash] + 0.1 * norm_subscriptions[hit.infohash]
            hit.relevance_score[-1] = score

        self.hits.sort(key=lambda hit: hit.relevance_score, reverse=True)

    def doStatNormalization(self, hits, normKey):
        '''Center the variance on zero (this means mean == 0) and divide
        all values by the standard deviation. This is sometimes called scaling.
        This is done on the field normKey of hits.'''

        tot = 0
        for hit in hits:
            tot += (hit.get(normKey, 0) or 0)

        if len(hits) > 0:
            mean = tot / len(hits)
        else:
            mean = 0

        sum = 0
        for hit in hits:
            temp = (hit.get(normKey, 0) or 0) - mean
            temp = temp * temp
            sum += temp

        if len(hits) > 1:
            dev = sum / (len(hits) - 1)
        else:
            dev = 0

        stdDev = sqrt(dev)

        return_dict = {}
        for hit in hits:
            if stdDev > 0:
                return_dict[hit.infohash] = ((hit.get(normKey, 0) or 0) - mean) / stdDev
            else:
                return_dict[hit.infohash] = 0
        return return_dict


class LibraryManager:
    # Code to make this a singleton
    __single = None

    def __init__(self, guiUtility):
        if LibraryManager.__single:
            raise RuntimeError("LibraryManager is singleton")
        self.guiUtility = guiUtility
        self.guiserver = GUITaskQueue.getInstance()
        self.connected = False

        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.dslist = []
        self.magnetlist = {}

        # current progress of download states
        self.cache_progress = {}
        self.last_progress_update = time()
        self.rerankingStrategy = DefaultTorrentReranker()

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

    def _get_videoplayer(self):
        """
        Returns the VideoPlayer instance.
        """
        self.guiUtility.ShowPlayer()
        return VideoPlayer.getInstance()

    def download_state_callback(self, dslist):
        """
        Called by any thread
        """
        self.dslist = dslist
        self.guiserver.add_task(self._do_gui_callback, id="LibraryManager_refresh_callbacks")

        if time() - self.last_progress_update > 10:
            self.last_progress_update = time()
            startWorker(None, self.updateProgressInDB, uId=u"LibraryManager_refresh_callbacks", retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        return self.wantpeers

    def magnet_started(self, infohash):
        self.magnetlist[infohash] = [long(time()), 0, 0]

    def magnet_got_peers(self, infohash, total_peers):
        if infohash not in self.magnetlist:
            self.magnet_started(infohash)
        self.magnetlist[infohash][1] = total_peers

    def magnet_got_piece(self, infohash, progress):
        if infohash not in self.magnetlist:
            self.magnet_started(infohash)
        self.magnetlist[infohash][2] = progress

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

    def updateProgressInDB(self):
        updates = False

        for ds in self.dslist[:]:
            id = ds.get_download().get_def().get_id()
            progress = (ds.get_progress() or 0.0) * 100.0

            # update progress if difference is larger than 5%
            if progress - self.cache_progress.get(id, 0) > 5:
                self.cache_progress[id] = progress
                try:
                    self.mypref_db.updateProgressByHash(id, progress, commit=False)
                    updates = True
                except:
                    print_exc()

        if updates:
            self.mypref_db.commit()

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

    @forceWxThread
    def startLastVODTorrent(self):
        if self.last_vod_torrent:
            self.playTorrent(*self.last_vod_torrent)

    @forceWxThread
    def stopLastVODTorrent(self):
        if self.last_vod_torrent:
            self.stopTorrent(self.last_vod_torrent[0])

    @forceWxThread
    def playTorrent(self, torrent, selectedinfilename=None):
        print >> sys.stderr, "PLAY CLICKED", selectedinfilename

        self.last_vod_torrent = [torrent, selectedinfilename]

        ds = torrent.get('ds')

        # videoplayer calls should be on gui thread, hence forceWxThread
        videoplayer = self._get_videoplayer()
        videoplayer.recreate_videopanel()
        videoplayer.stop_playback()
        videoplayer.show_loading()

        if ds is None:
            torrent_filename = self.torrentsearch_manager.getCollectedFilename(torrent)
            if torrent_filename:
                if torrent.swift_hash:
                    sdef = SwiftDef(torrent.swift_hash, "127.0.0.1:9999")
                else:
                    sdef = None

                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                d = self.guiUtility.frame.startDownload(torrent_filename, sdef=sdef, destdir=defaultDLConfig.get_dest_dir(), vodmode=True, selectedFiles=[selectedinfilename])

            else:
                print >> sys.stderr, ".TORRENT MISSING REQUESTING FROM PEERS"
                callback = lambda: self.playTorrent(torrent, selectedinfilename)
                self.torrentsearch_manager.getTorrent(torrent, callback)
        else:
            videoplayer.play(ds, selectedinfilename)

    def startDownloadFromUrl(self, url, useDefault=False):
        if useDefault:
            dscfg = DefaultDownloadStartupConfig.getInstance()
            destdir = dscfg.get_dest_dir()
        else:
            destdir = None

        if url.startswith("http"):
            self.guiUtility.frame.startDownloadFromUrl(url, destdir)
        elif url.startswith("magnet:"):
            self.guiUtility.frame.startDownloadFromMagnet(url, destdir)

    def resumeTorrent(self, torrent, force_seed=False):
        downloads = self._getDownloads(torrent)
        resumed = False
        for download in downloads:
            if download:
                download.restart()
                resumed = True

                id = download.get_def().get_id()
                self.user_download_choice.set_download_state(id, "restartseed" if force_seed and download.get_progress() == 1.0 else "restart")

        if not resumed:
            filename = self.torrentsearch_manager.getCollectedFilename(torrent)
            if filename:
                tdef = TorrentDef.load(filename)

                destdirs = self.mypref_db.getMyPrefStats(torrent.torrent_id)
                destdir = destdirs.get(torrent.torrent_id, None)
                if destdir:
                    destdir = destdir[-1]
                self.guiUtility.frame.startDownload(tdef=tdef, destdir=destdir)
            else:
                callback = lambda: self.resumeTorrent(torrent)
                self.torrentsearch_manager.getTorrent(torrent, callback)

    def stopTorrent(self, torrent):
        downloads = self._getDownloads(torrent)
        for download in downloads:
            if download:
                if download == self._get_videoplayer().get_vod_download():
                    self._get_videoplayer().stop_playback()

                download.stop()

                id = download.get_def().get_id()
                self.user_download_choice.set_download_state(id, "stop")

    def _getDownloads(self, torrent):
        downloads = []
        for curdownload in self.session.get_downloads():
            id = curdownload.get_def().get_id()
            if id == torrent.infohash or id == torrent.swift_hash:
                downloads.append(curdownload)
        return downloads

    def updateTorrent(self, infohash, roothash):
        self.torrent_db.updateTorrent(infohash, swift_hash=roothash)

        # Niels 09-01-2013: we need to commit now to prevent possibly forgetting the link between this torrent and the roothash
        dispersy = self.session.lm.dispersy
        startWorker(None, dispersy._commit_now)

    def deleteTorrent(self, torrent, removecontent=False):
        if torrent.dslist:
            dslist = torrent.dslist
        else:
            dslist = [None, None]

        for i, ds in enumerate(dslist):
            if i == 0:
                id = torrent.infohash
            else:
                id = torrent.swift_hash
            self.deleteTorrentDS(ds, id, removecontent)

    def deleteTorrentDS(self, ds, infohash, removecontent=False):
        if not ds is None:
            videoplayer = VideoPlayer.getInstance()
            playd = videoplayer.get_vod_download()

            if playd == ds.download:
                self._get_videoplayer().stop_playback()

            self.deleteTorrentDownload(ds.get_download(), infohash, removecontent)

        elif infohash:
            self.deleteTorrentDownload(None, infohash, removecontent)

    def deleteTorrentDownload(self, download, id, removecontent=False, removestate=True):
        if download:
            self.session.remove_download(download, removecontent=removecontent, removestate=removestate)
        else:
            self.session.remove_download_by_id(id, removecontent, removestate)

        if id:
            self.user_download_choice.remove_download_state(id)

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
        if DEBUG:
            begintime = time()

        results = self.torrent_db.getLibraryTorrents(LIBRARY_REQ_COLUMNS)

        if len(results) > 0:
            channelDict = {}
            channels = set((result[0] for result in results))
            if len(channels) > 0:
                _, channels = self.channelsearch_manager.getChannels(channels)
                for channel in channels:
                    channelDict[channel.id] = channel

            def create_torrent(a):
                t = ChannelTorrent(*a[1:-1] + [channelDict.get(a[0], False), None])

                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                t._progress = a[-1] / 100.0
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

        # Niels: maybe create a clever reranking for library results, for now disable
        # results = self.rerankingStrategy.rerank(results, '', self.torrent_db, self.pref_db, self.mypref_db, self.search_db)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took:', time() - begintime

        self.hits = self.addDownloadStates(results)
        return [len(self.hits), self.hits]

    def getTorrentFromInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash, keys=['C.torrent_id', 'infohash', 'swift_hash', 'swift_torrent_hash', 'name', 'torrent_file_name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers'])
        if dict and dict['myDownloadHistory']:
            t = LibraryTorrent(dict['C.torrent_id'], dict['infohash'], dict['swift_hash'], dict['swift_torrent_hash'], dict['name'], dict['torrent_file_name'], dict['length'], dict['category_id'], dict['status_id'], dict['num_seeders'], dict['num_leechers'], None)
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
                print >> sys.stderr, bin2str(infohash), "missing in library"
                return True
        return False

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()


class ChannelManager:
    # Code to make this a singleton
    __single = None

    def __init__(self):
        if ChannelManager.__single:
            raise RuntimeError("ChannelManager is singleton")
        self.connected = False

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
            self.remote_th = RemoteTorrentHandler.getInstance()

            self.dispersy = session.lm.dispersy
        else:
            raise RuntimeError('ChannelManager already connected')

    def set_gridmgr(self, gridmgr):
        self.gridmgr = gridmgr

    def getChannel(self, channel_id):
        channel = self.channelcast_db.getChannel(channel_id)
        return self._getChannel(channel)

    def getChannelByCid(self, channel_cid):
        channel = self.channelcast_db.getChannelByCID(channel_cid)
        return self._getChannel(channel)

    def getChannelByPermid(self, channel_permid):
        channel = self.channelcast_db.getChannelFromPermid(channel_permid)
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

    def getPermidFromChannel(self, channel_id):
        return self.channelcast_db.getPermidForChannel(channel_id)

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

    def getChannnelTorrents(self, infohash, filterTorrents=False):
        hits = self.channelcast_db.getChannelTorrents(infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrents(hits, filterTorrents)

    def getTorrentFromChannelTorrentId(self, channel, channeltorrent_id, collectedOnly=True):
        data = self.channelcast_db.getTorrentFromChannelTorrentId(channeltorrent_id, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel, collectedOnly=collectedOnly)

    def getTorrentsFromChannel(self, channel, filterTorrents=True, limit=None):
        hits = self.channelcast_db.getTorrentsFromChannelId(channel.id, channel.isDispersy(), CHANNEL_REQ_COLUMNS, limit)
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

    def getMostPopularTorrentsFromChannel(self, channel_id, keys, family_filter=False, limit=None):
        return self.channelcast_db.getMostPopularTorrentsFromChannel(channel_id, keys, limit, family_filter)

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

    def getCommentsFromChannel(self, channel, limit=None, resolve_names=True):
        hits = self.channelcast_db.getCommentsFromChannelId(channel.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel=channel)

    def getCommentsFromPlayList(self, playlist, limit=None):
        hits = self.channelcast_db.getCommentsFromPlayListId(playlist.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel=playlist.channel, playlist=playlist)

    def getCommentsFromChannelTorrent(self, channel_torrent, limit=None):
        hits = self.channelcast_db.getCommentsFromChannelTorrentId(channel_torrent.channeltorrent_id, COMMENT_REQ_COLUMNS, limit)
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

    def getMyVote(self, channel):
        return self.votecastdb.getVote(channel.id, None)

    def getSubscribersCount(self, channel):
        return self.channelcast_db.getSubscribersCount(channel.id)

    def _applyFF(self, hits):
        enabled_category_keys = [key.lower() for key, _ in self.category.getCategoryNames()]
        enabled_category_ids = set()
        for key, id in self.torrent_db.category_table.iteritems():
            if key.lower() in enabled_category_keys:
                enabled_category_ids.add(id)
        deadstatus_id = self.torrent_db.status_table['dead']

        def torrentFilter(torrent):
            okCategory = False

            category = torrent.get("category_id", None)
            if not category:
                category = 0

            if category in enabled_category_ids:
                okCategory = True

            if not okCategory:
                self.filteredResults += 1

            okGood = torrent.status_id != deadstatus_id
            return okCategory and okGood

        return filter(torrentFilter, hits)

    @forceAndReturnDispersyThread
    def _disp_get_community_from_channel_id(self, channel_id):
        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()

        if channel_id:
            # 1. get the dispersy identifier from the channel_id
            dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
            dispersy_cid = str(dispersy_cid)

            return self._disp_get_community_from_cid(dispersy_cid)

        print >> sys.stderr, "Could not find channel", channel_id

    @forceAndReturnDispersyThread
    def _disp_get_community_from_cid(self, dispersy_cid):
        try:
            community = self.dispersy.get_community(dispersy_cid)
            return community

        except (KeyError, AttributeError):
            return None

    @forcePrioDispersyThread
    def createChannel(self, name, description):
        community = ChannelCommunity.create_community(self.dispersy, self.session.dispersy_member)
        community.set_channel_mode(ChannelCommunity.CHANNEL_OPEN)
        community.create_channel(name, description)

    @forcePrioDispersyThread
    def createPlaylist(self, channel_id, name, description, infohashes=[]):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.create_playlist(name, description, infohashes)

    @forcePrioDispersyThread
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

    @forcePrioDispersyThread
    def addPlaylistTorrent(self, playlist, torrent):
        if not self.channelcast_db.playlistHasTorrent(playlist.id, torrent.channeltorrent_id):
            community = self._disp_get_community_from_channel_id(playlist.channel.id)
            community.create_playlist_torrents(playlist.id, [torrent.infohash])

    @forceDispersyThread
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
            print >> sys.stderr, "Could not create torrent, no files?", torrent.name, torrent.files, torrent.trackers
            return False

        if not self.channelcast_db.hasTorrent(channel_id, torrent.infohash):
            community = self._disp_get_community_from_channel_id(channel_id)
            community._disp_create_torrent(torrent.infohash, long(time()), torrent.name, tuple(torrent.files), tuple(torrent.trackers))
            return True
        return False

    @forceDispersyThread
    def createTorrentFromDef(self, channel_id, tdef, extraInfo={}, forward=True):
        # Make sure that this new tdef is also in collected torrents
        self.remote_th.save_torrent(tdef)

        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()

        if channel_id and not self.channelcast_db.hasTorrent(channel_id, tdef.infohash):
            community = self._disp_get_community_from_channel_id(channel_id)

            files = tdef.get_files_as_unicode_with_length()
            if len(files) == 0:
                print >> sys.stderr, "Could not create torrent, no files?", tdef.get_name_as_unicode(), files, tdef.get_trackers_as_single_tuple()
                return False

            community._disp_create_torrent(tdef.infohash, long(time()), tdef.get_name_as_unicode(), tuple(files), tdef.get_trackers_as_single_tuple(), forward=forward)

            if 'description' in extraInfo:
                desc = extraInfo['description']
                desc = desc.strip()

                if desc != '':
                    data = self.channelcast_db.getTorrentFromChannelId(channel_id, tdef.infohash, CHANNEL_REQ_COLUMNS)
                    torrent = self._createTorrent(data, False)

                    self.modifyTorrent(channel_id, torrent.channeltorrent_id, {'description': desc}, forward=forward)
            return True
        return False

    @forceDispersyThread
    def createTorrentsFromDefs(self, channel_id, tdefs):
        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()

        if not channel_id:
            print >> sys.stderr, "No channel"
            return

        for tdef in tdefs:
            self.createTorrentFromDef(channel_id, tdef, forward=False)

    @forceDispersyThread
    def removeTorrent(self, channel, infohash):
        torrent = self.getTorrentFromChannel(channel, infohash, collectedOnly=False)
        if torrent:
            community = self._disp_get_community_from_channel_id(channel.id)
            community.remove_torrents([torrent.dispersy_id])

    @forceDispersyThread
    def removeAllTorrents(self, channel):
        _, _, torrents = self.getTorrentsFromChannel(channel, filterTorrents=False)
        dispersy_ids = [torrent.dispersy_id for torrent in torrents if torrent]

        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_torrents(dispersy_ids)

    @forceDispersyThread
    def removePlaylist(self, channel, playlist_id):
        playlist = self.getPlaylist(channel, playlist_id)
        if playlist:
            community = self._disp_get_community_from_channel_id(channel.id)
            community.remove_playlists([playlist.dispersy_id])

            self.removeAllPlaylistTorrents(community, playlist)

    @forceDispersyThread
    def removeAllPlaylists(self, channel):
        _, playlists = self.dispersy_id(channel)
        dispersy_ids = [playlist.dispersy_id for playlist in playlists if playlist]

        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_playlists(dispersy_ids)
        for playlist in playlists:
            self.removeAllPlaylistTorrents(community, playlist)

    @forceDispersyThread
    def removeAllPlaylistTorrents(self, community, playlist):
        sql = "SELECT dispersy_id FROM PlaylistTorrents WHERE playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql, (playlist.id,))
        to_be_removed = [dispersy_id for dispersy_id, in records]

        community.remove_playlist_torrents(playlist.dispersy_id, to_be_removed)

    @forceDispersyThread
    def createComment(self, comment, channel, reply_to=None, reply_after=None, playlist=None, infohash=None):
        comment = comment.strip()
        comment = comment[:1023]
        if len(comment) > 0:
            playlist_id = None
            if playlist:
                playlist_id = playlist.id

            community = self._disp_get_community_from_channel_id(channel.id)
            community.create_comment(comment, long(time()), reply_to, reply_after, playlist_id, infohash)

    @forceDispersyThread
    def removeComment(self, comment, channel):
        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_comment(comment.dispersy_id)

    @forceDispersyThread
    def modifyChannel(self, channel_id, changes):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyChannel(changes)

    @forceDispersyThread
    def modifyPlaylist(self, channel_id, playlist_id, name, description):
        dict = {'name': name, 'description': description}

        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyPlaylist(playlist_id, dict)

    @forceDispersyThread
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

    @forcePrioDispersyThread
    def do_vote_cid(self, dispersy_cid, vote, timestamp=None):
        if not timestamp:
            timestamp = int(time())

        if len(dispersy_cid) == 20:
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    community.disp_create_votecast(dispersy_cid, vote, timestamp)
                    break

    @forcePrioDispersyThread
    def markTorrent(self, channel_id, infohash, type):
        community = self._disp_get_community_from_channel_id(channel_id)
        community._disp_create_mark_torrent(infohash, type, long(time()))

    @forcePrioDispersyThread
    def revertModification(self, channel, moderation, text, severity, revert_to):
        cause = moderation.dispersy_id

        community = self._disp_get_community_from_channel_id(channel.id)
        community._disp_create_moderation(text, long(time()), severity, cause)

    def getChannelForTorrent(self, infohash):
        return self.channelcast_db.getMostPopularChannelFromTorrent(infohash)[:-1]

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
        if DEBUG:
            begintime = time()

        hitsUpdated = self.searchLocalDatabase()
        if DEBUG:
            print >> sys.stderr, 'ChannelManager: getChannelHits: search found: %d items' % len(self.hits)

        try:
            # merge remoteHits
            self.remoteLock.acquire()

            if len(self.remoteHits) > 0:
                for remoteItem, permid in self.remoteHits:

                    channel = None
                    if not isinstance(remoteItem, Channel):
                        channel_id, _, infohash, torrent_name, timestamp = remoteItem

                        if channel_id not in self.hits:
                            channel = self.getChannel(channel_id)
                        else:
                            channel = self.hits[channel_id]

                        torrent = channel.getTorrent(infohash)
                        if not torrent:
                            torrent = RemoteChannelTorrent(torrent_id=None, infohash=infohash, name=torrent_name, channel=channel, query_permids=set())
                            channel.addTorrent(torrent)

                        if not torrent.query_permids:
                            torrent.query_permids = set()
                        torrent.query_permids.add(permid)

                        channel.nr_torrents += 1
                        channel.modified = max(channel.modified, timestamp)
                    else:
                        channel = remoteItem

                    if channel and not channel.id in self.hits:
                        self.hits[channel.id] = channel
                        hitsUpdated = True
        finally:
            self.remoteLock.release()

        if DEBUG:
            print >> sys.stderr, "ChannelManager: getChannelHits took", time() - begintime

        if len(self.hits) == 0:
            return [0, hitsUpdated, None]
        else:
            return [len(self.hits), hitsUpdated, self.hits]

    @forceDispersyThread
    def searchDispersy(self):
        sendSearch = False
        if self.dispersy:
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    sendSearch = community.create_channelsearch(self.searchkeywords, self.gotDispersyRemoteHits)
                    break

        if not sendSearch:
            print >> sys.stderr, "Could not send search, AllChannelCommunity not found?"

    def searchLocalDatabase(self):
        """ Called by GetChannelHits() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            if DEBUG:
                print >> sys.stderr, "ChannelManager: searchLocalDB: returning old hit list", len(self.hits)
            return False

        self.oldsearchkeywords = self.searchkeywords

        if DEBUG:
            print >> sys.stderr, "ChannelManager: searchLocalDB: Want", self.searchkeywords

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

    def gotDispersyRemoteHits(self, kws, answers):
        if self.searchkeywords == kws:
            channel_cids = answers.keys()
            _, dispersyChannels = self.getChannelsByCID(channel_cids)
            try:
                self.remoteLock.acquire()

                for channel in dispersyChannels:
                    self.remoteHits.append((channel, -1))

            finally:
                refreshGrid = len(self.remoteHits) > 0
                if refreshGrid:
                    # if already scheduled, dont schedule another
                    if self.remoteRefresh:
                        refreshGrid = False
                    else:
                        self.remoteRefresh = True

                self.remoteLock.release()

                if refreshGrid:
                    self.refreshGrid()

    def gotRemoteHits(self, permid, kws, answers):
        """ Called by GUIUtil when hits come in. """
        if self.searchkeywords == kws:
            startWorker(None, self._gotRemoteHits, wargs=(permid, kws, answers), retryOnBusy=True, workerType="guiTaskQueue")

    def _gotRemoteHits(self, permid, kws, answers):
        # @param permid: the peer who returned the answer to the query
        # @param kws: the keywords of the query that originated the answer
        # @param answers: the filtered answers returned by the peer (channel_id, publisher_name, infohash, name, time_stamp)

        t1 = time()
        try:
            self.remoteLock.acquire()

            if DEBUG:
                print >> sys.stderr, "ChannelManager: gotRemoteHist: got", len(answers), "for", kws

            if self.searchkeywords == kws:
                for hit in answers.itervalues():
                    self.remoteHits.append((hit, permid))

                    if DEBUG:
                        print >> sys.stderr, 'ChannelManager: gotRemoteHits: Refresh grid after new remote channel hits came in', "Took", time() - t1

            elif DEBUG:
                print >> sys.stderr, "ChannelManager: gotRemoteHits: got hits for", kws, "but current search is for", self.searchkeywords

        finally:
            refreshGrid = len(self.remoteHits) > 0

            if refreshGrid:
                # if already scheduled, dont schedule another
                if self.remoteRefresh:
                    refreshGrid = False
                else:
                    self.remoteRefresh = True

            self.remoteLock.release()

            if refreshGrid:
                self.refreshGrid()

    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh_channel()
