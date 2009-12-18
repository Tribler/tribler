# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information

import sys
import wx
import os
from traceback import print_exc, print_stack
from time import time

from Tribler.Category.Category import Category
from Tribler.Core.Search.SearchManager import SearchManager
from Tribler.Core.Search.Reranking import getTorrentReranker, DefaultTorrentReranker
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.simpledefs import *

from Tribler.Core.Overlay.MetadataHandler import get_filename
from Tribler.Core.Session import Session

from math import sqrt
try:
    import web2
except ImportError:
    print >>sys.stderr,'SearchGridManager: Could not import web2'
    print_exc()
    

DEBUG = False

SEARCHMODE_STOPPED = 1
SEARCHMODE_SEARCHING = 2
SEARCHMODE_NONE = 3
VOTE_LIMIT = -5

class TorrentSearchGridManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if TorrentSearchGridManager.__single:
            raise RuntimeError, "TorrentSearchGridManager is singleton"
        TorrentSearchGridManager.__single = self
        
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        # Remote results for current keywords
        self.remoteHits = {}
        self.stopped = False
        self.dod = None
        # Jelle's word filter
        self.searchmgr = None
        self.torrent_db = None
        self.pref_db = None # Nic: for rerankers
        self.mypref_db = None
        self.search_db = None
        # For asking for a refresh when remote results came in
        self.gridmgr = None

        self.standardOverview = None
        self.searchkeywords = {'filesMode':[], 'libraryMode':[]}
        self.rerankingStrategy = {'filesMode':DefaultTorrentReranker(), 'libraryMode':DefaultTorrentReranker()}
        self.oldsearchkeywords = {'filesMode':[], 'channelsMode':[], 'libraryMode':[]} # previous query

        self.category = Category.getInstance()

        #self.votecastdb= self.guiUtility.utility.session.open_dbhandler(NTFY_VOTECAST)
        #self.channelcastdb= self.guiUtility.utility.session.open_dbhandler(NTFY_CHANNELCAST)

        #self.votecastdb = VoteCastDBHandler.getInstance()
        #self.channelcastdb = ChannelCastDBHandler.getInstance()

        # 09/10/09 boudewijn: CallLater does not accept zero as a
        # delay. the value needs to be a positive integer.
        self.prefetch_callback = wx.CallLater(10, self.prefetch_hits)
        
        
    def getInstance(*args, **kw):
        if TorrentSearchGridManager.__single is None:
            TorrentSearchGridManager(*args, **kw)       
        return TorrentSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def register(self,torrent_db,pref_db,mypref_db,search_db,channelcast_db, votecast_db):
        self.torrent_db = torrent_db
        self.pref_db = pref_db
        self.mypref_db = mypref_db
        self.search_db = search_db
        self.searchmgr = SearchManager(torrent_db)
        self.channelcastdb = channelcast_db ##
        self.votecastdb = votecast_db ##
        
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def getHitsInCategory(self,mode,categorykey,range,sort,reverse):
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
        
        if not self.standardOverview:
            self.standardOverview = self.guiUtility.standardOverview
            
        

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
            
            #okGood = torrent['status'] == 'good' or torrent.get('myDownloadHistory', False)
            okGood = torrent['status'] != 'dead' or torrent.get('myDownloadHistory', False)
                        
            #print >>sys.stderr,"FILTER: lib",okLibrary,"cat",okCategory,"good",okGood
            return okLibrary and okCategory and okGood
        
        # 1. Local search puts hits in self.hits
        new_local_hits = self.searchLocalDatabase(mode)
        
        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: search found: %d items' % len(self.hits)

        if new_local_hits:
            # 2. Filter self.hits on category and status
            self.hits = filter(torrentFilter,self.hits)

        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: torrentFilter after filter found: %d items' % len(self.hits)
        
        self.standardOverview.setSearchFeedback('web2', self.stopped, -1, self.searchkeywords[mode])
        self.standardOverview.setSearchFeedback('remote', self.stopped, -1, self.searchkeywords[mode])
        if mode == 'filesMode':
            ##pass
            self.standardOverview.setSearchFeedback('torrent', self.stopped, len(self.hits), self.searchkeywords[mode])
        elif mode == 'libraryMode':
            # set finished true and use other string
            self.standardOverview.setSearchFeedback('library', True, len(self.hits), self.searchkeywords[mode])
            
        
        # 3. Add remote hits that may apply. TODO: double filtering, could
        # add remote hits to self.hits before filter(torrentFilter,...)

        if mode != 'libraryMode':
            self.addStoredRemoteResults(mode, categorykey)

            if DEBUG:
                print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: found after remote search: %d items' % len(self.hits)
        

                
