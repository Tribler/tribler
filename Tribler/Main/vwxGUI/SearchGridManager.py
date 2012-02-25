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
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.simpledefs import *
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.community.channel.community import ChannelCommunity,\
    forceDispersyThread, forceAndReturnDispersyThread
from Tribler.Core.dispersy.dispersy import Dispersy

from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Core.Session import Session
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Core.DecentralizedTracking.MagnetLink import MagnetLink 

from math import sqrt
from __init__ import *
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.Core.Search.Bundler import Bundler
from Tribler.Main.Utility.GuiDBTuples import Torrent, ChannelTorrent, CollectedTorrent, RemoteTorrent, getValidArgs, NotCollectedTorrent, LibraryTorrent,\
    Comment, Modification, Channel, RemoteChannel, Playlist, Moderation,\
    RemoteChannelTorrent, Marking
import threading
from copy import copy
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from wx.lib import delayedresult

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
            raise RuntimeError, "TorrentManager is singleton"
        TorrentManager.__single = self
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.hitsLock = threading.Lock()
        
        # Remote results for current keywords
        self.remoteHits = []
        self.remoteLock = threading.Lock()
        self.remoteRefresh = False
        
        # Requests for torrents
        self.requestedTorrents = set()
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.guiserver = GUITaskQueue.getInstance()
        
        self.searchkeywords = []
        self.rerankingStrategy = DefaultTorrentReranker()
        self.oldsearchkeywords = None
        self.fts3feaures = []
        self.fts3negated = []
        
        self.filteredResults = 0
        
        self.bundler = Bundler()
        self.bundle_mode = None
        self.bundle_mode_changed = True
        self.category = Category.getInstance()

    def getInstance(*args, **kw):
        if TorrentManager.__single is None:
            TorrentManager(*args, **kw)       
        return TorrentManager.__single
    getInstance = staticmethod(getInstance)
    
    def getCollectedFilename(self, torrent):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!
        
        Returns a filename, if filename is known
        """
        torrent_dir = self.session.get_torrent_collecting_dir()
        
        torrent_filename = torrent.get('torrent_file_name')
        if not torrent_filename:
            torrent_filename = get_collected_torrent_filename(torrent.infohash)
        torrent_filename = os.path.join(torrent_dir, torrent_filename)
        
        #.torrent found, return complete filename
        if os.path.isfile(torrent_filename):
            return torrent_filename
        
        #.torrent not found, possibly a new torrent_collecting_dir
        torrent_filename = get_collected_torrent_filename(torrent.infohash)
        torrent_filename = os.path.join(torrent_dir, torrent_filename)
        if os.path.isfile(torrent_filename):
            return torrent_filename
        
    def getCollectedFilenameFromDef(self, torrentdef):
        torrent_dir = self.session.get_torrent_collecting_dir()
        
        torrent_filename = get_collected_torrent_filename(torrentdef.infohash)
        return os.path.join(torrent_dir, torrent_filename)
    
    def getTorrent(self, torrent, callback):
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
        
        #.torrent not found, try to download from peers
        peers = torrent.query_permids
        if peers and len(peers) > 0:
            if self.downloadTorrentfileFromPeers(torrent, callback):
                return (True, "from peers")
        
        torrent_dir = self.session.get_torrent_collecting_dir()
        torrent_filename = os.path.join(torrent_dir, get_collected_torrent_filename(torrent.infohash))
        #.torrent still not found, try magnet link
        magnetlink = "magnet:?xt=urn:btih:"+hexlify(torrent.infohash)
        sources = self.torrent_db.getTorrentCollecting(torrent.torrent_id)
        if sources:
            for source, in sources:
                if source.startswith('magnet'):
                    magnetlink = str(source)
                    break
        
        def torrentdef_retrieved(tdef):
            tdef.save(torrent_filename)
            callback(torrent.infohash, torrent, torrent_filename)

        return (TorrentDef.retrieve_from_magnet(magnetlink, torrentdef_retrieved), "from dht")
             
    def downloadTorrentfileFromPeers(self, torrent, callback, duplicate=True, prio = 0):
        """
        TORRENT is a dictionary containing torrent information used to
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
        
        if torrent.query_permids == None or len(torrent.query_permids) == 0:
            self.session.download_torrentfile(torrent.infohash, callback, prio)
            
        else:
            #only add to requestedTorrents if we have peers
            self.requestedTorrents.add(torrent.infohash)
            
            peers = list(torrent.query_permids)
            for permid in peers:
                self.session.download_torrentfile_from_peer(permid, torrent.infohash, callback, prio)
                
        return True
    
    def downloadTorrent(self, torrent, dest = None, secret = False, vodmode = False, selectedFiles = None):
        torrent_filename = self.getCollectedFilename(torrent)
        
        if isinstance(torrent_filename, basestring):
            #got actual filename
            name = torrent.get('name', torrent.infohash)
            clicklog={'keywords': self.searchkeywords,
                      'reranking_strategy': self.rerankingStrategy.getID()}
            
            if torrent.get('name'):
                name = torrent.name
            else:
                name = torrent.infohash
            
            clicklog={'keywords': self.searchkeywords,
                      'reranking_strategy': self.rerankingStrategy.getID()}
            
            if "click_position" in torrent:
                clicklog["click_position"] = torrent["click_position"]
            
            # Api download
            d = self.guiUtility.frame.startDownload(torrent_filename,destdir=dest,clicklog=clicklog,name=name,vodmode=vodmode, selectedFiles = selectedFiles) ## remove name=name
            if d:
                if secret:
                    self.torrent_db.setSecret(torrent.infohash, secret)

                if DEBUG:
                    print >>sys.stderr,'standardDetails: download: download started'
        else:
            callback = lambda infohash, metadata, filename: self.downloadTorrent(torrent, dest, secret, vodmode)
            response = self.getTorrent(torrent, callback)

            if response[0]:
                #torrent is being requested from peers, using callback this function will be called again
                return response[1]
            
            else:
                #torrent not found
                def showdialog():
                    str = self.guiUtility.utility.lang.get('delete_torrent') % torrent['name']
                    dlg = wx.MessageDialog(self.guiUtility.frame, str, self.guiUtility.utility.lang.get('delete_dead_torrent'), 
                                    wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
                    result = dlg.ShowModal()
                    dlg.Destroy()
            
                    if result == wx.ID_YES:
                        infohash = torrent.infohash
                        self.torrent_db.deleteTorrent(infohash, delete_file=True, commit = True)
                wx.CallAfter(showdialog)
    
    def loadTorrent(self, torrent, callback=None):
        if not isinstance(torrent, CollectedTorrent):
            
            torrent_filename = self.getCollectedFilename(torrent)
            if not torrent_filename:
                files = []
                trackers = []
                
                #see if we have most info in our tables
                if torrent.get('torrent_id') is not None:
                    files = self.torrent_db.getTorrentFiles(torrent.torrent_id)
                    
                    collectingSources = self.torrent_db.getTorrentCollecting(torrent.torrent_id)
                    for source, in collectingSources:
                        if source.startswith('magnet'):
                            _, _, trs = MagnetLink.MagnetLink.parse_url(source)
                            trackers.extend(trs)
                
                if len(files) > 0:
                    torrent = NotCollectedTorrent(torrent, files, trackers)
                else:
                    torrent_callback = lambda infohash, metadata, filename: self.loadTorrent(torrent, callback)
                    torrent_filename = self.getTorrent(torrent, torrent_callback)
                    
                    if torrent_filename[0]:
                        return torrent_filename[1]
            else:
                tdef = TorrentDef.load(torrent_filename)
                torrent = CollectedTorrent(torrent, tdef)
            
        if not callback is None:
            callback(torrent)
        else:
            return torrent
    
    def getSwarmInfo(self, infohash):
        return self.torrent_db.getSwarmInfoByInfohash(infohash)
    
    def getTorrentByInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash, keys = ['C.torrent_id', 'infohash', 'name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers'])
        if dict:
            t = Torrent(dict['C.torrent_id'], dict['infohash'], dict['name'], dict['length'], dict['category_id'], dict['status_id'], dict['num_seeders'], dict['num_leechers'], None)
            t.torrent_db = self.torrent_db
            t.channelcast_db = self.channelcast_db
            
            _ = t.channel
            return t 
    
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def connect(self, session, library_manager, channel_manager):
        self.session = session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
        self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
        
        self.library_manager = library_manager
        self.channel_manager = channel_manager
        
    def getSearchSuggestion(self, keywords, limit = 1):
        return self.torrent_db.getSearchSuggestion(keywords, limit)
    
    def getHitsInCategory(self, categorykey = 'all', sort = 'fulltextmetric'):
        if DEBUG: begintime = time()
        # categorykey can be 'all', 'Video', 'Document', ...
        bundle_mode = self.bundle_mode
        
        if DEBUG:
            print >>sys.stderr,"TorrentSearchManager: getHitsInCategory:", categorykey
        
        enabled_category_keys = [key.lower() for key, _ in self.category.getCategoryNames()]
        enabled_category_ids = set()
        for key, id in self.torrent_db.category_table.iteritems():
            if key.lower() in enabled_category_keys:
                enabled_category_ids.add(id)
            
            if key.lower() == categorykey.lower():
                categorykey = id
                
        deadstatus_id = self.torrent_db.status_table['dead']

        def torrentFilter(torrent):
            okCategory = False
            category = torrent.category_id
            if not category:
                category = 0
                
            if categorykey == 'all' and category in enabled_category_ids:
                okCategory = True
            
            elif category == categorykey:
                okCategory = True
            
            if not okCategory:
                self.filteredResults += 1
            
            okGood = torrent.status_id != deadstatus_id
            return okCategory and okGood
        
        try:
            #locking hits variable
            self.hitsLock.acquire()
            
            # 1. Local search puts hits in self.hits
            if DEBUG:
                beginlocalsearch = time()
            new_local_hits = self.searchLocalDatabase()
            
            if DEBUG:
                print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: search found: %d items took %s' % (len(self.hits), time() - beginlocalsearch)
            
            # 2. Add remote hits that may apply.
            new_remote_hits = self.addStoredRemoteResults()
    
            if DEBUG:
                print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items' % len(self.hits)
    
            if DEBUG:
                beginsort = time()
            
            if new_local_hits or new_remote_hits:
                self.hits = filter(torrentFilter, self.hits)
                
                if sort == 'rameezmetric':
                    self.rameezSort()
                    
                elif sort == 'fulltextmetric':
                    self.fulltextSort()
    
                self.hits = self.rerankingStrategy.rerank(self.hits, self.searchkeywords, self.torrent_db, 
                                                            self.pref_db, self.mypref_db, self.search_db)
                
                self.hits = self.library_manager.addDownloadStates(self.hits)
                
                # boudewijn: now that we have sorted the search results we
                # want to prefetch the top N torrents.
                self.guiserver.add_task(self.prefetch_hits, t = 1, id = "PREFETCH_RESULTS")
    
            if DEBUG:
                beginbundle = time()
                
        finally:
            self.hitsLock.release()
        
        # Niels: important, we should not change self.hits otherwise prefetching will not work 
        returned_hits, selected_bundle_mode = self.bundler.bundle(self.hits, bundle_mode, self.searchkeywords)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took: %s of which sort took %s, bundle took %s' % (time() - begintime, beginbundle - beginsort, time() - beginbundle)
        
        bundle_mode_changed = self.bundle_mode_changed or (selected_bundle_mode != bundle_mode)
        self.bundle_mode_changed = False

        return [len(returned_hits), self.filteredResults , new_local_hits or new_remote_hits or bundle_mode_changed, selected_bundle_mode, returned_hits]

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
        if DEBUG: begin_time = time()
        torrent_dir = Session.get_instance().get_torrent_collecting_dir()
        hit_counter = 0
        prefetch_counter = 0

        # prefetch .torrent files if they are from buddycast sources
        for hit in self.hits:
            def sesscb_prefetch_done(infohash, metadata, filename):
                if DEBUG:
                    # find the origional hit
                    for hit in self.hits:
                        if hit.infohash == infohash:
                            print >> sys.stderr, "Prefetch: in", "%.1fs" % (time() - begin_time), hit.name
                            return
                    print >> sys.stderr, "Prefetch BUG. We got a hit from something we didn't ask for"

            torrent_filename = self.getCollectedFilename(hit)
            if not torrent_filename:
                if self.downloadTorrentfileFromPeers(hit, sesscb_prefetch_done, duplicate = False, prio = 1):
                    if DEBUG: print >> sys.stderr, "Prefetch: attempting to download", hit.name
                    prefetch_counter += 1
            else:
                #schedule health check
                TorrentChecking.getInstance().addTorrentToQueue(hit)

            hit_counter += 1
            if prefetch_counter >= 10 or hit_counter >= 25:
                # (1) prefetch a maximum of N hits
                # (2) prefetch only from the first M hits
                # (.) wichever is lowest or (1) or (2)
                break
    
    def getSearchKeywords(self ):
        return self.searchkeywords, len(self.hits), self.filteredResults
    
    def setSearchKeywords(self, wantkeywords, fts3feaures):
        if wantkeywords != self.searchkeywords or fts3feaures != self.fts3feaures:
            try:
                self.hitsLock.acquire()
                self.remoteLock.acquire()
                
                self.bundle_mode = None
                self.searchkeywords = [kw for kw in wantkeywords if kw != '']
                self.fts3feaures = fts3feaures
                self.fts3negated = [kw[1:].lower() for kw in fts3feaures if kw[0] == '-']
                if DEBUG:
                    print >> sys.stderr, "TorrentSearchGridManager: keywords:", self.searchkeywords,"fts3keywords", fts3feaures, ";time:%", time() 
            
                self.filteredResults = 0
                
                self.hits = []
                self.remoteHits = []
                
                self.oldsearchkeywords = None
                self.remoteRefresh = False
            finally:
                self.hitsLock.release()
                self.remoteLock.release()
            
    def setBundleMode(self, bundle_mode):
        if bundle_mode != self.bundle_mode:
            self.bundle_mode = bundle_mode
            self.bundle_mode_changed = True
            self.refreshGrid()

    def searchLocalDatabase(self):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return False
        self.oldsearchkeywords = self.searchkeywords
        
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: Want",self.searchkeywords
        
        if len(self.searchkeywords) == 0 and len(self.fts3feaures) == 0:
            return False
        
        results = self.torrent_db.searchNames(self.searchkeywords + self.fts3feaures)

        if len(results) > 0:
            def create_channel(a):
                if a['channel_id'] and a['channel_name'] != '':
                    return Channel(a['channel_id'], a['channel_cid'], a['channel_name'], a['channel_description'], a['channel_nr_torrents'], a['subscriptions'], a['neg_votes'], a['channel_vote'], a['channel_modified'], a['channel_id'] == self.channelcast_db._channel_id)
                return False
            
            def create_torrent(a):
                a['channel'] = create_channel(a)
                a['playlist'] = None
                a['colt_name'] = a['name']
                
                if a['channel'] and (a['channel'].isFavorite() or a['channel'].isMyChannel()):
                    t = ChannelTorrent(**getValidArgs(ChannelTorrent.__init__, a))
                else:
                    t = Torrent(**getValidArgs(Torrent.__init__, a))
                    
                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                t.assignRelevance(a['matches'])
                return t
            
            results = map(create_torrent, results)
        self.hits = results
        return True

    def addStoredRemoteResults(self):
        """ Called by GetHitsInCategory() to add remote results to self.hits """
        hitsUpdated = False
        try:
            self.remoteLock.acquire()
            
            if len(self.remoteHits) > 0:
                for remoteItem in self.remoteHits:
                    
                    known = False
                    for item in self.hits:
                        if item.infohash == remoteItem['infohash']:
                            if item.query_permids == None:
                                item.query_permids = set()
                            item.query_permids.update(remoteItem['query_permids'])
                            
                            if remoteItem['channel']:
                                if isinstance(item, RemoteTorrent):
                                    self.hits.remove(item) #Replace this item with a new result with a channel
                                    break
                                
                                #Maybe update channel?    
                                if isinstance(item, RemoteChannelTorrent):
                                    this_rating = remoteItem['channel'].nr_favorites - remoteItem['channel'].nr_spam
                                    current_rating = item.channel.nr_favorites - item.channel.nr_spam
                                    if this_rating > current_rating:
                                        item.updateChannel(remoteItem['channel'])
                                
                                    hitsUpdated = True
                            known = True
                            break
                    
                    if not known:
                        if remoteItem.get('channel', False):
                            remoteHit = RemoteChannelTorrent(**getValidArgs(RemoteChannelTorrent.__init__, remoteItem))
                        else:
                            remoteHit = RemoteTorrent(**getValidArgs(RemoteTorrent.__init__, remoteItem))
                        remoteHit.torrent_db = self.torrent_db
                        remoteHit.channelcast_db = self.channelcast_db
                        remoteHit.assignRelevance(remoteItem['matches'])
                        
                        self.hits.append(remoteHit)
                        hitsUpdated = True
                        
                self.remoteHits = []
        except:
            raise
        
        finally:
            self.remoteRefresh = False
            self.remoteLock.release()
        return hitsUpdated
        
    def gotRemoteHits(self, permid, kws, answers):
        """
        Called by GUIUtil when hits come in.

        29/06/11 boudewijn: from now on called on the GUITaskQueue instead on the wx MainThread to
        avoid blocking the GUI because of the database queries.
        """
        if self.searchkeywords == kws:
            startWorker(None, self._gotRemoteHits, wargs=(permid, kws, answers), retryOnBusy=True)

    def _gotRemoteHits(self, permid, kws, answers):
        refreshGrid = False
        try:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got",len(answers),"unfiltered results for",kws, bin2str(permid), time()
            self.remoteLock.acquire()
            
            if self.searchkeywords == kws:
                permid_channelid = self.channelcast_db.getPermChannelIdDict()
                permid_channel = {}
                
                for key,value in answers.iteritems():
                    ignore = False
                    #check fts3 negated values
                    for keyword in self.fts3negated:
                        if value['content_name'].lower().find(keyword) != -1:
                            ignore = True
                            break
                        
                    if not ignore:
                        # Convert answer fields as per 
                        # Session.query_connected_peers() spec. to NEWDB format
                        newval = {}
                        newval['torrent_id'] = -1
                        newval['name'] = value['content_name']
                        newval['infohash'] = key
                        newval['torrent_file_name'] = ''
                        newval['length'] = value['length']
                        newval['creation_date'] = time()  # None  gives '?' in GUI
                        newval['relevance'] = 0
                        newval['source'] = 'RQ'
                        newval['category'] = value['category'][0]
                        newval['category_id'] = self.torrent_db.category_table.get(newval['category'], 0)
                        
                        # We trust the peer
                        newval['status'] = 'good'
                        newval['status_id'] = self.torrent_db.status_table['good']
                        newval['num_seeders'] = value['seeder']
                        newval['num_leechers'] = value['leecher']
    
                        # OLPROTO_VER_NINETH includes a torrent_size. Set to
                        # -1 when not available.
                        newval['torrent_size'] = value.get('torrent_size', -1)
                            
                        # OLPROTO_VER_ELEVENTH includes channel_permid, channel_name fields.
                        if 'channel_permid' not in value:
                            # just to check if it is not OLPROTO_VER_ELEVENTH version
                            # if so, check word boundaries in the swarm name
                            ls = split_into_keywords(value['content_name'])
    
                            if DEBUG:
                                print >>sys.stderr,"TorrentSearchGridManager: ls is",`ls`
                                print >>sys.stderr,"TorrentSearchGridManager: kws is",`kws`
                            
                            flag = False
                            for kw in kws:
                                if kw not in ls:
                                    flag=True
                                    break
                            if flag:
                                continue
                        
                        newval['channel'] = None
                        if value.get('channel_name', '') != '':
                            channel_permid = value['channel_permid']
                            channel_id = permid_channelid.get(channel_permid, None)
                            if channel_id:
                                if channel_permid not in permid_channel:
                                    permid_channel[channel_permid] = self.channel_manager.getChannelByPermid(channel_permid)
                                newval['channel'] = permid_channel[channel_permid]
                            else:
                                newval['channel'] = RemoteChannel(channel_permid, value['channel_name'])
                            
                        # Guess matches
                        keywordset = set(kws)
                        
                        newval['matches'] = {'fileextensions': set()}
                        newval['matches']['swarmname'] = set(split_into_keywords(newval['name'])) & keywordset #all keywords matching in swarmname
                        newval['matches']['filenames'] = keywordset - newval['matches']['swarmname'] #remaining keywords should thus me matching in filenames or fileextensions
                        
                        if len(newval['matches']['filenames']) == 0:
                            _, ext = os.path.splitext(newval['name'])
                            ext = ext[1:]
                            
                            newval['matches']['filenames'] = newval['matches']['swarmname']
                            newval['matches']['filenames'].discard(ext)
                            
                            if ext in keywordset:
                                newval['matches']['fileextensions'].add(ext)
                                
                        # Extra field: Set from which peer this info originates
                        newval['query_permids'] = set([permid])
                            
                        # Store or update self.remoteHits
                        self.remoteHits.append(newval)
                    
                refreshGrid = True
                return True
            
            elif DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHits: got hits for", kws, "but current search is for", self.searchkeywords
            return False
        
        except:
            print_exc()
            return False
        
        finally:
            if refreshGrid:
                #if already scheduled, dont schedule another
                if self.remoteRefresh:
                    refreshGrid = False
                else:
                    self.remoteRefresh = True
            self.remoteLock.release()
            
            if refreshGrid:
                self.refreshGrid()
    
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()

    #Rameez: The following code will call normalization functions and then 
    #sort and merge the torrent results
    def rameezSort(self):
        norm_num_seeders = self.doStatNormalization(self.hits, 'num_seeders')
        norm_neg_votes = self.doStatNormalization(self.hits, 'neg_votes')
        norm_subscriptions = self.doStatNormalization(self.hits, 'subscriptions')

        def score_cmp(a,b):
            info_a = a.infohash
            info_b = b.infohash
            
            # normScores can be small, so multiply
            score_a = 0.8*norm_num_seeders[info_a] - 0.1 * norm_neg_votes[info_a] + 0.1 * norm_subscriptions[info_a]
            score_b = 0.8*norm_num_seeders[info_b] - 0.1 * norm_neg_votes[info_b] + 0.1 * norm_subscriptions[info_b]

            return cmp(score_a, score_b)
           
        self.hits.sort(cmp, reverse = True)
        
    def fulltextSort(self):
        norm_num_seeders = self.doStatNormalization(self.hits, 'num_seeders')
        norm_neg_votes = self.doStatNormalization(self.hits, 'neg_votes')
        norm_subscriptions = self.doStatNormalization(self.hits, 'subscriptions')
        
        for hit in self.hits:
            score = 0.8*norm_num_seeders[hit.infohash] - 0.1 * norm_neg_votes[hit.infohash] + 0.1 * norm_subscriptions[hit.infohash]
            hit.relevance_score[-1] = score
           
        self.hits.sort(key=lambda hit:hit.relevance_score, reverse = True)

    def doStatNormalization(self, hits, normKey):
        '''Center the variance on zero (this means mean == 0) and divide
        all values by the standard deviation. This is sometimes called scaling.
        This is done on the field normKey of hits.'''
        
        tot = 0
        for hit in hits:
            tot += (hit.get(normKey, 0) or 0)
        
        if len(hits) > 0:
            mean = tot/len(hits)
        else:
            mean = 0
        
        sum = 0
        for hit in hits:
            temp = (hit.get(normKey, 0) or 0) - mean
            temp = temp * temp
            sum += temp
        
        if len(hits) > 1:
            dev = sum /(len(hits)-1)
        else:
            dev = 0
        
        stdDev = sqrt(dev)
        
        return_dict = {}
        for hit in hits:
            if stdDev > 0:
                return_dict[hit.infohash] = ((hit.get(normKey, 0) or 0) - mean)/ stdDev
            else:
                return_dict[hit.infohash] = 0
        return return_dict
                
class LibraryManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self, guiUtility):
        if LibraryManager.__single:
            raise RuntimeError, "LibraryManager is singleton"
        LibraryManager.__single = self
        self.guiUtility = guiUtility
        self.guiserver = GUITaskQueue.getInstance()
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        self.dslist = []
        
        #current progress of download states
        self.cache_progress = {}
        self.last_progress_update = time()
        self.rerankingStrategy = DefaultTorrentReranker()
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        
        # Gui callbacks
        self.gui_callback = []
        self.user_download_choice = UserDownloadChoice.get_singleton()

    def getInstance(*args, **kw):
        if LibraryManager.__single is None:
            LibraryManager(*args, **kw)       
        return LibraryManager.__single
    getInstance = staticmethod(getInstance)

    def _get_videoplayer(self, exclude=None):
        """
        Returns the VideoPlayer instance and ensures that it knows if
        there are other downloads running.
        """
        other_downloads = False
        for ds in self.dslist:
            if ds is not exclude and ds.get_status() not in (DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR):
                other_downloads = True
                break
        
        videoplayer = VideoPlayer.getInstance()
        videoplayer.set_other_downloads(other_downloads)
        
        self.guiUtility.ShowPlayer(True)
        return videoplayer
        
    def download_state_callback(self, dslist):
        """
        Called by any thread
        """
        self.dslist = dslist
        self.guiserver.add_task(self._do_gui_callback, id = "LibraryManager_refresh_callbacks")
        
        if time() - self.last_progress_update > 10:
            self.last_progress_update = time()
            startWorker(None, self.updateProgressInDB, uId="LibraryManager_refresh_callbacks", retryOnBusy=True)
    
    @forceWxThread
    def _do_gui_callback(self):
        dslist = self.dslist[:]
        
        for callback in self.gui_callback:
            try:
                callback(dslist)
            except:
                print_exc()
    
    def updateProgressInDB(self):
        updates = False
        
        for ds in self.dslist[:]:
            infohash = ds.get_download().get_def().get_infohash()
            
            progress = (ds.get_progress() or 0.0) * 100.0
            #update progress if difference is larger than 5%
            if progress - self.cache_progress.get(infohash, 0) > 5:
                self.cache_progress[infohash] = progress
                try:
                    self.mypref_db.updateProgress(infohash, progress, commit = False)
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
    
    def addDownloadState(self, torrent):
        # Add downloadstate data to a torrent instance
        for ds in self.dslist:
            try:
                infohash = ds.get_download().get_def().get_infohash()
                if torrent.infohash == infohash:
                    torrent.ds = ds
                    break
            except:
                pass
        return torrent
    
    def addDownloadStates(self, torrentlist):
        if len(torrentlist) > 0:
            infohash_ds = {}
            for ds in self.dslist:
                try:
                    infohash = ds.get_download().get_def().get_infohash()
                    infohash_ds[infohash] = ds
                except:
                    pass
                
            for torrent in torrentlist:
                if torrent.infohash in infohash_ds:
                    torrent.ds = infohash_ds[torrent.infohash]
        return torrentlist
    
    def playTorrent(self, torrent, selectedinfilename = None):
        ds = torrent.get('ds')
        
        videoplayer = self._get_videoplayer(ds)
        videoplayer.stop_playback()
        videoplayer.show_loading()
        
        if ds is None:
            filename = self.torrentsearch_manager.getCollectedFilename(torrent)
            if filename:
                tdef = TorrentDef.load(filename)
                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()
                videoplayer.start_and_play(tdef, dscfg, selectedinfilename)
                
            else:
                callback = lambda infohash, metadata, filename: self.playTorrent(torrent)
                self.torrentsearch_manager.getTorrent(torrent, callback)
        else:
            videoplayer.play(ds, selectedinfilename)
    
    def resumeTorrent(self, torrent):
        download = None
        if torrent.ds:
            download = torrent.ds.get_download()
        
        if not download:
            session = self.guiUtility.utility.session
            for curdownload in session.get_downloads():
                if curdownload.get_def().get_infohash() == torrent.infohash:
                    download = curdownload
                    break
        
        if download:
            download.restart()
            
        else:
            filename = self.torrentsearch_manager.getCollectedFilename(torrent)
            if filename:
                tdef = TorrentDef.load(filename)
                
                destdirs = self.mypref_db.getMyPrefStats(torrent.torrent_id)
                destdir = destdirs.get(torrent.torrent_id, None)
                self.guiUtility.frame.startDownload(tdef=tdef, destdir=destdir)
            else:
                callback = lambda infohash, metadata, filename: self.resumeTorrent(torrent)
                self.torrentsearch_manager.getTorrent(torrent, callback)
    
    def deleteTorrent(self, torrent, removecontent = False):
        self.deleteTorrentDS(torrent.ds, torrent.infohash, removecontent)
    
    def deleteTorrentDS(self, ds, infohash, removecontent = False):
        if not ds is None:
            videoplayer = VideoPlayer.getInstance()
            playd = videoplayer.get_vod_download()
            
            if playd == ds.download:
                self._get_videoplayer(ds).stop_playback()
            
            self.deleteTorrentDownload(ds.get_download(), infohash, removecontent)
        else:
            self.deleteTorrentDownload(None, infohash, removecontent)
        
    def deleteTorrentDownload(self, download, infohash, removecontent = False, removestate = True):
        if download:
            self.session.remove_download(download, removecontent = removecontent, removestate = removestate)
        else:
            self.session.remove_download_by_infohash(infohash, removecontent, removestate)
        
        if infohash:
            # Johan, 2009-03-05: we need long download histories for good 
            # semantic clustering.
            # Arno, 2009-03-10: Not removing it from MyPref means it keeps showing
            # up in the Library, even after removal :-( H4x0r this.
            self.mypref_db.updateDestDir(infohash,"")
            self.user_download_choice.remove_download_state(infohash)
    
    def connect(self, session, torrentsearch_manager):
        self.session = session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.torrentsearch_manager = torrentsearch_manager
    
    def getHitsInCategory(self):
        if DEBUG: begintime = time()
        
        results = self.torrent_db.getTorrents(sort = "name", library = True)
        if len(results) > 0:
            def create_torrent(a):
                t = LibraryTorrent(**getValidArgs(LibraryTorrent.__init__, a))
                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                
                #touch channel to force load
                t.channel
                
                return t
            
            results = map(create_torrent, results)
        
        #Niels: maybe create a clever reranking for library results, for now disable
        #results = self.rerankingStrategy.rerank(results, '', self.torrent_db, self.pref_db, self.mypref_db, self.search_db)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took:', time() - begintime
            
        self.hits = self.addDownloadStates(results)
        return [len(self.hits), 0 , self.hits]
       
    def getTorrentFromInfohash(self, infohash):
        dict = self.torrent_db.getTorrent(infohash, keys = ['C.torrent_id', 'infohash', 'name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers'])
        if dict and dict['myDownloadHistory']:
            t = LibraryTorrent(dict['C.torrent_id'], dict['infohash'], dict['name'], dict['length'], dict['category_id'], dict['status_id'], dict['num_seeders'], dict['num_leechers'], None)
            t.torrent_db = self.torrent_db
            t.channelcast_db = self.channelcast_db
            
            #touch channel to force load
            t.channel
            return t
    
    def exists(self, infohashes):
        prefrerences = self.mypref_db.getMyPrefListInfohash(returnDeleted = False)
        for infohash in infohashes:
            if infohash not in prefrerences:
                return False
        return True

    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()

class ChannelManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self):
        if ChannelManager.__single:
            raise RuntimeError, "ChannelManager is singleton"
        ChannelManager.__single = self
        
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
            ChannelManager(*args, **kw)       
        return ChannelManager.__single
    getInstance = staticmethod(getInstance)

    def connect(self, session, torrentsearch_manager):
        self.session = session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = self.session.open_dbhandler(NTFY_VOTECAST)
        self.torrentsearch_manager = torrentsearch_manager

        if Dispersy.has_instance():
            self.dispersy = Dispersy.get_instance()
            self.dispersy.database.attach_commit_callback(self.channelcast_db.commit)

        else:
            def dispersy_started(subject,changeType,objectID):
                self.dispersy = Dispersy.get_instance()
                self.dispersy.database.attach_commit_callback(self.channelcast_db.commit)
                
                self.session.remove_observer(dispersy_started)
            
            self.session.add_observer(dispersy_started,NTFY_DISPERSY,[NTFY_STARTED])
        
    def set_gridmgr(self,gridmgr):
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
            
            #check if we need to convert our vote
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
    
    def _createChannel(self, hit):
        return Channel(*hit+(hit[0] == self.channelcast_db._channel_id,))
    
    def _createChannels(self, hits, filterTorrents = True):
        channels = []
        for hit in hits:
            channel = Channel(*hit+(hit[0] == self.channelcast_db._channel_id,))
            channels.append(channel)
        
        self.filteredResults = 0
        if filterTorrents:
            channels = self._applyChannelFF(channels)
        return len(channels), self.filteredResults, channels
    
    def getTorrentMarkings(self, channeltorrent_id):
        return self.channelcast_db.getTorrentMarkings(channeltorrent_id)
    
    def getTorrentFromChannel(self, channel, infohash, collectedOnly = True):
        data = self.channelcast_db.getTorrentFromChannelId(channel.id, infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel, collectedOnly)
    
    def getChannnelTorrents(self, infohash, filterTorrents = False):
        hits = self.channelcast_db.getChannelTorrents(infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrents(hits, filterTorrents)
    
    def getTorrentFromChannelTorrentId(self, channel, channeltorrent_id):
        data = self.channelcast_db.getTorrentFromChannelTorrentId(channeltorrent_id, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel)
    
    def getTorrentsFromChannel(self, channel, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getTorrentsFromChannelId(channel.id, channel.isDispersy(), CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {channel.id : channel})
    
    def getRecentReceivedTorrentsFromChannel(self, channel, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getRecentReceivedTorrentsFromChannelId(channel.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {channel.id : channel})

    def getTorrentsNotInPlaylist(self, channel, filterTorrents = True):
        hits = self.channelcast_db.getTorrentsNotInPlaylist(channel.id, CHANNEL_REQ_COLUMNS)
        results = self._createTorrents(hits, filterTorrents, {channel.id : channel})
        
        if isinstance(channel, RemoteChannel):
            if len(results) == 0:
                return channel.torrents
        return results
        
    def getTorrentsFromPlaylist(self, playlist, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id : playlist.channel}, playlist)

    def getTorrentFromPlaylist(self, playlist, infohash):
        data = self.channelcast_db.getTorrentFromPlaylist(playlist.id, infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, playlist.channel, playlist)
    
    def getRecentTorrentsFromPlaylist(self, playlist, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getRecentTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id : playlist.channel}, playlist)
    
    def populateWithPlaylists(self, torrents):
        torrentdict = {}
        for torrent in torrents:
            torrentdict[torrent.channeltorrent_id] = torrent

        hits = self.channelcast_db.getPlaylistsForTorrents(torrentdict.keys(), PLAYLIST_REQ_COLUMNS)
        for hit in hits:
            torrent = torrentdict[hit[0]]
            playlist = Playlist(*hit[1:]+(torrent.channel,))
            torrent.playlist = playlist
    
    def _createTorrent(self, tuple, channel, playlist = None, collectedOnly = True):
        if tuple:
            ct = ChannelTorrent(*tuple[1:]+[channel, playlist])
            ct.torrent_db = self.torrent_db
            ct.channelcast_db = self.channelcast_db
            
            #Only return ChannelTorrent with a name, old not-collected torrents 
            #will be filtered due to this
            if not collectedOnly or ct.name:
                return ct
        
    def _createTorrents(self, hits, filterTorrents, channel_dict = {}, playlist = None):
        fetch_channels = set(hit[0] for hit in hits if hit[0] not in channel_dict)
        if len(fetch_channels) > 0:
            _,_,channels = self.getChannels(fetch_channels)
            for channel in channels:
                channel_dict[channel.id] = channel
        
        torrents = []
        for hit in hits:
            torrent = self._createTorrent(hit, channel_dict.get(hit[0], None), playlist)
            if torrent: 
                torrents.append(torrent)
                
        self.filteredResults = 0
        if filterTorrents:
            torrents = self._applyFF(torrents)
        return len(torrents), self.filteredResults, torrents

    def getTorrentModifications(self, torrent):
        data = self.channelcast_db.getTorrentModifications(torrent.channeltorrent_id, MODIFICATION_REQ_COLUMNS)
        return self._createModifications(data)
    
    def getRecentModificationsFromChannel(self, channel, limit = None):
        data = self.channelcast_db.getRecentModificationsFromChannelId(channel.id, MODIFICATION_REQ_COLUMNS, limit)
        return self._createModifications(data)

    def getRecentModificationsFromPlaylist(self, playlist, limit = None):
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
            #touch torrent property to load torrent
            mod.torrent
            
            returnList.append(mod)
            
        return returnList
    
    def getRecentModerationsFromChannel(self, channel, limit = None):
        data = self.channelcast_db.getRecentModerationsFromChannel(channel.id, MODERATION_REQ_COLUMNS, limit)
        return self._createModerations(data)

    def getRecentModerationsFromPlaylist(self, playlist, limit = None):
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
                
                #touch torrent property to load torrent
                modification.torrent
                
                mod.modification = modification
            returnList.append(mod)
            
        return returnList
    
    def getRecentMarkingsFromChannel(self, channel, limit = None):
        data = self.channelcast_db.getRecentMarkingsFromChannel(channel.id, MARKING_REQ_COLUMNS, limit)
        return self._createMarkings(data)

    def getRecentMarkingsFromPlaylist(self, playlist, limit = None):
        data = self.channelcast_db.getRecentMarkingsFromPlaylist(playlist.id, MARKING_REQ_COLUMNS, limit)
        return self._createMarkings(data)
    
    def _createMarkings(self, hits):
        returnList = []
        for hit in hits:
            mar = Marking(*hit[:5])
            mar.get_nickname = self.session.get_nickname
            
            #touch torrent property to load torrent
            mar.torrent
            
            returnList.append(mar)
            
        return returnList
    
    def getCommentsFromChannel(self, channel, limit = None, resolve_names = True):
        hits = self.channelcast_db.getCommentsFromChannelId(channel.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel = channel)

    def getCommentsFromPlayList(self, playlist, limit = None):
        hits = self.channelcast_db.getCommentsFromPlayListId(playlist.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel = playlist.channel, playlist = playlist)
            
    def getCommentsFromChannelTorrent(self, channel_torrent, limit = None):
        hits = self.channelcast_db.getCommentsFromChannelTorrentId(channel_torrent.channeltorrent_id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits, channel=channel_torrent.channel, channel_torrent=channel_torrent)
        
    def _createComments(self, hits, channel = None, playlist = None, channel_torrent = None):
        hitsDict = {}
        hitsSequence = []
        for hit in hits:
            comment = Comment(*(hit+(channel, playlist, channel_torrent)))
            
            comment.get_nickname = self.session.get_nickname
            comment.get_mugshot = self.session.get_mugshot
            
            #touch torrent property to load torrent
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
    
    def _createPlaylist(self, hit, channel = None):
        pl = Playlist(*(hit+(channel, )))
        
        #touch extended_description property to possibly load torrents
        pl.extended_description
        return pl 
    
    def _createPlaylists(self, hits, channel = None):
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
    
    def _applyChannelFF(self, channels):
        enabled_category_keys = [key.lower() for key, _ in self.category.getCategoryNames()]
        
        #only check XXX category
        if 'xxx' in enabled_category_keys:
            return channels
        
        def channelFilter(channel):
            isXXX = self.category.xxx_filter.isXXX(channel.name, False)
            return not isXXX
        return filter(channelFilter, channels) 
    
    @forceAndReturnDispersyThread
    def _disp_get_community_from_channel_id(self, channel_id):
        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()
        
        if channel_id:
            # 1. get the dispersy identifier from the channel_id
            dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
            dispersy_cid = str(dispersy_cid)

            return self._disp_get_community_from_cid(dispersy_cid)
        
        print >> sys.stderr, "Could not find channel",channel_id
    
    @forceAndReturnDispersyThread
    def _disp_get_community_from_cid(self, dispersy_cid):
        try:
            community = self.dispersy.get_community(dispersy_cid)
            return community
        
        except (KeyError, AttributeError):
            return None
    
    @forceDispersyThread
    def createChannel(self, name, description):
        community = ChannelCommunity.create_community(self.session.dispersy_member)
        community.set_channel_mode(ChannelCommunity.CHANNEL_OPEN)
        community.create_channel(name, description)
    
    @forceDispersyThread
    def createPlaylist(self, channel_id, name, description, infohashes = []):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.create_playlist(name, description, infohashes)
    
    @forceDispersyThread
    def savePlaylistTorrents(self, channel_id, playlist_id, infohashes):
        #detect changesmodification
        to_be_created = set(infohashes)
        to_be_removed = set()
        
        sql = "SELECT distinct infohash, PL.dispersy_id FROM PlaylistTorrents PL, ChannelTorrents CT, Torrent T WHERE PL.channeltorrent_id = CT.id AND CT.torrent_id = T.torrent_id AND playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql,(playlist_id,))
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
               
    @forceDispersyThread 
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
    def createTorrentFromDef(self, channel_id, tdef, extraInfo = {}, forward = True):
        if not channel_id:
            channel_id = self.channelcast_db.getMyChannelId()
            
        if channel_id and not self.channelcast_db.hasTorrent(channel_id, tdef.infohash):
            community = self._disp_get_community_from_channel_id(channel_id)
            
            files = tdef.get_files_as_unicode_with_length()
            if len(files) == 0:
                print >> sys.stderr, "Could not create torrent, no files?", tdef.get_name_as_unicode(), files, tdef.get_trackers_as_single_tuple()
                return False
            
            community._disp_create_torrent(tdef.infohash, long(time()), tdef.get_name_as_unicode(), tuple(files), tdef.get_trackers_as_single_tuple(), forward = forward)
            
            if 'description' in extraInfo:
                desc = extraInfo['description']
                desc = desc.strip()
                
                if desc != '':
                    data = self.channelcast_db.getTorrentFromChannelId(channel_id, tdef.infohash, CHANNEL_REQ_COLUMNS)
                    torrent = self._createTorrent(data, False)
                    
                    self.modifyTorrent(channel_id, torrent.channeltorrent_id, {'description': desc}, forward = forward)
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
            self.createTorrentFromDef(channel_id, tdef, forward = False)
            
    @forceDispersyThread
    def removeTorrent(self, channel, infohash):
        torrent = self.getTorrentFromChannel(channel, infohash, collectedOnly = False)
        if torrent:
            community = self._disp_get_community_from_channel_id(channel.id)
            community.remove_torrents([torrent.dispersy_id])
    
    @forceDispersyThread
    def removeAllTorrents(self, channel):
        _,_,torrents = self.getTorrentsFromChannel(channel, filterTorrents=False)
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
        _,playlists = self.dispersy_id(channel)
        dispersy_ids = [playlist.dispersy_id for playlist in playlists if playlist]
        
        community = self._disp_get_community_from_channel_id(channel.id)
        community.remove_playlists(dispersy_ids)
        for playlist in playlists:
            self.removeAllPlaylistTorrents(community, playlist)
    
    @forceDispersyThread
    def removeAllPlaylistTorrents(self, community, playlist):
        sql = "SELECT dispersy_id FROM PlaylistTorrents WHERE playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql,(playlist.id,))
        to_be_removed = [dispersy_id for dispersy_id, in records]
        
        community.remove_playlist_torrents(playlist.dispersy_id, to_be_removed)
    
    @forceDispersyThread
    def createComment(self, comment, channel, reply_to = None, reply_after = None, playlist = None, infohash = None):
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
        dict = {'name':name, 'description':description}
        
        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyPlaylist(playlist_id, dict)

    @forceDispersyThread    
    def modifyTorrent(self, channel_id, channeltorrent_id, dict_changes, forward = True):
        community = self._disp_get_community_from_channel_id(channel_id)
        community.modifyTorrent(channeltorrent_id, dict_changes, forward = forward)
    
    def spam(self, channel_id):
        self.do_vote(channel_id, -1)
        
    def favorite(self, channel_id):
        self.do_vote(channel_id, 2)
    
    def remove_vote(self, channel_id):
        self.do_vote(channel_id, 0)
        
    def do_vote(self, channel_id, vote, timestamp = None):
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
    
    @forceDispersyThread
    def do_vote_cid(self, dispersy_cid, vote, timestamp = None):
        if not timestamp:
            timestamp = int(time())
        
        if len(dispersy_cid) == 20:
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    community._disp_create_votecast(dispersy_cid, vote, timestamp)
                    break
                
    @forceDispersyThread
    def markTorrent(self, channel_id, infohash, type):
        community = self._disp_get_community_from_channel_id(channel_id)
        community._disp_create_mark_torrent(infohash, type, long(time()))
        
    @forceDispersyThread
    def revertModification(self, channel, moderation, text, severity, revert_to):
        cause = moderation.dispersy_id
        
        community = self._disp_get_community_from_channel_id(channel.id)
        community._disp_create_moderation(text, long(time()), severity, cause)
        
    def getChannelForTorrent(self, infohash):
        return self.channelcast_db.getMostPopularChannelFromTorrent(infohash)
    
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
        try:
            self.searchDispersy()
        except TypeError:
            #Dispersy not loaded yet
            pass
        
    def getChannelHits(self):
        hitsUpdated = self.searchLocalDatabase()
        if DEBUG:
            print >>sys.stderr,'ChannelManager: getChannelHits: search found: %d items' % len(self.hits)
            
        try:
            #merge remoteHits 
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
                            torrent = RemoteChannelTorrent(torrent_id = None, infohash = infohash, name = torrent_name, channel = channel, query_permids = set())
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

        if len(self.hits) == 0:
            return [0, hitsUpdated, None]
        else:
            nrNonEmpty = 0
            for hit in self.hits.itervalues():
                if not hit.isEmpty():
                    nrNonEmpty += 1
            
            return [nrNonEmpty, hitsUpdated, self.hits]
    
    @forceDispersyThread 
    def searchDispersy(self):
        sendSearch = False
        if self.dispersy:
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    community.create_channelsearch(self.searchkeywords, self.gotDispersyRemoteHits)
                    sendSearch = True
                    break
            
        if not sendSearch:
            print >> sys.stderr, "Could not send search, AllChannelCommunity not found?"
    
    def searchLocalDatabase(self):
        """ Called by GetChannelHits() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords:
            if DEBUG:
                print >>sys.stderr,"ChannelManager: searchLocalDB: returning old hit list", len(self.hits)
            return False
        
        self.oldsearchkeywords = self.searchkeywords
        
        if DEBUG:
            print >>sys.stderr,"ChannelManager: searchLocalDB: Want",self.searchkeywords
     
        if len(self.searchkeywords) == 0 or len(self.searchkeywords) == 1 and self.searchkeywords[0] == '':
            return False

        self.hits = {}
        hits = self.channelcast_db.searchChannels(self.searchkeywords)
        _,_,channels = self._createChannels(hits)
        
        for channel in channels:
            self.hits[channel.id] = channel
        return True
    
    def gotDispersyRemoteHits(self, kws, answers):
        if self.searchkeywords == kws:
            channel_cids = answers.keys()
            _,_,dispersyChannels = self.getChannelsByCID(channel_cids)
            try:
                self.remoteLock.acquire()
                
                for channel in dispersyChannels:
                    self.remoteHits.append((channel, -1))
                    
            finally:
                refreshGrid = len(self.remoteHits) > 0
                if refreshGrid:
                    #if already scheduled, dont schedule another
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
            startWorker(None, self._gotRemoteHits, wargs=(permid, kws, answers), retryOnBusy=True)

    def _gotRemoteHits(self, permid, kws, answers):
        # @param permid: the peer who returned the answer to the query
        # @param kws: the keywords of the query that originated the answer
        # @param answers: the filtered answers returned by the peer (channel_id, publisher_name, infohash, name, time_stamp)
        
        t1 = time()
        try:
            self.remoteLock.acquire()
            
            if DEBUG:
                print >>sys.stderr,"ChannelManager: gotRemoteHist: got",len(answers),"for",kws

            if self.searchkeywords == kws:
                for hit in answers.itervalues():
                    self.remoteHits.append((hit, permid))
                    
                    if DEBUG:
                        print >>sys.stderr,'ChannelManager: gotRemoteHits: Refresh grid after new remote channel hits came in', "Took", time() - t1
            
            elif DEBUG:
                print >>sys.stderr,"ChannelManager: gotRemoteHits: got hits for",kws,"but current search is for",self.searchkeywords
        
        finally:
            refreshGrid = len(self.remoteHits) > 0
            
            if refreshGrid:
                #if already scheduled, dont schedule another
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
