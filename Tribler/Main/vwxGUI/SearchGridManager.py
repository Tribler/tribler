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

from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Core.Session import Session
from Tribler.Video.utils import videoextdefaults
from Tribler.Video.VideoPlayer import VideoPlayer

from math import sqrt

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
        self.remoteHits = {}
        
        #current progress of download states
        self.cache_progress = {}
        
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        self.guiserver = GUITaskQueue.getInstance()
        
        # Gui callbacks
        self.gui_callback = []

        self.searchkeywords = {'filesMode':[], 'libraryMode':[]}
        self.rerankingStrategy = {'filesMode':DefaultTorrentReranker(), 'libraryMode':DefaultTorrentReranker()}
        self.oldsearchkeywords = {'filesMode':[], 'libraryMode':[]} # previous query

        self.category = Category.getInstance()
        
        # 09/10/09 boudewijn: CallLater does not accept zero as a
        # delay. the value needs to be a positive integer.
        self.prefetch_callback = wx.CallLater(10, self.prefetch_hits)
        
    def getInstance(*args, **kw):
        if TorrentManager.__single is None:
            TorrentManager(*args, **kw)       
        return TorrentManager.__single
    getInstance = staticmethod(getInstance)
    
    def getTorrent(self, torrent, callback):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!
        
        CALLBACK is called when the torrent is downloaded. When no
        torrent can be downloaded the callback is ignored
        
        Returns a filename, if filename is known or a boolean + request_type
        describing if the torrent is requested
        """
        torrent_dir = self.guiUtility.utility.session.get_torrent_collecting_dir()
        
        if 'torrent_file_name' not in torrent or not torrent['torrent_file_name']:
            torrent['torrent_file_name'] = get_collected_torrent_filename(torrent['infohash'])
        torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
        
        #.torrent found, return complete filename
        if os.path.isfile(torrent_filename):
            return torrent_filename
        
        #.torrent not found, possibly a new torrent_collecting_dir
        torrent['torrent_file_name'] = get_collected_torrent_filename(torrent['infohash'])
        torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
        if os.path.isfile(torrent_filename):
            return torrent_filename
        
        #.torrent not found, try to download from peers
        if 'query_permids' in torrent and not torrent.get('myDownloadHistory'):
            if self.downloadTorrentfileFromPeers(torrent, callback):
                return (True, "from peers")
        
        #.torrent still not found, try magnet link
        magnetlink = "magnet:?xt=urn:btih:"+hexlify(torrent['infohash'])
        def torrentdef_retrieved(tdef):
            tdef.save(torrent_filename)
            callback(torrent['infohash'], torrent, torrent_filename)
            
        return (TorrentDef.retrieve_from_magnet(magnetlink, torrentdef_retrieved), "from dht")
             
    def downloadTorrentfileFromPeers(self, torrent, callback, duplicate=True):
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

        Returns True or False
        """
        def success_callback(*args):
            # empty the permids list to indicate that we are done
            if state[0]:
                if DEBUG: print >>sys.stderr,"standardDetails: _download_torrentfile_from_peers: received .torrent from peer after", time() - begin_timer, "seconds"
                state[0] = False
                callback(*args)

        def next_callback(timeout):
            """
            TIMEOUT: when TIMEOUT>=0 then will try another peer after TIMEOUT seconds.
            """
            if state[0] and state[1]:
                if DEBUG: print >>sys.stderr,"standardDetails: _download_torrentfile_from_peers: trying to .torrent download from peer.",len(state[1])-1,"other peers to ask"
                self.guiUtility.utility.session.download_torrentfile_from_peer(state[1].pop(0), torrent['infohash'], success_callback)
                if timeout >= 0:
                    next_callback_lambda = lambda:next_callback(timeout)
                    guiserver.add_task(next_callback_lambda, timeout)

        # return False when duplicate
        if not duplicate and torrent.get('query_torrent_was_requested', False):
            return False

        # return False when there are no sources to retrieve the
        # torrent from
        if not 'query_permids' in torrent:
            if DEBUG:
                print >> sys.stderr, "standardDetails: _download_torrentfile_from_peers: can not download .torrent file. No known source peers"
            return False

        torrent['query_torrent_was_requested'] = True
        
        guiserver = GUITaskQueue.getInstance()
        state = [True, torrent['query_permids'][:]]

        if DEBUG:
            begin_timer = time()

        # The rules and policies below can be tweaked to increase
        # performace. More parallel requests can be made, or the
        # timeout to ask more people can be decreased. All at the
        # expence of bandwith.
        if torrent['torrent_size'] > 50 * 1024:
            # this is a big torrent. to preserve bandwidth we will
            # request sequentially with a large timeout
            next_callback(3)
            
        elif 0 <= torrent['torrent_size'] <= 10 * 1024:
            # this is a small torrent. bandwidth is not an issue so
            # download in parallel
            next_callback(-1)
            next_callback(1)
            next_callback(1)

        else:
            # medium and unknown torrent size. 
            next_callback(1)
            next_callback(1)
        return True
    
    def downloadTorrent(self, torrent, dest = None, secret = False, vodmode = False):
        callback = lambda infohash, metadata, filename: self.downloadTorrent(torrent, dest, secret, vodmode)
        torrent_filename = self.getTorrent(torrent, callback)
        
        if isinstance(torrent_filename, basestring):
            #got actual filename
            
            if torrent.get('name'):
                name = torrent['name']
            else:
                name = torrent['infohash']
            
            clicklog={'keywords': self.searchkeywords['filesMode'],
                      'reranking_strategy': self.rerankingStrategy['filesMode'].getID()}
            
            if "click_position" in torrent:
                clicklog["click_position"] = torrent["click_position"]
            
            # Api download
            d = self.guiUtility.frame.startDownload(torrent_filename,destdir=dest,clicklog=clicklog,name=name,vodmode=vodmode) ## remove name=name
            if d:
                if secret:
                    self.torrent_db.setSecret(torrent['infohash'], secret)

                if DEBUG:
                    print >>sys.stderr,'standardDetails: download: download started'
               
                torrent['myDownloadHistory'] = True
        elif torrent_filename[0]:
            #torrent is being requested from peers, using callback this function will be called again
            return torrent_filename[1]
        else:
            #torrent not found
            str = self.guiUtility.utility.lang.get('delete_torrent') % torrent['name']
            dlg = wx.MessageDialog(self.guiUtility.frame, str, self.guiUtility.utility.lang.get('delete_dead_torrent'), 
                                wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                infohash = torrent['infohash']
                self.torrent_db.deleteTorrent(infohash, delete_file=True, commit = True)
    
    def isTorrentPlayable(self, torrent, default=(False, [], []), callback=None):
        """
        TORRENT is a dictionary containing torrent information used to
        display the entry on the UI. it is NOT the torrent file!

        DEFAULT indicates the default value when we don't know if the
        torrent is playable. 

        CALLBACK can be given to result the actual 'playable' value
        for the torrent after some downloading/processing. The DEFAULT
        value is returned in this case. Will only be called if
        self.item == torrent

        The return value is a tuple consisting of a boolean indicating if the torrent is playable and a list.
        If the torrent is not playable or if the default value is returned the boolean is False and the list is empty.
        If it is playable the boolean is true and the list returned consists of the playable files within the actual torrent. 
        """
        torrent_callback = lambda infohash, metadata, filename: self.isTorrentPlayable(torrent, default, callback)
        torrent_filename = self.getTorrent(torrent, torrent_callback)
        
        if isinstance(torrent_filename, basestring):
            #got actual filename
            tdef = TorrentDef.load(torrent_filename)
            
            files = tdef.get_files_as_unicode(exts=videoextdefaults)
            allfiles = tdef.get_files_as_unicode_with_length()
            playable = len(files) > 0
            torrent['comment'] = tdef.get_comment_as_unicode()
            
            if tdef.get_tracker_hierarchy():
                torrent['trackers'] = tdef.get_tracker_hierarchy()
            else:
                torrent['trackers'] = [[tdef.get_tracker()]]
            
            if not callback is None:
                wx.CallAfter(callback, torrent, (playable, files, allfiles))
            else:
                return (playable, files, allfiles)
        elif not torrent_filename[0]:
            if DEBUG:
                print >>sys.stderr, "standardDetails:torrent_is_playable returning default", default
            wx.CallAfter(callback, torrent, default)
        else:
            return torrent_filename[1]
    
    def getSwarmInfo(self, torrent_id):
        return self.torrent_db.getSwarmInfo(torrent_id)
    
    def playTorrent(self, torrent, selectedinfilename = None):
        ds = torrent.get('ds')
        
        videoplayer = self._get_videoplayer(ds)
        videoplayer.stop_playback()
        videoplayer.show_loading()
        
        if ds is None:
            #Making sure we actually have this .torrent
            callback = lambda infohash, metadata, filename: self.playTorrent(torrent)
            filename = self.getTorrent(torrent, callback)
            
            if isinstance(filename, basestring):
                #got actual filename, load torrentdef and create downloadconfig
                
                tdef = TorrentDef.load(filename)
                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()
                videoplayer.start_and_play(tdef, dscfg, selectedinfilename)
        else:
            videoplayer.play(ds, selectedinfilename)
    
    def deleteTorrent(self, torrent, removecontent = False):
        ds = torrent.get('ds')
        if not ds is None:
            videoplayer = VideoPlayer.getInstance()
            playd = videoplayer.get_vod_download()
            
            if playd == ds.download:
               self._get_videoplayer(ds).stop_playback()
            
            self.guiUtility.utility.session.remove_download(ds.get_download(), removecontent = removecontent)
            
        # Johan, 2009-03-05: we need long download histories for good 
        # semantic clustering.
        # Arno, 2009-03-10: Not removing it from MyPref means it keeps showing
        # up in the Library, even after removal :-( H4x0r this.
        self.mypref_db.updateDestDir(torrent['infohash'],"")
    
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
        for ds in dslist:
            infohash = ds.get_download().get_def().get_infohash()
            
            progress = (ds.get_progress() or 0.0) * 100.0
            if progress - self.cache_progress.get(infohash, 0) > 1:
                self.cache_progress[infohash] = progress
                try:
                    self.mypref_db.updateProgress(infohash, progress, commit=True)
                except:
                    print_exc() 
        
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
                if torrent['infohash'] == infohash:
                    torrent['ds'] = ds
                    break
            except:
                pass
        return torrent
    
    def addDownloadStates(self, liblist):
        # Add downloadstate data to list of torrent dicts
        for ds in self.dslist:
            try:
                infohash = ds.get_download().get_def().get_infohash()
                for torrent in liblist:
                    if torrent['infohash'] == infohash:
                        torrent['ds'] = ds
                        break
            except:
                pass
        return liblist
    
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def connect(self):
        session = self.guiUtility.utility.session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.channelcastdb = session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
        self.searchmgr = SearchManager(self.torrent_db)
    
    def getHitsInCategory(self, mode = 'filesMode', categorykey = 'all', range = [0,250], sort = 'rameezmetric', reverse = False):
        if DEBUG: begintime = time()
        # mode is 'filesMode', 'libraryMode'
        # categorykey can be 'all', 'Video', 'Document', ...
        
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: getHitsInCategory:",mode,categorykey,range
        
        categorykey = categorykey.lower()
        enabledcattuples = self.category.getCategoryNames()
        enabledcatslow = ["other"]
        for catname,displayname in enabledcattuples:
            enabledcatslow.append(catname.lower())
        
        # TODO: do all filtering in DB query
        def torrentFilter(torrent):
            library = (mode == 'libraryMode')
            okLibrary = not library or (torrent.get('myDownloadHistory', False) and torrent.get('destdir',"") != "")
            
            okCategory = False
            categories = torrent.get("category", [])
            if not categories:
                categories = ["other"]
            if categorykey == 'all':
                for torcat in categories:
                    if torcat.lower() in enabledcatslow:
                        okCategory = True
                        break
            elif categorykey in [cat.lower() for cat in categories]:
                okCategory = True
            
            okGood = torrent['status'] != 'dead'
                        
            #print >>sys.stderr,"FILTER: lib",okLibrary,"cat",okCategory,"good",okGood
            return okLibrary and okCategory and okGood
        
        # 1. Local search puts hits in self.hits
        new_local_hits = self.searchLocalDatabase(mode)
        
        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: search found: %d items' % len(self.hits)

        # 2. Filter self.hits on category and status
        if new_local_hits:
            self.hits = filter(torrentFilter,self.hits)

        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: torrentFilter after filter found: %d items' % len(self.hits)
        
        # 3. Add remote hits that may apply. TODO: double filtering, could
        # add remote hits to self.hits before filter(torrentFilter,...)
        if mode != 'libraryMode':
            self.addStoredRemoteResults()

            if DEBUG:
                print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items' % len(self.hits)
        
        if range[0] > len(self.hits):
            return [0,None]

        if DEBUG:
            beginsort = time()
        
        if sort == 'rameezmetric':
            self.sort()

        # Nic: Ok this is somewhat diagonal to the previous sorting algorithms
        # eventually, these should probably be combined
        # since for now, however, my reranking is very tame (exchanging first and second place under certain circumstances)
        # this should be fine...
        self.rerankingStrategy[mode] = getTorrentReranker()
        self.hits = self.rerankingStrategy[mode].rerank(self.hits, self.searchkeywords[mode], self.torrent_db, 
                                                        self.pref_db, self.mypref_db, self.search_db)

        # boudewijn: now that we have sorted the search results we
        # want to prefetch the top N torrents.
        if not self.prefetch_callback.IsRunning():
            self.prefetch_callback.Start(1000)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took: %s of which search %s' % ((time() - begintime), (time() - beginsort))
        self.hits = self.addDownloadStates(self.hits)

        return [len(self.hits), self.hits]

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
                        if hit["infohash"] == infohash:
                            print >> sys.stderr, "Prefetch: in", "%.1fs" % (time() - begin_time), `hit["name"]`
                            return
                    print >> sys.stderr, "Prefetch BUG. We got a hit from something we didn't ask for"

            if 'torrent_file_name' not in hit or not hit['torrent_file_name']:
                hit['torrent_file_name'] = get_collected_torrent_filename(hit['infohash']) 
            torrent_filename = os.path.join(torrent_dir, hit['torrent_file_name'])

            if not os.path.isfile(torrent_filename):
                if self.downloadTorrentfileFromPeers(hit, sesscb_prefetch_done, duplicate=False):
                    prefetch_counter += 1
                    if DEBUG: print >> sys.stderr, "Prefetch: attempting to download", `hit["name"]`

            hit_counter += 1
            if prefetch_counter >= 10 or hit_counter >= 25:
                # (1) prefetch a maximum of N hits
                # (2) prefetch only from the first M hits
                # (.) wichever is lowest or (1) or (2)
                break

    def setSearchKeywords(self, wantkeywords, mode):
        self.stopped = False
        self.searchkeywords[mode] = wantkeywords
        if mode == 'filesMode':
            if DEBUG:
                print >> sys.stderr, "TorrentSearchGridManager: keywords:", self.searchkeywords[mode],";time:%", time()
            self.remoteHits = {}
            self.oldsearchkeywords[mode] = ''

    def searchLocalDatabase(self, mode):
        if mode != 'libraryMode':
            """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
            if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
                if DEBUG:
                    print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
                return False

            self.oldsearchkeywords[mode] = self.searchkeywords[mode]
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: Want",self.searchkeywords[mode]
            
            if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
                return False
            
            self.hits = self.searchmgr.search(self.searchkeywords[mode])
        else:
            self.hits = self.searchmgr.searchLibrary()
        return True

    def addStoredRemoteResults(self):
        """ Called by GetHitsInCategory() to add remote results to self.hits """
        if len(self.remoteHits) > 0:
            numResults = 0
            def catFilter(item):
                icat = item.get('category')
                if type(icat) == list:
                    icat = icat[0].lower()
                elif type(icat) == str:
                    icat = icat.lower()
                else:
                    return False
            
            #catResults = filter(catFilter, self.remoteHits.values())
            catResults = self.remoteHits.values()
            if DEBUG:
                print >> sys.stderr,"TorrentSearchGridManager: remote: Adding %d remote results (%d in category)" % (len(self.remoteHits), len(catResults))
            
            for remoteItem in catResults:
                known = False
                for item in self.hits:
                    #print >> sys.stderr,"TorrentSearchGridManager: remote: Should we add",`remoteItem['name']`
                    if item['infohash'] == remoteItem['infohash']:
                        known = True
                        # if a hit belongs to a more popular channel, then replace the previous
                        """
                        if remoteItem['channel_permid'] !="" and remoteItem['channel_name'] != "" and remoteItem['subscriptions']-remoteItem['neg_votes'] > item['subscriptions']-item['neg_votes']:
                            item['subscriptions'] = remoteItem['subscriptions']
                            item['neg_votes'] = remoteItem['neg_votes']
                            item['channel_permid'] = remoteItem['channel_permid']
                            item['channel_name'] = remoteItem['channel_name']
                        """
                        break
                if not known:
                    #print >> sys.stderr,"TorrentSearchGridManager: remote: Adding",`remoteItem['name']`
                    self.hits.append(remoteItem)
                    numResults+=1
        
    def gotRemoteHits(self, permid, kws, answers):
        """ Called by GUIUtil when hits come in. """
        try:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got",len(answers),"unfiltered results for",kws, bin2str(permid), time()
            
            # Always store the results, only display when in filesMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords['filesMode'] == kws:
                numResults = 0
                catobj = Category.getInstance()
                for key,value in answers.iteritems():
                    
                    if self.torrent_db.hasTorrent(key):
                        if DEBUG:
                            print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: Ignoring hit for",`value['content_name']`,"already got it"
                        continue # do not show results we have ourselves
                    
                    # First, check if it matches the word boundaries, that belongs to previous version
                    
                    # Convert answer fields as per 
                    # Session.query_connected_peers() spec. to NEWDB format
                    newval = {}
                    newval['name'] = value['content_name']                    
                    newval['infohash'] = key
                    newval['torrent_file_name'] = ''
                    newval['length'] = value['length']
                    newval['creation_date'] = time()  # None  gives '?' in GUI
                    newval['relevance'] = 0
                    newval['source'] = 'RQ'
                    newval['category'] = value['category'][0] 
                    # We trust the peer
                    newval['status'] = 'good'
                    newval['num_seeders'] = value['seeder']
                    newval['num_leechers'] = value['leecher']

                    # OLPROTO_VER_NINETH includes a torrent_size. Set to
                    # -1 when not available.
                    if 'torrent_size' in value:
                        newval['torrent_size'] = value['torrent_size']
                    else:
                        newval['torrent_size'] = -1
                        
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
                        
                    if 'channel_permid' in value:
                        newval['channel_permid']=value['channel_permid']
                    else:
                        newval['channel_permid']=""
                        
                    if 'channel_name' in value:
                        newval['channel_name'] = value['channel_name']
                    else:
                        newval['channel_name']=""
                        
                    if 'channel_permid' in value:
                        newval['neg_votes'] = self.votecastdb.getNegVotes(value['channel_permid'])
                        newval['subscriptions'] = self.votecastdb.getNumSubscriptions(value['channel_permid'])
                        if newval['subscriptions']-newval['neg_votes']<VOTE_LIMIT:
                            # now, this is SPAM
                            continue
                    else:
                        newval['subscriptions']=0
                        newval['neg_votes'] = 0
                            

                    # Extra field: Set from which peer this info originates
                    newval['query_permids'] = [permid]
                        
                    # Filter out results from unwanted categories
                    flag = False
                    for cat in value['category']:
                        rank = catobj.getCategoryRank(cat)
                        if rank == -1:
                            if DEBUG:
                                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHits: Got",`newval['name']`,"from banned category",cat,", discarded it."
                            flag = True
                            break
                    if flag:
                        continue

                    if newval['infohash'] in self.remoteHits:
                        if DEBUG:
                            print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: merging hit",`newval['name']`

                        # merge this result with previous results
                        oldval = self.remoteHits[newval['infohash']]
                        for query_permid in newval['query_permids']:
                            if not query_permid in oldval['query_permids']:
                                oldval['query_permids'].append(query_permid)
                        
                        # if a hit belongs to a more popular channel, then replace the previous
                        if newval['channel_permid'] !="" and newval['channel_name'] != "" and newval['subscriptions']-newval['neg_votes'] > oldval['subscriptions']-oldval['neg_votes']:
                            oldval['subscriptions'] = newval['subscriptions']
                            oldval['neg_votes'] = newval['neg_votes']
                            oldval['channel_permid'] = newval['channel_permid']
                            oldval['channel_name'] = newval['channel_name']
                    else:
                        if DEBUG:
                            print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: appending hit",`newval['name']`

                        self.remoteHits[newval['infohash']] = newval
                        numResults +=1
                        # if numResults % 5 == 0:
                        # self.refreshGrid()
             
                if numResults > 0:
                    self.refreshGrid()
                    if DEBUG:
                        print >>sys.stderr,'TorrentSearchGridManager: gotRemoteHits: Refresh grid after new remote torrent hits came in'
                return True
            elif DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHits: got hits for",kws,"but current search is for",self.searchkeywords
            return False
        except:
            print_exc()
            return False
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()

    #Rameez: The following code will call normalization functions and then 
    #sort and merge the torrent results
    def sort(self):
        self.doStatNormalization(self.hits,'num_seeders', 'norm_num_seeders')
        self.doStatNormalization(self.hits,'neg_votes', 'norm_neg_votes')
        self.doStatNormalization(self.hits,'subscriptions', 'norm_subscriptions')

        def cmp(a,b):
            # normScores can be small, so multiply
            return int( 1000000.0 * ( 0.8*b.get('norm_num_seeders',0) + 0.1*b.get('norm_neg_votes',0) + 0.1*b.get('norm_subscriptions',0) -
                        0.8*a.get('norm_num_seeders',0) - 0.1*a.get('norm_neg_votes',0) - 0.1*a.get('norm_subscriptions',0) ))
           
        self.hits.sort(cmp)

    def doStatNormalization(self, hits, normKey, newKey):
        '''Center the variance on zero (this means mean == 0) and divide
        all values by the standard deviation. This is sometimes called scaling.
        This is done on the field normKey of hits and the output is added to a new 
        field called newKey.'''
        
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
        
        for hit in hits:
            if stdDev > 0:
                hit[newKey] = (hit.get(normKey,0)-mean)/ stdDev
            else:
                hit[newKey] = 0
                
class ChannelSearchGridManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if ChannelSearchGridManager.__single:
            raise RuntimeError, "ChannelSearchGridManager is singleton"
        ChannelSearchGridManager.__single = self
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        
        self.searchmgr = None
        self.channelcast_db = None
        self.pref_db = None # Nic: for rerankers
        self.mypref_db = None
        self.search_db = None
        
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
        session = self.guiUtility.utility.session
        self.torrent_db = session.open_dbhandler(NTFY_TORRENTS)
        self.pref_db = session.open_dbhandler(NTFY_PREFERENCES)
        self.mypref_db = session.open_dbhandler(NTFY_MYPREFERENCES)
        self.search_db = session.open_dbhandler(NTFY_SEARCH)
        self.channelcast_db = session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = session.open_dbhandler(NTFY_VOTECAST)
        self.searchmgr = SearchManager(self.channelcast_db)
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()

        
        
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr

    def getChannelHits(self):
        new_local_hits = self.searchLocalDatabase()

        if DEBUG:
            print >>sys.stderr,'ChannelSearchGridManager: getChannelHits: search found: %d items' % len(self.hits)

        if len(self.hits) == 0:
            return [0, None]
        else:        
            return [len(self.hits),self.hits]

    def getNewChannels(self):
        #all channels with no votes + updated since
        two_months = time() - 5259487
        
        newchannels = self.channelcast_db.getNewChannels(two_months)
        return [len(newchannels), newchannels]

    def getAllChannels(self):
        allchannels = self.channelcast_db.getAllChannels()
        return [len(allchannels), allchannels]
 
    def getSubscriptions(self):
        subscriptions = self.channelcast_db.getMySubscribedChannels()
        return [len(subscriptions), subscriptions]

    def getPopularChannels(self):
        pchannels = self.channelcast_db.getMostPopularUnsubscribedChannels()
        return [len(pchannels), pchannels]
    
    def getMyVote(self, publisher_id):
        return self.votecastdb.getVote(publisher_id, bin2str(self.votecastdb.my_permid))
    
    def getTorrentsFromMyChannel(self):
        return self.getTorrentsFromPublisherId(bin2str(self.votecastdb.my_permid))
    
    def getTorrentFromPublisherId(self, publisher_id, infohash):
        return self.channelcast_db.getTorrentFromPublisherId(publisher_id, infohash)
    
    def getTorrentsFromPublisherId(self, publisher_id):
        hits = self.channelcast_db.getTorrentsFromPublisherId(publisher_id)
        
        enabledcattuples = self.category.getCategoryNames()
        enabledcatslow = ["other"]
        for catname,displayname in enabledcattuples:
            enabledcatslow.append(catname.lower())
        
        def torrentFilter(torrent):
            okCategory = False
            categories = torrent.get("category", ["other"])
            for torcat in categories:
                if torcat.lower() in enabledcatslow:
                    okCategory = True
                    break
                
            okGood = torrent['status'] != 'dead'
            return okGood and okCategory
        
        return filter(torrentFilter, hits) 
    
    def getChannel(self, publisher_id):
        return self.channelcast_db.getChannel(publisher_id)
    
    def spam(self, publisher_id):
        self.votecastdb.spam(publisher_id)
        self.channelcast_db.deleteTorrentsFromPublisherId(publisher_id)
        
    def favorite(self, publisher_id):
        self.votecastdb.subscribe(publisher_id)
    
    def remove_vote(self, publisher_id):
        self.votecastdb.unsubscribe(publisher_id)
        
    def getChannelForTorrent(self, infohash):
        return self.channelcast_db.getMostPopularChannelFromTorrent(infohash)
    
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
        
        #self.hits = self.searchmgr.searchChannels(query)
        hits = self.searchmgr.searchChannels(query)
        
        # Nitin on Feb 5, 2010: temp fix: converting into string format coz most things in GUI use string forms.
        # Fields like permid, infohash, torrenthash are in binary format in each record in 'hits' list.
        votecache = {}
        self.hits = {}
        for hit in hits:
            if bin2str(hit[0]) not in self.hits:
                torrents = {}                 
                torrents[bin2str(hit[2])] = (hit[4], hit[5]) # {infohash:(torrentname, timestamp)}
                self.hits[bin2str(hit[0])] = [hit[1], votecache.setdefault(hit[0], self.votecastdb.getEffectiveVote(bin2str(hit[0]))), torrents]
            else:
                torrents = self.hits[bin2str(hit[0])][2]
                if bin2str(hit[2]) not in torrents:
                    torrents[bin2str(hit[2])] = (hit[4], hit[5])
        return True
        
    def gotRemoteHits(self, permid, kws, answers):
        """ Called by GUIUtil when hits come in. """
        #
        # @param permid: the peer who returned the answer to the query
        # @param kws: the keywords of the query that originated the answer
        # @param answers: the complete answer returned by the peer
        
        #05-06-2010 Andrea:
        # I moved the code to update the Channelcast DB in RemoteQueryMsgHandler.process_query_reply
        # so that is no more the GUI thread that has to write in the db
            
        #09-04-2010 Andrea: answers now is exactly a ChannelCastMessage

        t1 = time()
        try:
            if DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHist: got",len(answers),"for",kws
            
            # Always store the results, only display when in channelsMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords == kws:
                numResults = 0
                votecache = {}
                
                session = self.rtorrent_handler.session
                my_permid = bin2str(session.get_permid())
                
                for _, d in answers.iteritems():
                    #Is this channel marked as spam?
                    d['publisher_id'] = bin2str(d['publisher_id'])
                    
                    if d['publisher_id'] not in votecache:
                        votecache[d['publisher_id']] = (self.votecastdb.getVote(d['publisher_id'],my_permid), self.channelcast_db.getSubscribersCount(d['publisher_id']))
                    if votecache[d['publisher_id']][0] == -1:
                        continue
                    
                    #Add to self.hits
                    if d['publisher_id'] not in self.hits:
                        self.hits[d['publisher_id']] = [d['publisher_name'], votecache[d['publisher_id']][1], {}]
                    
                    #Extend torrent dict for this channel
                    torrents = self.hits[d['publisher_id']][2]
                    if d['infohash'] not in torrents:
                        torrents[d['infohash']] = (d['torrentname'], d['time_stamp'])
                        numResults +=1
                
                if numResults > 0:
                    wx.CallAfter(self.refreshGrid)
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