#       if self.getSearchMode(mode) == SEARCHMODE_SEARCHING:
#            self.standardOverview.setSearchFeedback('torrent', True, len(self.hits))                
        
        if range[0] > len(self.hits):
            return [0,None]
        elif range[1] > len(self.hits):
            end = len(self.hits)
        else:
            end = range[1]
        begin = range[0]

        if DEBUG: beginsort = time()
        
        if sort == 'rameezmetric':
            self.sort()
#        else:
#            # Sort on columns in list view
#            cmpfunc = lambda a,b:torrent_cmp(a,b,sort)
#            self.hits.sort(cmpfunc,reverse=reverse)
#            
#        # Nic: Ok this is somewhat diagonal to the previous sorting algorithms
#        # eventually, these should probably be combined
#        # since for now, however, my reranking is very tame (exchanging first and second place under certain circumstances)
#        # this should be fine...
         
        self.rerankingStrategy[mode] = getTorrentReranker()
        self.hits = self.rerankingStrategy[mode].rerank(self.hits, self.searchkeywords[mode], self.torrent_db, 
                                                        self.pref_db, self.mypref_db, self.search_db)

        # boudewijn: now that we have sorted the search results we
        # want to prefetch the top N torrents.
        if not self.prefetch_callback.IsRunning():
            self.prefetch_callback.Start(1000)

        if DEBUG:
            print >> sys.stderr, 'getHitsInCat took: %s of which search %s' % ((time() - begintime), (time()-beginsort))
        return [len(self.hits),self.hits[begin:end]]
                

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
        if not self.guiUtility.standardDetails is None:
            if DEBUG: begin_time = time()
            download_torrentfile_from_peers = self.guiUtility.standardDetails._download_torrentfile_from_peers
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
                    hit['torrent_file_name'] = get_filename(hit['infohash']) 
                torrent_filename = os.path.join(torrent_dir, hit['torrent_file_name'])

                if not os.path.isfile(torrent_filename):
                    if download_torrentfile_from_peers(hit, sesscb_prefetch_done, duplicate=False):
                        prefetch_counter += 1
                        if DEBUG: print >> sys.stderr, "Prefetch: attempting to download", `hit["name"]`

                hit_counter += 1
                if prefetch_counter >= 10 or hit_counter >= 25:
                    # (1) prefetch a maximum of N hits
                    # (2) prefetch only from the first M hits
                    # (.) wichever is lowest or (1) or (2)
                    break

    def setSearchKeywords(self,wantkeywords, mode):
        self.stopped = False
