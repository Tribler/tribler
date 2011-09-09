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
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL,\
    safenamedtuple
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.simpledefs import *
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.community.channel.community import ChannelCommunity
from Tribler.Core.dispersy.dispersy import Dispersy

from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Core.Session import Session
from Tribler.Video.utils import videoextdefaults
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Core.DecentralizedTracking.MagnetLink import MagnetLink 

from math import sqrt
from __init__ import *
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.Core.Search.Bundler import Bundler
from Tribler.Main.Utility.GuiDBHandler import startWorker
from collections import namedtuple
from Tribler.Main.Utility.GuiDBTuples import Torrent, ChannelTorrent, CollectedTorrent, RemoteTorrent, getValidArgs, NotCollectedTorrent, LibraryTorrent,\
    Comment, Modification, Channel
import threading

DEBUG = False

SEARCHMODE_STOPPED = 1
SEARCHMODE_SEARCHING = 2
SEARCHMODE_NONE = 3
VOTE_LIMIT = -5

class TorrentManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if TorrentManager.__single:
            raise RuntimeError, "TorrentSearchGridManager is singleton"
        TorrentManager.__single = self
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        
        # Remote results for current keywords
        self.remoteHits = []
        self.remoteLock = threading.Lock()
        
        # Requests for torrents
        self.requestedTorrents = set()
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.guiserver = GUITaskQueue.getInstance()
        
        self.searchkeywords = []
        self.rerankingStrategy = DefaultTorrentReranker()
        self.oldsearchkeywords = []
        
        self.filteredResults = 0
        
        self.bundler = Bundler()
        self.bundle_mode = None
        self.bundle_mode_changed = True
        self.category = Category.getInstance()
        
        # 09/10/09 boudewijn: CallLater does not accept zero as a
        # delay. the value needs to be a positive integer.
        self.prefetch_callback = wx.CallLater(10, self.prefetch_hits)

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
        torrent_dir = self.guiUtility.utility.session.get_torrent_collecting_dir()
        
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
        if self.downloadTorrentfileFromPeers(torrent, callback):
            return (True, "from peers")
        
        torrent_dir = self.guiUtility.utility.session.get_torrent_collecting_dir()
        torrent_filename = os.path.join(torrent_dir, get_collected_torrent_filename(torrent['infohash']))
        
        #.torrent still not found, try magnet link
        magnetlink = "magnet:?xt=urn:btih:"+hexlify(torrent['infohash'])
        sources = self.torrent_db.getTorrentCollecting(torrent['torrent_id'])
        if sources:
            for source, in sources:
                if source.startswith('magnet'):
                    magnetlink = str(source)
                    break
        
        def torrentdef_retrieved(tdef):
            tdef.save(torrent_filename)
            callback(torrent['infohash'], torrent, torrent_filename)

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
        
        self.requestedTorrents.add(torrent.infohash)
        
        peers = torrent.get('query_permids', [])
        if len(peers) == 0:
            self.guiUtility.utility.session.download_torrentfile(torrent.infohash, callback, prio)
        else:
            for permid in peers:
                self.guiUtility.utility.session.download_torrentfile_from_peer(permid, torrent.infohash, callback, prio)
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
                #torrent cannot be requested
                str = self.guiUtility.utility.lang.get('delete_torrent') % torrent.name
                dlg = wx.MessageDialog(self.guiUtility.frame, str, self.guiUtility.utility.lang.get('delete_dead_torrent'), 
                                    wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
                result = dlg.ShowModal()
                dlg.Destroy()
                
                if result == wx.ID_YES:
                    self.torrent_db.deleteTorrent(torrent.infohash, delete_file=True, commit = True)
    
    def loadTorrent(self, torrent, callback=None):
        if not isinstance(torrent, CollectedTorrent):
            
            torrent_filename = self.getCollectedFilename(torrent)
            if not torrent_filename:
                #see if we have most info in our tables
                if torrent.get('torrent_id') is not None:
                    files = self.torrent_db.getTorrentFiles(torrent.torrent_id)
                    
                    trackers = []
                    collectingSources = self.torrent_db.getTorrentCollecting(torrent.torrent_id)
                    for source, in collectingSources:
                        if source.startswith('magnet'):
                            _, _, trs = MagnetLink.MagnetLink.parse_url(source)
                            trackers.append(trs)
                    
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
            channel = self.channelcast_db.getMostPopularChannelFromTorrent(infohash)
            if not channel:
                channel = 0, '', '', 0, 0
            
            t = Torrent(dict['C.torrent_id'], dict['infohash'], dict['name'], dict['length'], dict['category_id'], dict['status_id'], dict['num_seeders'], dict['num_leechers'], channel[0], channel[1], channel[2], channel[3], channel[4])
            t.torrent_db = self.torrent_db
            return t 
    
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def connect(self):
        session = self.guiUtility.utility.session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
        self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
        self.library_manager = self.guiUtility.library_manager
    
    def getHitsInCategory(self, categorykey = 'all', sort = 'rameezmetric'):
        if DEBUG: begintime = time()
        # categorykey can be 'all', 'Video', 'Document', ...
        bundle_mode = self.bundle_mode
        
        if DEBUG:
            print >>sys.stderr,"TorrentSearchManager: getHitsInCategory:", categorykey, range
        
        enabled_category_keys = [key.lower() for key in self.category.getCategoryKeys()]
        enabled_category_ids = set()
        for key, id in self.torrent_db.category_table.iteritems():
            if key.lower() in enabled_category_keys:
                enabled_category_ids.add(id)
            
            if key.lower() == categorykey.lower():
                categorykey = id
                
        deadstatus_id = self.torrent_db.status_table['dead']

        def torrentFilter(torrent):
            okCategory = False
            category = torrent.get("category_id", None)
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
        
        # 1. Local search puts hits in self.hits
        if DEBUG:
            beginlocalsearch = time()
        new_local_hits = self.searchLocalDatabase()
        
        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: search found: %d items took %s' % (len(self.hits), time() - beginlocalsearch)

        # 2. Filter self.hits on category and status
        if DEBUG:
            beginfilterhits = time()
            
        if new_local_hits:
            self.hits = filter(torrentFilter, self.hits)

        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: torrentFilter after filter found: %d items took %s' % (len(self.hits), time() - beginfilterhits)
        
        # 3. Add remote hits that may apply.
        new_remote_hits = self.addStoredRemoteResults()

        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items' % len(self.hits)

        if DEBUG:
            beginsort = time()
        
        if sort == 'rameezmetric':
            self.sort()

        self.hits = self.rerankingStrategy.rerank(self.hits, self.searchkeywords, self.torrent_db, 
                                                        self.pref_db, self.mypref_db, self.search_db)
        
        # boudewijn: now that we have sorted the search results we
        # want to prefetch the top N torrents.
        self.guiserver.add_task(self.prefetch_hits, t = 1, id = "PREFETCH_RESULTS")

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took: %s of which sort took %s' % ((time() - begintime), (time() - beginsort))
        self.hits = self.library_manager.addDownloadStates(self.hits)
        
        # Niels: important, we should not change self.hits otherwise prefetching will not work 
        returned_hits, selected_bundle_mode = self.bundler.bundle(self.hits, bundle_mode, self.searchkeywords)
        
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
                if self.downloadTorrentfileFromPeers(hit, sesscb_prefetch_done, duplicate=False, prio = 1):
                    if DEBUG: print >> sys.stderr, "Prefetch: attempting to download", hit.name
                    prefetch_counter += 1

            hit_counter += 1
            if prefetch_counter >= 10 or hit_counter >= 25:
                # (1) prefetch a maximum of N hits
                # (2) prefetch only from the first M hits
                # (.) wichever is lowest or (1) or (2)
                break
    
    def getSearchKeywords(self ):
        return self.searchkeywords, len(self.hits), self.filteredResults
    
    def setSearchKeywords(self, wantkeywords):
        if wantkeywords != self.searchkeywords:
            self.bundle_mode = None
        
        self.searchkeywords = wantkeywords
        if DEBUG:
            print >> sys.stderr, "TorrentSearchGridManager: keywords:", self.searchkeywords,";time:%", time()
            
        self.filteredResults = 0
        self.remoteHits = []
        self.oldsearchkeywords = ''
            
    def setBundleMode(self, bundle_mode):
        if bundle_mode != self.bundle_mode:
            self.bundle_mode = bundle_mode
            self.bundle_mode_changed = True
            self.refreshGrid()

    def searchLocalDatabase(self):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return False

        self.oldsearchkeywords = self.searchkeywords
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: Want",self.searchkeywords
                    
        if len(self.searchkeywords) == 0 or len(self.searchkeywords) == 1 and self.searchkeywords[0] == '':
            return False
        
        results = self.torrent_db.searchNames(self.searchkeywords)
        if len(results) > 0:
            
            def create_channel(a):
                if a['channel_id']:
                    channel = Channel(a['channel_id'], -1, a['channel_name'], '', 0, a['subscriptions'], a['neg_votes'], 0, 0, a['channel_id'] == self.channelcast_db._channel_id)
                    channel.searchManager = self.guiUtility.channelsearch_manager
                    return channel
                return False
            
            def create_torrent(a):
                a['channel'] = create_channel(a)
                t = Torrent(**getValidArgs(Torrent.__init__, a))
                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
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
                    known = remoteItem['torrent_id'] != -1
                    
                    if not known:
                        for item in self.hits:
                            
                            if item.infohash == remoteItem['infohash']:
                                #If this item is a remote, then update query_permids
                                if isinstance(item, RemoteTorrent):
                                    item.query_permids.update(remoteItem['query_permids'])
                                    
                                    #Maybe update channel?
                                    if remoteItem['channel_permid'] != "" and remoteItem['channel_name'] != "":
                                        this_rating = remoteItem['subscriptions'] - remoteItem['neg_votes']
                                        current_rating = item.channel.nr_favorites - item.channel.nr_spam
                                        
                                        if this_rating > current_rating:
                                            item.updateChannel(remoteItem['channel_permid'], remoteItem['channel_name'], remoteItem['subscriptions'], remoteItem['neg_votes'])
                                    
                                    hitsUpdated = True
                                known = True
                                break
                    
                    if not known:
                        remoteHit = RemoteTorrent(**getValidArgs(RemoteTorrent.__init__, remoteItem))
                        remoteHit.torrent_db = self.torrent_db
                        self.hits.append(remoteHit)
                        
                        hitsUpdated = True
                        
                self.remoteHits = []
        except:
            raise
        
        finally:
            self.remoteLock.release()
        return hitsUpdated
        
    def gotRemoteHits(self, permid, kws, answers):
        """
        Called by GUIUtil when hits come in.

        29/06/11 boudewijn: from now on called on the GUITaskQueue instead on the wx MainThread to
        avoid blocking the GUI because of the database queries.
        """
        if self.searchkeywords == kws:
            startWorker(None, self._gotRemoteHits, wargs=(permid, kws, answers))
        
    def _gotRemoteHits(self, permid, kws, answers):
        refreshGrid = False
        try:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got",len(answers),"unfiltered results for",kws, bin2str(permid), time()
                
            self.remoteLock.acquire()
            
            permid_channelid = self.channelcast_db.getPermChannelIdDict()
            my_votes = self.votecastdb.getMyVotes()
            
            # Always store the results, only display when in filesMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords == kws:
                numResults = 0
                catobj = Category.getInstance()
                
                for key,value in answers.iteritems():
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
                    
                    newval['channel_permid'] = value.get('channel_permid', '')
                    newval['channel_id'] = 0
                    newval['channel_name'] = value.get('channel_name', '')
                    newval['subscriptions'] = 0
                    newval['neg_votes'] = 0
                    
                    if 'channel_permid' in value:
                        channel_id = permid_channelid.get(newval['channel_permid'], None)
                        
                        if channel_id is not None:
                            my_vote = my_votes.get(channel_id, 0)
                            if my_vote < 0:
                                # I marked this channel as SPAM
                                continue
                            
                            newval['subscriptions'], newval['neg_votes'] = self.votecastdb.getPosNegVotes(channel_id)
                            if newval['subscriptions'] - newval['neg_votes'] < VOTE_LIMIT:
                                # We consider this as SPAM
                                continue
                            
                            newval['channel_id'] = channel_id
                    else:
                        newval['channel_permid'] = ""
                        newval['subscriptions'] = 0
                        newval['neg_votes'] = 0
               
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
            self.remoteLock.release()
            
            if refreshGrid:
                self.refreshGrid()
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()

    #Rameez: The following code will call normalization functions and then 
    #sort and merge the torrent results
    def sort(self):
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

    def doStatNormalization(self, hits, normKey):
        '''Center the variance on zero (this means mean == 0) and divide
        all values by the standard deviation. This is sometimes called scaling.
        This is done on the field normKey of hits.'''
        
        tot = 0
        for hit in hits:
            tot += hit.get(normKey, 0)
        
        if len(hits) > 0:
            mean = tot/len(hits)
        else:
            mean = 0
        
        sum = 0
        for hit in hits:
            temp = hit.get(normKey,0) - mean
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
                return_dict[hit.infohash] = (hit.get(normKey,0) - mean)/ stdDev
            else:
                return_dict[hit.infohash] = 0
        return return_dict
                
class LibraryManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if LibraryManager.__single:
            raise RuntimeError, "LibraryManager is singleton"
        LibraryManager.__single = self
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        
        #current progress of download states
        self.cache_progress = {}
        
        self.rerankingStrategy = DefaultTorrentReranker()
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.guiserver = GUITaskQueue.getInstance()
        
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
        
    def download_state_gui_callback(self, dslist):
        """
        Called by GUIThread
        """
        self.dslist = dslist
        for callback in self.gui_callback:
            try:
                callback(dslist)
            except:
                print_exc()
                self.remove_download_state_callback(callback)
            
        #TODO: This seems like the wrong place to do this?
        self.guiserver.add_task(lambda:self.updateProgressInDB(dslist),0)
     
    def updateProgressInDB(self, dslist):
        updates = False
        for ds in dslist:
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
        # Add downloadstate data to list of torrent dicts
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
                    torrent.ds = ds
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
    
    def deleteTorrent(self, torrent, removecontent = False):
        self.deleteTorrentDS(torrent.get('ds'), torrent['infohash'], removecontent)
    
    def deleteTorrentDS(self, ds, infohash, removecontent = False):
        if not ds is None:
            videoplayer = VideoPlayer.getInstance()
            playd = videoplayer.get_vod_download()
            
            if playd == ds.download:
                self._get_videoplayer(ds).stop_playback()
            
        self.deleteTorrentDownload(ds.get_download(), infohash, removecontent)
        
    def deleteTorrentDownload(self, download, infohash, removecontent = False, removestate = True):
        self.guiUtility.utility.session.remove_download(download, removecontent = removecontent, removestate = removestate)
        
        if infohash:
            # Johan, 2009-03-05: we need long download histories for good 
            # semantic clustering.
            # Arno, 2009-03-10: Not removing it from MyPref means it keeps showing
            # up in the Library, even after removal :-( H4x0r this.
            self.mypref_db.updateDestDir(infohash,"")
            self.user_download_choice.remove_download_state(infohash)
    
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def connect(self):
        session = self.guiUtility.utility.session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.torrentsearch_manager = self.guiUtility.torrentsearch_manager
        self.torrentsearch_manager = self.guiUtility.torrentsearch_manager
    
    def getHitsInCategory(self):
        if DEBUG: begintime = time()
        
        results = self.torrent_db.getTorrents(sort = "name", library = True)
        if len(results) > 0:
            def create_torrent(a):
                t = LibraryTorrent(**getValidArgs(LibraryTorrent.__init__, a))
                t.torrent_db = self.torrent_db
                t.channelcast_db = self.channelcast_db
                
                return t
            
            results = map(create_torrent, results)
        
        #Niels: maybe create a clever reranking for library results, for now disable
        #results = self.rerankingStrategy.rerank(results, '', self.torrent_db, self.pref_db, self.mypref_db, self.search_db)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took:', time() - begintime
            
        self.hits = self.addDownloadStates(results)
        return [len(self.hits), 0 , self.hits]

    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()

class ChannelSearchGridManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if ChannelSearchGridManager.__single:
            raise RuntimeError, "ChannelSearchGridManager is singleton"
        ChannelSearchGridManager.__single = self
        self.guiUtility = guiUtility
        self.guiserver = GUITaskQueue.getInstance()
        self.utility = guiUtility.utility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = {}
        
        self.channelcast_db = None
        self.votecastdb = None
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        
        self.searchkeywords = []
        self.oldsearchkeywords = []
        
        self.category = Category.getInstance()
        
    def getInstance(*args, **kw):
        if ChannelSearchGridManager.__single is None:
            ChannelSearchGridManager(*args, **kw)       
        return ChannelSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def connect(self):
        self.session = self.utility.session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = self.session.open_dbhandler(NTFY_VOTECAST)

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

    def getChannelHits(self):
        self.searchLocalDatabase()
        if DEBUG:
            print >>sys.stderr,'ChannelSearchGridManager: getChannelHits: search found: %d items' % len(self.hits)

        if len(self.hits) == 0:
            return [0, None]
        else:        
            return [len(self.hits),self.hits]
    
    def getChannel(self, channel_id):
        channel = self.channelcast_db.getChannel(channel_id)
        channel = self._createChannel(channel)
        
        #check if we need to convert our vote
        if channel.isDispersy() and channel.my_vote != 0:
            timestamp = self.votecastdb.getTimestamp(channel_id, None)
            self.do_vote(channel_id, channel.my_vote, timestamp)
        
        return channel
    
    def getChannels(self, channel_ids):
        channels = self.channelcast_db.channel_ids(channel_ids)
        return self._createChannels(channels)
    
    def getChannelState(self, channel_id):
        community = self._disp_get_community_from_channel_id(channel_id)
        return community.get_channel_mode()
    
    def setChannelState(self, channel_id, channel_mode):
        community = self._disp_get_community_from_channel_id(channel_id)
        return community.set_channel_mode(channel_mode)
    
    def getChannelFromPermid(self, channel_permid):
        channel = self.channelcast_db.getChannelFromPermid(channel_permid)
        if channel:
            return self._createChannel(channel)
        
    def getPermidFromChannel(self, channel_id):
        return self.channelcast_db.getPermidForChannel(channel_id)

    def getNewChannels(self):
        two_months = time() - 5259487
        
        newchannels = self.channelcast_db.getNewChannels(two_months)
        return len(newchannels), self._createChannels(newchannels)

    def getAllChannels(self):
        allchannels = self.channelcast_db.getAllChannels()
        return len(allchannels), self._createChannels(allchannels)
 
    def getMySubscriptions(self):
        subscriptions = self.channelcast_db.getMySubscribedChannels()
        return len(subscriptions), self._createChannels(subscriptions)

    def getPopularChannels(self):
        pchannels = self.channelcast_db.getMostPopularChannels()
        return len(pchannels), self._createChannels(pchannels)
    
    def getUpdatedChannels(self):
        lchannels = self.channelcast_db.getLatestUpdated()
        return len(lchannels), self._createChannels(lchannels)
    
    def _createChannel(self, hit):
        channel = Channel(*hit+(hit[0] == self.channelcast_db._channel_id,))
        channel.searchManager = self
        return channel
    
    def _createChannels(self, hits):
        channels = []
        for hit in hits:
            channel = Channel(*hit+(hit[0] == self.channelcast_db._channel_id,))
            channel.searchManager = self
            channels.append(channel)
            
        return channels
    
    def getTorrentMarkings(self, channeltorrent_id):
        return self.channelcast_db.getTorrentMarkings(channeltorrent_id)
    
    def getTorrentFromChannel(self, channel, infohash):
        data = self.channelcast_db.getTorrentFromChannelId(channel.id, infohash, CHANNEL_REQ_COLUMNS)
        return self._createTorrent(data, channel)
    
    def getTorrentsFromChannel(self, channel, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getTorrentsFromChannelId(channel.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {channel.id : channel})
    
    def getRecentTorrentsFromChannel(self, channel, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getRecentTorrentsFromChannelId(channel.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {channel.id : channel})

    def getTorrentsNotInPlaylist(self, channel, filterTorrents = True):
        hits = self.channelcast_db.getTorrentsNotInPlaylist(channel.id, CHANNEL_REQ_COLUMNS)
        return self._createTorrents(hits, filterTorrents, {channel.id : channel})
    
    def getTorrentsFromPlaylist(self, playlist, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id : playlist.channel})
    
    def getRecentTorrentsFromPlaylist(self, playlist, filterTorrents = True, limit = None):
        hits = self.channelcast_db.getRecentTorrentsFromPlaylist(playlist.id, CHANNEL_REQ_COLUMNS, limit)
        return self._createTorrents(hits, filterTorrents, {playlist.channel.id : playlist.channel})
    
    def _createTorrent(self, tuple, channel):
        if tuple:
            ct = ChannelTorrent(*tuple[1:]+[channel,])
            ct.torrent_db = self.torrent_db
            
            #Only return ChannelTorrent with a name, old not-collected torrents 
            #will be filtered due to this
            if ct.name:
                return ct
        
    def _createTorrents(self, hits, filterTorrents, channel_dict = {}):
        fetch_channels = set(hit[0] for hit in hits if hit[0] not in channel_dict)
        if len(fetch_channels) > 0:
            for channel in self.getChannels(fetch_channels):
                channel_dict[channel.id] = channel
        
        channels = []
        for hit in hits:
            channel = self._createTorrent(hit, channel_dict.get(hit[0], None))
            if channel: 
                channels.append(channel)
                
        self.filteredResults = 0
        if filterTorrents:
            channels = self._applyFF(channels)
        return len(channels), self.filteredResults, channels

    def getTorrentModifications(self, channeltorrent_id):
        data = self.channelcast_db.getTorrentModifications(channeltorrent_id)
        return self._createModifications(data)
    
    def getRecentModificationsFromChannel(self, channel, filterTorrents = True, limit = None):
        data = self.channelcast_db.getRecentModificationsFromChannelId(channel.id, MODIFICATION_REQ_COLUMNS, limit)
        return self._createModifications(data)

    def getRecentModificationsFromPlaylist(self, playlist_id, filterTorrents = True, limit = None):
        data = self.channelcast_db.getRecentModificationsFromPlaylist(playlist_id, MODIFICATION_REQ_COLUMNS, limit)
        return self._createModifications(data)

    def _createModifications(self, hits):
        returnList = []
        for hit in hits:
            mod = Modification(*hit)
            mod.channelcast_db = self.channelcast_db
            returnList.append(mod)
            
        return returnList
    
    def getCommentsFromChannel(self, channel, limit = None, resolve_names = True):
        hits = self.channelcast_db.getCommentsFromChannelId(channel.id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits)

    def getCommentsFromPlayListId(self, playlist_id, limit = None):
        hits = self.channelcast_db.getCommentsFromPlayListId(playlist_id, COMMENTPLAY_REQ_COLUMNS, limit)
        return self._createComments(hits)
            
    def getCommentsFromChannelTorrentId(self, channel_torrent_id, limit = None):
        hits = self.channelcast_db.getCommentsFromChannelTorrentId(channel_torrent_id, COMMENT_REQ_COLUMNS, limit)
        return self._createComments(hits)
        
    def _createComments(self, hits):
        returnList = []
        for hit in hits:
            comment = Comment(*hit)
            comment.get_nickname = self.utility.session.get_nickname
            comment.get_mugshot = self.utility.session.get_mugshot
            
            returnList.append(comment)
            
        return returnList
    
    def getMyVote(self, channel):
        return self.votecastdb.getVote(channel.id, None)
    
    def getSubscribersCount(self, channel):
        return self.channelcast_db.getSubscribersCount(channel.id)
    
    def _applyFF(self, hits):
        enabled_category_keys = [key.lower() for key in self.category.getCategoryKeys()]
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
        #return filter(torrentFilter, hits)
        return hits
    
    def _disp_get_community_from_channel_id(self, channel_id):
        assert isinstance(channel_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
        dispersy_cid = str(dispersy_cid)
        
        # 2. get the community instance from the 20 byte identifier
        try:
            community = self.dispersy.get_community(dispersy_cid)
        except KeyError:
            raise RuntimeError("Unknown community identifier")

        return community
    
    def createChannel(self, name, description):
        def dispersy_thread():
            community = ChannelCommunity.create_community(self.session.dispersy_member)
            community.create_channel(name, description)
        
        self.dispersy.callback.register(dispersy_thread)
    
    def createPlaylist(self, channel_id, name, description, infohashes = []):
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community.create_playlist(name, description, infohashes)

        self.dispersy.callback.register(dispersy_thread)
        
    def savePlaylistTorrents(self, channel_id, playlist_id, infohashes):
        #detect changes
        to_be_created = set(infohashes)
        to_be_removed = set()
        
        sql = "SELECT distinct infohash FROM PlaylistTorrents PL, ChannelTorrents CT, Torrent T WHERE PL.channeltorrent_id = CT.id AND CT.torrent_id = T.torrent_id AND playlist_id = ?"
        records = self.channelcast_db._db.fetchall(sql,(playlist_id,))
        for infohash, in records:
            infohash = str2bin(infohash)
            if infohash in to_be_created:
                to_be_created.remove(infohash)
            else:
                to_be_removed.add(infohash)
        
        if len(to_be_created) > 0:
            def dispersy_thread():
                community = self._disp_get_community_from_channel_id(channel_id)
                community.create_playlist_torrents(playlist_id, to_be_created)
            
            self.dispersy.callback.register(dispersy_thread)
    
    def createComment(self, comment, channel_id, reply_after = None, reply_to = None, playlist_id = None, channeltorrent_id = None):
        infohash = None
        if channeltorrent_id:
            infohash = self.channelcast_db.getTorrentFromChannelTorrentId(channeltorrent_id, ['infohash'])
        
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community.create_comment(comment, int(time()), reply_after, reply_to, playlist_id, infohash)
        self.dispersy.callback.register(dispersy_thread)
    
    def modifyChannel(self, channel_id, name, description):
        dict = {'name':name, 'description':description}
        
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community.modifyChannel(dict)
        self.dispersy.callback.register(dispersy_thread)

    def modifyPlaylist(self, channel_id, playlist_id, name, description):
        dict = {'name':name, 'description':description}
        
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community.modifyPlaylist(playlist_id, dict)
        self.dispersy.callback.register(dispersy_thread)
    
    def modifyTorrent(self, channel_id, channeltorrent_id, dict_changes):
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community.modifyTorrent(channeltorrent_id, dict_changes)
        
        self.dispersy.callback.register(dispersy_thread)
    
    def getPlaylistsFromChannelId(self, channel_id, keys):
        hits = self.channelcast_db.getPlaylistsFromChannelId(channel_id, keys)
        return len(hits), hits
    
    def spam(self, channel_id):
        self.do_vote(channel_id, -1)
        
    def favorite(self, channel_id):
        self.do_vote(channel_id, 2)
    
    def remove_vote(self, channel_id):
        self.do_vote(channel_id, 0)
        
    def do_vote(self, channel_id, vote, timestamp = None):
        if not timestamp:
            timestamp = int(time())
        
        dispersy_cid = self.channelcast_db.getDispersyCIDFromChannelId(channel_id)
        dispersy_cid = str(dispersy_cid)
        if dispersy_cid != '-1':
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    community._disp_create_votecast(dispersy_cid, vote, timestamp)
                    break
            
        elif vote == 2:
            self.votecastdb.subscribe(channel_id)
        elif vote == -1:
            self.votecastdb.spam(channel_id)
        else:
            self.votecastdb.unsubscribe(channel_id)
    
    def markTorrent(self, channel_id, infohash, type, timestamp = None):
        if not timestamp:
            timestamp = int(time())
        
        def dispersy_thread():
            community = self._disp_get_community_from_channel_id(channel_id)
            community._disp_create_mark_torrent(infohash, type, timestamp)
        
        self.dispersy.callback.register(dispersy_thread)
        
    def getChannelForTorrent(self, infohash):
        return self.channelcast_db.getMostPopularChannelFromTorrent(infohash)
    
    def getNrTorrentsDownloaded(self, publisher_id):
        return self.channelcast_db.getNrTorrentsDownloaded(publisher_id)
    
    def getPlaylist(self, playlist_id, keys):
        return self.channelcast_db.getPlaylist(playlist_id, keys)
    
    def setSearchKeywords(self, wantkeywords):
        self.searchkeywords = wantkeywords
    
    def searchLocalDatabase(self):
        """ Called by GetChannelHits() to search local DB. Caches previous query result. """
        if self.searchkeywords == self.oldsearchkeywords  and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: searchLocalDB: returning old hit list", len(self.hits)
            return False
        
        self.oldsearchkeywords = self.searchkeywords
        if DEBUG:
            print >>sys.stderr,"ChannelSearchGridManager: searchLocalDB: Want",self.searchkeywords
         
        if len(self.searchkeywords) == 0 or len(self.searchkeywords) == 1 and self.searchkeywords[0] == '':
            return False

        query = "k "
        for i in self.searchkeywords:
            query = query + i + ' '
        
        hits = self.channelcast_db.searchChannels(query) 
        
        self.hits = {}
        for hit in hits:
            if hit[0] not in self.hits:
                self.hits[hit[0]] = [hit[1], self.votecastdb.getEffectiveVote(hit[0]), {}]
            
            #Extend torrent dict for this channel
            torrents = self.hits[hit[0]][2]
            if hit[2] not in torrents:
                torrents[hit[2]] = (hit[3], hit[4])
        return True
        
    def gotRemoteHits(self, permid, kws, answers):
        """ Called by GUIUtil when hits come in. """
        self.guiserver.add_task(lambda:self._gotRemoteHits(permid, kws, answers))
        
    def _gotRemoteHits(self, permid, kws, answers):
        #
        # @param permid: the peer who returned the answer to the query
        # @param kws: the keywords of the query that originated the answer
        # @param answers: the filtered answers returned by the peer (channel_id, publisher_name, infohash, name, time_stamp)

        t1 = time()
        try:
            if DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHist: got",len(answers),"for",kws
            
            # Always store the results, only display when in channelsMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords == kws:
                numResults = 0
                
                for hit in answers.itervalues():
                    #Add to self.hits
                    if hit[0] not in self.hits:
                        self.hits[hit[0]] = [hit[1], self.votecastdb.getEffectiveVote(hit[0]), {}]
                    
                    #Extend torrent dict for this channel
                    torrents = self.hits[hit[0]][2]
                    if hit[2] not in torrents:
                        torrents[hit[2]] = (hit[3], hit[4])
                        numResults +=1
                
                if numResults > 0:
                    self.refreshGrid()
                    if DEBUG:
                        print >>sys.stderr,'ChannelSearchGridManager: gotRemoteHits: Refresh grid after new remote channel hits came in', "Took", time() - t1
                return True
            elif DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHits: got hits for",kws,"but current search is for",self.searchkeywords
            return False
        except:
            print_exc()
            return False
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh_channel()                