#        if len(wantkeywords) == 0:
#            print_stack()
        
        self.searchkeywords[mode] = wantkeywords
        if mode == 'filesMode':
            print >> sys.stderr, "query:", self.searchkeywords[mode],";time:%", time()
            self.remoteHits = {}
            if self.dod:
                self.dod.clear()

    def getSearchMode(self, mode):
        # Return searching, stopped, or no search
        if self.standardOverview is None:
            if self.searchkeywords.get(mode):
                return SEARCHMODE_SEARCHING
        else:
            if self.searchkeywords.get(mode):
                if self.standardOverview.getSearchBusy():
                    return SEARCHMODE_SEARCHING
                else:
                    return SEARCHMODE_STOPPED
        return SEARCHMODE_NONE
            
         
    def stopSearch(self):
        self.stopped = True
        if self.dod:
            self.dod.stop()
     
    def getCurrentHitsLen(self):
        return len(self.hits)
    
    def searchLocalDatabase(self,mode):
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
        return True

    def addStoredRemoteResults(self, mode, cat):
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
                return icat == cat or cat == 'all'
            
            catResults = filter(catFilter, self.remoteHits.values())
            if DEBUG:
                print >> sys.stderr,"TorrentSearchGridManager: remote: Adding %d remote results (%d in category)" % (len(self.remoteHits), len(catResults))
            
            for remoteItem in catResults:
                known = False
                for item in self.hits:
                    #print >> sys.stderr,"TorrentSearchGridManager: remote: Should we add",`remoteItem['name']`
                    if item['infohash'] == remoteItem['infohash']:
                        known = True
                        # if a hit belongs to a more popular channel, then replace the previous
                        if remoteItem['channel_permid'] !="" and remoteItem['channel_name'] != "" and remoteItem['subscriptions']-remoteItem['neg_votes'] > item['subscriptions']-item['neg_votes']:
                            item['subscriptions'] = remoteItem['subscriptions']
                            item['neg_votes'] = remoteItem['neg_votes']
                            item['channel_permid'] = remoteItem['channel_permid']
                            item['channel_name'] = remoteItem['channel_name']
                        break
                if not known:
                    #print >> sys.stderr,"TorrentSearchGridManager: remote: Adding",`remoteItem['name']`
                    self.hits.append(remoteItem)
                    numResults+=1
            self.standardOverview.setSearchFeedback('remote', self.stopped, numResults, self.searchkeywords[mode])
        
    def gotRemoteHits(self,permid,kws,answers,mode):
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
                        filename = value['content_name']
                        filename = filename.lower()
                        import re
                        ls = re.split(r'\W+', filename)
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
                            

                    # Extra fiedl: Set from which peer this info originates
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
             
                if numResults > 0 and mode == 'filesMode': #  and self.standardOverview.getSearchBusy():
                    self.gridmgr.grid.allowDeselectAll = False
                    self.refreshGrid()
                    if DEBUG:
                        print >>sys.stderr,'TorrentSearchGridManager: gotRemoteHits: Refresh grid after new remote torrent hits came in'
                return True
            elif DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHits: got hits for",kws,"but current search is for",self.searchkeywords[mode]
            return False
        except:
            print_exc()
            return False
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            #print >>sys.stderr,"TorrentSearchGridManager: refreshGrid: gridmgr refresh"
            self.gridmgr.refresh()

            
    #
    # Move to Web2SearchGridManager
    #
    def searchWeb2(self,initialnum):
        
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: searchWeb2:",initialnum
        
        if self.dod:
            self.dod.stop()
        self.dod = web2.DataOnDemandWeb2(" ".join(self.searchkeywords['filesMode']),guiutil=self.guiUtility)
        self.dod.request(initialnum)
        self.dod.register(self.tthread_gotWeb2Hit)
        
    def tthread_gotWeb2Hit(self,item):
        """ Called by Web2DBSearchThread*s* """
        #if DEBUG:
        print >>sys.stderr,"TorrentSearchGridManager: tthread_gotWeb2Hit",`item['content_name']`

        wx.CallAfter(self.refreshGrid)
        
    def web2tonewdb(self,value):
        try:
            # Added protection against missing values
            newval = {}
            newval['infohash'] = value['infohash']
            newval['name'] = value['content_name']
            newval['status'] = value.get('status','unknown')
            newval['description'] = value.get('description','')
            newval['tags'] = value.get('tags',[])
            newval['url'] = value.get('url','')
            newval['num_leechers'] = value.get('leecher',1)
            newval['num_seeders'] = value.get('views',1)
            newval['creation_date'] = value.get('date','')
            newval['views'] = value.get('views',0)
            newval['web2'] = value.get('web2',True)
            newval['length'] = value.get('length',1)
            if 'preview' in value: # Apparently not always present
                newval['preview'] = value['preview']
            return newval
        except:
            print_exc()
            return None

    def addStoredWeb2Results(self,mode,categorykey,range):
        web2on = self.guiUtility.utility.config.Read('enableweb2search',"boolean")
        
        #if DEBUG:
        #    print >>sys.stderr,"TorrentSearchGridManager: getCategory: mode",mode,"webon",web2on,"insearch",self.getSearchMode(mode),"catekey",categorykey
        
        if mode == 'filesMode' and web2on and self.getSearchMode(mode) == SEARCHMODE_SEARCHING and \
            categorykey in ['video', 'all']:
            # if we are searching in filesmode
            #self.standardOverview.setSearchFeedback('web2', False, 0)
            
            if self.dod:
                # Arno: ask for more when needed (=only one page left to display)
                if DEBUG:
                    print >>sys.stderr,"TorrentSearchManager: web2: requestMore?",range[1],self.dod.getNumRequested()
                pagesize = range[1] - range[0]
                #diff = self.dod.getNumRequested() - range[1]
                #if diff <= pagesize:
                # JelleComment: above code doesnt work, because other search results are also on pages
                # so we might have 100 pages of local search results. If range is related to 80th page
                # websearch will try to get 80xpagesize youtube videos
                # Set it steady to 3 pages
                if self.dod.getNumRequested() < 3*pagesize:
                    if DEBUG:
                        print >>sys.stderr,"TorrentSearchManager: web2: requestMore diff",pagesize
                    self.dod.requestMore(pagesize)
                    
                data = self.dod.getData()
                if DEBUG:
                    print >>sys.stderr,"TorrentSearchManager: getHitsInCat: web2: Got total",len(data)
                numResults = 0
                for value in data:
                    
                    # Translate to NEWDB/FileItemPanel format, doing this in 
                    # web2/video/genericsearch.py breaks something
                    newval = self.web2tonewdb(value)
                    if newval is None:
                        continue

                    known = False
                    for item in self.hits:
                        if item['infohash'] == newval['infohash']:
                            known = True
                            break
                    if not known:
                        self.hits.append(newval)
                        numResults += 1

                self.standardOverview.setSearchFeedback('web2', self.stopped, numResults, self.searchkeywords[mode])
        #    else:
        #        print >>sys.stderr,"TorrentSearchManager: No web2 hits, no self.dod"
                
        #else:
        #    print >>sys.stderr,"TorrentSearchManager: No web2 hits, mode",mode,"web2on",web2on,"in search",self.getSearchMode(mode),"catkey",categorykey
    
    
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
            tot += hit[normKey]
        
        if len(hits) > 0:
            mean = tot/len(hits)
        else:
            mean = 0
        
        sum = 0
        for hit in hits:
            temp = hit[normKey] - mean
            temp = temp * temp
            sum += temp
        
        if len(hits) > 1:
            dev = sum /(len(hits)-1)
        else:
            dev = 0
        
        stdDev = sqrt(dev)
        
        for hit in hits:
            if stdDev > 0:
                hit[newKey] = (hit[normKey]-mean)/ stdDev
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
        # Remote results for current keywords
        self.remoteHits = {}
        self.stopped = False
        self.dod = None
        # Jelle's word filter
        self.searchmgr = None
        self.channelcast_db = None
        self.pref_db = None # Nic: for rerankers
        self.mypref_db = None
        self.search_db = None
        # For asking for a refresh when remote results came in
        self.gridmgr = None
        
        self.mychannel = None
        self.mysubscriptions = None 

        self.standardOverview = None
        self.searchkeywords = {'filesMode':[], 'channelsMode':[], 'libraryMode':[]}
        self.rerankingStrategy = {'filesMode':DefaultTorrentReranker(), 'libraryMode':DefaultTorrentReranker()}
        self.oldsearchkeywords = {'filesMode':[], 'channelsMode':[], 'libraryMode':[]} # previous query
        
        self.category = Category.getInstance()
        
    def getInstance(*args, **kw):
        if ChannelSearchGridManager.__single is None:
            ChannelSearchGridManager(*args, **kw)       
        return ChannelSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def register(self,channelcast_db,pref_db,mypref_db,search_db, votecast_db, torrent_db):
        self.channelcast_db = channelcast_db
        self.pref_db = pref_db
        self.mypref_db = mypref_db
        self.search_db = search_db
        self.searchmgr = SearchManager(channelcast_db)
        self.votecastdb = votecast_db
        self.torrent_db = torrent_db
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()
        
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    

    def getChannelHits(self,mode):
        begintime = time()
        
        if DEBUG:
            print >>sys.stderr,"ChannelSearchGridManager: getChannelHits:",mode
        
        
        if not self.standardOverview:
            self.standardOverview = self.guiUtility.standardOverview
            
        

        # 1. Local search puts hits in self.hits
        new_local_hits = self.searchLocalDatabase(mode)
        if DEBUG:
            print >> sys.stderr , "new_local_hits", new_local_hits
        
        if DEBUG:
            print >>sys.stderr,'ChannelSearchGridManager: getChannelHits: search found: %d items' % len(self.hits)

        
        self.standardOverview.setSearchFeedback('remotechannels', self.stopped, -1, self.searchkeywords[mode])
        if mode == 'channelsMode':
            self.standardOverview.setSearchFeedback('channels', self.stopped, len(self.hits), self.searchkeywords[mode])
        elif mode == 'libraryMode':
            # set finished true and use other string
            self.standardOverview.setSearchFeedback('library', True, len(self.hits), self.searchkeywords[mode])
            
        
        # 2. Add remote hits that may apply.
        if mode != 'libraryMode':
            self.addStoredRemoteResults(mode)

            if DEBUG:
                print >>sys.stderr,'ChannelSearchGridManager: getChannelHits: found after remote search: %d items' % len(self.hits)
        
      
        self.standardOverview.setSearchFeedback('channels', self.stopped, len(self.hits), self.searchkeywords[mode])


        if len(self.hits) == 0:
            return [0, None]
        else:        
            return [len(self.hits),self.hits]
                
    def getMyChannel(self, mode):
        if self.mychannel is None:
            print >> sys.stderr , "FIRST"
            self.mychannel = self.channelcast_db.getMyChannel()
        mychannel = self.mychannel
        return [1, mychannel]
 
    def getSubscriptions(self, mode):
        t1 = time()
        if self.mysubscriptions is None:
            self.mysubscriptions = self.channelcast_db.getMySubscribedChannels()
        t2 = time()
        if DEBUG:
            print >> sys.stderr , "getSubscriptions" , t2 - t1
        subscriptions = self.mysubscriptions
        return [len(subscriptions), subscriptions]

    def getPopularChannels(self, mode, maximum=20):
        t1 = time()
        pchannels = self.channelcast_db.getMostPopularUnsubscribedChannels()
        pchannels = pchannels[:maximum]
        t2 = time()
        if DEBUG:
            print >> sys.stderr , "getPopularChannels" , t2 - t1
        return [len(pchannels), pchannels]
               
    def setSearchKeywords(self,wantkeywords, mode):
        self.stopped = False
        self.searchkeywords[mode] = wantkeywords
        if mode == 'filesMode':
            self.remoteHits = {}
            if self.dod:
                self.dod.clear()

    def getSearchMode(self, mode):
        # Return searching, stopped, or no search
        if self.standardOverview is None:
            if self.searchkeywords.get(mode):
                return SEARCHMODE_SEARCHING
        else:
            if self.searchkeywords.get(mode):
                if self.standardOverview.getSearchBusy():
                    return SEARCHMODE_SEARCHING
                else:
                    return SEARCHMODE_STOPPED
        return SEARCHMODE_NONE
            
         
    def stopSearch(self):
        self.stopped = True
        if self.dod:
            self.dod.stop()
     
    def getCurrentHitsLen(self):
        return len(self.hits)
    
    def searchLocalDatabase(self,mode):
        """ Called by GetChannelHits() to search local DB. Caches previous query result. """
        if self.searchkeywords[mode] == self.oldsearchkeywords[mode]:  ## and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return False
        
        self.oldsearchkeywords[mode] = self.searchkeywords[mode]
        if DEBUG:
            print >>sys.stderr,"ChannelSearchGridManager: searchLocalDB: Want",self.searchkeywords[mode]
         
        if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
            return False

        query = "k:"
        for i in self.searchkeywords[mode]:
            query = query + i + ' '
        
        #self.hits = self.searchmgr.searchChannels(query)
        hits = self.searchmgr.searchChannels(query)
        self.hits = {}
        for hit in hits:
            if hit[0] not in hits:
                torrents = {}                 
                torrents[hit[2]] = (hit[4], hit[5]) # {infohash:(torrentname, timestamp)}
                self.hits[hit[0]] = [hit[1], self.votecastdb.getEffectiveVote(hit[0]), torrents]
            else:
                torrents = self.hits[hit[0]][2]
                if hit[2] not in torrents:
                    torrents[hit[2]] = (hit[4], hit[5])
                
        print >> sys.stderr , " LOCAL HITS" , self.hits
        return True




    def addStoredRemoteResults(self, mode):
        """ Called by getChannelHits() to add remote results to self.hits """
        if len(self.remoteHits) > 0:
            numResults = 0
            
            for remoteItem in self.remoteHits.keys():
                if remoteItem[0] not in self.hits:
                    torrents = {}
                    torrents[remoteItem[2]] = (remoteItem[4], remoteItem[5])
                    self.hits[remoteItem[0]] = [remoteItem[1], self.channelcast_db.getSubscribersCount(remoteItem[0]), torrents]
                else:
                    torrents = self.hits[remoteItem[0]][2]
                    if remoteItem[2] not in torrents:
                        torrents[remoteItem[2]] = (remoteItem[4], remoteItem[5])
                #self.hits.append(remoteItem)
                numResults+=1
            self.standardOverview.setSearchFeedback('remotechannels', self.stopped, numResults, self.searchkeywords[mode])
            self.remoteHits = {}
        
    def gotRemoteHits(self,permid,kws,answers,mode):
        """ Called by GUIUtil when hits come in. """
        ##print >> sys.stderr , "answers" , answers
        try:
            #if DEBUG:
            print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHist: got",len(answers),"for",kws
            
            # Always store the results, only display when in channelsMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords['channelsMode'] == kws:
                numResults = 0
                for el in answers:  
                    
#                    if self.channelcast_db.hasTorrent(infohash):
#                        if DEBUG:
#                            print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHist: Ignoring hit for",`value['content_name']`,"already got it"
#                        continue # do not show results we have ourselves
                    
                    # Convert answer fields as per 
                    # Session.chquery_connected_peers() spec. to NEWDB format
                    newval = {}
                    newval['publisher_id'] = el[0]                    
                    newval['publisher_name'] = el[1]                    
                    newval['infohash'] = el[2]
                    newval['torrenthash'] = el[3]
                    newval['torrentname'] = el[4]
                    newval['time_stamp'] = el[5]
                    newval['signature'] = el[6]
                    
                    self.remoteHits[el] = 1
                    numResults +=1
                    def usercallback(infohash,metadata,filename):
                        pass
                    if not self.torrent_db.hasTorrent(str2bin(el[2])):
                        self.rtorrent_handler.download_torrent(permid,str2bin(el[2]),usercallback)
#                    if newval['infohash'] in self.remoteHits:
#                        # merge this result with previous results
#                        oldval = self.remoteHits[newval['infohash']]
#                        for query_permid in newval['query_permids']:
#                            if not query_permid in oldval['query_permids']:
#                                oldval['query_permids'].append(query_permid)
#                    else:
#                        self.remoteHits[newval['infohash']] = el #newval
#                        numResults +=1

                if numResults > 0 and mode == 'channelsMode': #  and self.standardOverview.getSearchBusy():
                    self.refreshGrid()
                    if DEBUG:
                        print >>sys.stderr,'ChannelSearchGridManager: gotRemoteHits: Refresh grid after new remote channel hits came in'
                return True
            elif DEBUG:
                print >>sys.stderr,"ChannelSearchGridManager: gotRemoteHits: got hits for",kws,"but current search is for",self.searchkeywords[mode]
            return False
        except:
            print_exc()
            return False
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            print >>sys.stderr,"ChannelSearchGridManager: refreshGrid: gridmgr refresh"
            self.gridmgr.refresh()

            
    #
    # Move to Web2SearchGridManager
    #
    def searchWeb2(self,initialnum):
        
        if DEBUG:
            print >>sys.stderr,"ChannelSearchGridManager: searchWeb2:",initialnum
        
        if self.dod:
            self.dod.stop()
        self.dod = web2.DataOnDemandWeb2(" ".join(self.searchkeywords['filesMode']),guiutil=self.guiUtility)
        self.dod.request(initialnum)
        self.dod.register(self.tthread_gotWeb2Hit)
        
    def tthread_gotWeb2Hit(self,item):
        """ Called by Web2DBSearchThread*s* """
        #if DEBUG:
        print >>sys.stderr,"ChannelSearchGridManager: tthread_gotWeb2Hit",`item['content_name']`

        wx.CallAfter(self.refreshGrid)
        
    def web2tonewdb(self,value):
        try:
            # Added protection against missing values
            newval = {}
            newval['infohash'] = value['infohash']
            newval['name'] = value['content_name']
            newval['status'] = value.get('status','unknown')
            newval['description'] = value.get('description','')
            newval['tags'] = value.get('tags',[])
            newval['url'] = value.get('url','')
            newval['num_leechers'] = value.get('leecher',1)
            newval['num_seeders'] = value.get('views',1)
            newval['creation_date'] = value.get('date','')
            newval['views'] = value.get('views',0)
            newval['web2'] = value.get('web2',True)
            newval['length'] = value.get('length',1)
            if 'preview' in value: # Apparently not always present
                newval['preview'] = value['preview']
            return newval
        except:
            print_exc()
            return None

    def addStoredWeb2Results(self,mode,categorykey,range):
        web2on = self.guiUtility.utility.config.Read('enableweb2search',"boolean")
        
        #if DEBUG:
        #    print >>sys.stderr,"TorrentSearchGridManager: getCategory: mode",mode,"webon",web2on,"insearch",self.getSearchMode(mode),"catekey",categorykey
        
        if mode == 'filesMode' and web2on and self.getSearchMode(mode) == SEARCHMODE_SEARCHING and \
            categorykey in ['video', 'all']:
            # if we are searching in filesmode
            #self.standardOverview.setSearchFeedback('web2', False, 0)
            
            if self.dod:
                # Arno: ask for more when needed (=only one page left to display)
                if DEBUG:
                    print >>sys.stderr,"ChannelSearchManager: web2: requestMore?",range[1],self.dod.getNumRequested()
                pagesize = range[1] - range[0]
                #diff = self.dod.getNumRequested() - range[1]
                #if diff <= pagesize:
                # JelleComment: above code doesnt work, because other search results are also on pages
                # so we might have 100 pages of local search results. If range is related to 80th page
                # websearch will try to get 80xpagesize youtube videos
                # Set it steady to 3 pages
                if self.dod.getNumRequested() < 3*pagesize:
                    if DEBUG:
                        print >>sys.stderr,"ChannelSearchManager: web2: requestMore diff",pagesize
                    self.dod.requestMore(pagesize)
                    
                data = self.dod.getData()
                if DEBUG:
                    print >>sys.stderr,"ChannelSearchManager: getHitsInCat: web2: Got total",len(data)
                numResults = 0
                for value in data:
                    
                    # Translate to NEWDB/FileItemPanel format, doing this in 
                    # web2/video/genericsearch.py breaks something
                    newval = self.web2tonewdb(value)
                    if newval is None:
                        continue

                    known = False
                    for item in self.hits:
                        if item['infohash'] == newval['infohash']:
                            known = True
                            break
                    if not known:
                        self.hits.append(newval)
                        numResults += 1

                self.standardOverview.setSearchFeedback('web2', self.stopped, numResults, self.searchkeywords[mode])
        #    else:
        #        print >>sys.stderr,"TorrentSearchManager: No web2 hits, no self.dod"
                
        #else:
        #    print >>sys.stderr,"TorrentSearchManager: No web2 hits, mode",mode,"web2on",web2on,"in search",self.getSearchMode(mode),"catkey",categorykey
    
    #Rameez: The following code will call normalization functions and then 
    #sort and merge the combine torrent and youtube results
    def sort(self):
        self.normalizeResults()
        self.statisticalNormalization()
        #Rameez: now sort combined (i.e after the above two normalization procedures)

        #print >> sys.stderr, 'SearchGridMan: Search res: %s' % [a.get('normScore',0) for a in self.hits]
        def cmp(a,b):
            # normScores can be small, so multiply
            # No normscore gives negative 1000, because should be less than 0 (mean)
            return int(1000000.0 * (b.get('normScore',-1000) - a.get('normScore',-1000)))
        self.hits.sort(cmp)
        
        
                            
    
    def normalizeResults(self):
        torrent_total = 0
        youtube_total = 0
        KEY_NORMSCORE = 'normScore'
        
        #Rameez: normalize torrent results
        #Rameez: normalize youtube results
        for hit in self.hits:
            if not hit.has_key('views'):
                torrent_total += hit.get('num_seeders',0)
            elif hit['views'] != 'unknown':
                youtube_total += int(hit['views'])

        if torrent_total == 0: # if zero, set to one for divZeroExc. we can do this, cause nominator will also be zero in following division
            torrent_total = 1 
        if youtube_total == 0:
            youtube_total = 1
            
        for hit in self.hits:
            if not hit.has_key('views'):
                hit[KEY_NORMSCORE] = hit.get('num_seeders',0)/float(torrent_total)
            elif hit['views'] != 'unknown':
                hit[KEY_NORMSCORE] = int(hit['views'])/float(youtube_total)

    
        
    
    def statisticalNormalization(self):
        youtube_hits = [hit for hit in self.hits if (hit.get('views', 'unknown') != "unknown"
                                                     and hit.has_key('normScore'))]
        torrent_hits = [hit for hit in self.hits if (not hit.has_key('views')
                                                     and hit.has_key('normScore'))]
        self.doStatNormalization(youtube_hits)
        self.doStatNormalization(torrent_hits)

    def doStatNormalization(self, hits):
        #Rameez: statistically normalize torrent results
        
        count = 0
        tot = 0

        for hit in hits:
            tot += hit['normScore']
            count +=1
        
        if count > 0:
            mean = tot/count
        else:
            mean = 0
        
        sum = 0
        for hit in hits:
            temp = hit['normScore'] - mean
            temp = temp * temp
            sum += temp
        
        if count > 1:
            dev = sum /(count-1)
        else:
            dev = 0
        
        stdDev = sqrt(dev)
        
        for hit in hits:
            if stdDev > 0:
                hit['normScore'] = (hit['normScore']-mean)/ stdDev
        





class PeerSearchGridManager:

    # Code to make this a singleton
    __single = None
   
    def __init__(self,guiUtility):
        if PeerSearchGridManager.__single:
            raise RuntimeError, "PeerSearchGridManager is singleton"
        PeerSearchGridManager.__single = self
        
        self.guiUtility = guiUtility
        
        # Contains all matches for keywords in DB, not filtered by category
        self.hits = []
        # Jelle's word filter
        self.psearchmgr = None
        self.fsearchmgr = None
        self.stopped = False # not stopped by default
        self.gridmgr = None

        self.standardOverview = None
        self.searchkeywords = {'personsMode':[], 'friendsMode':[]}
        self.oldsearchkeywords = {'personsMode':[], 'friendsMode':[]} # previous query
        
        
    def getInstance(*args, **kw):
        if PeerSearchGridManager.__single is None:
            PeerSearchGridManager(*args, **kw)       
        return PeerSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def register(self,peer_db,friend_db):
        self.psearchmgr = SearchManager(peer_db)
        self.fsearchmgr = SearchManager(friend_db)

    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr

    
    def getHits(self,mode,range):
        # mode is 'personsMode', 'friendsMode'
        if DEBUG:
            print >>sys.stderr,"PeerSearchGridManager: getHitsIn:",mode,range
        
        if not self.standardOverview:
            self.standardOverview = self.guiUtility.standardOverview
            
        # Local search puts hits in self.hits
        self.searchLocalDatabase(mode)
        
        #print >>sys.stderr,"PeerSearchGridManager: searchLocalDB: GOT HITS",self.hits
        
        if DEBUG:
            print >>sys.stderr,'PeerSearchGridManager: getHitsInCat: search found: %d items' % len(self.hits)
        
        if DEBUG:
            print >>sys.stderr,'PeerSearchGridManager: getHitsInCat: torrentFilter after search found: %d items' % len(self.hits)

        if mode == 'personsMode':
            searchType = 'peers'
        elif mode == 'friendsMode':
            searchType = 'friends'
        self.standardOverview.setSearchFeedback(searchType, True, len(self.hits), self.searchkeywords[mode])
            
        if range[0] > len(self.hits):
            return [0,None]
        elif range[1] > len(self.hits):
            end = len(self.hits)
        else:
            end = range[1]
        begin = range[0]
        
        return [len(self.hits),self.hits[begin:end]]
                
                
    def setSearchKeywords(self,wantkeywords, mode):
        self.stopped = False
#        if len(wantkeywords) == 0:
#            print_stack()
        
        self.searchkeywords[mode] = wantkeywords

    def getSearchMode(self, mode):
        if bool(self.searchkeywords[mode]):
            if not self.stopped:
                mode = SEARCHMODE_SEARCHING
            else:
                mode = SEARCHMODE_STOPPED
        else:
            mode = SEARCHMODE_NONE
        #if DEBUG:
        #    print >>sys.stderr,"PeerSearchGridManager: getSearchMode?",mode
        return mode
         
    def stopSearch(self):
        print_stack()
        self.stopped = True

    def searchLocalDatabase(self,mode):
        """ Called by getHits() to search local DB. Caches previous query result. """
        if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"PeerSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return self.hits

        self.oldsearchkeywords[mode] = self.searchkeywords[mode]
        
        if DEBUG:
            print >>sys.stderr,"PeerSearchGridManager: searchLocalDB: Want",self.searchkeywords[mode]
        
        if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
            return self.hits
        
        if mode == 'personsMode':
            self.hits = self.psearchmgr.search(self.searchkeywords[mode])
        else: # friends
            self.hits = self.fsearchmgr.search(self.searchkeywords[mode])

        return self.hits
    
        
def torrent_cmp(a,b,sort):
    """ Compare torrent db records based on key "sort" """
    vala = a.get(sort,0)
    valb = b.get(sort,0)
    if vala == valb:
        return 0
    elif vala < valb:
        return -1
    else:
        return 1
    
    
