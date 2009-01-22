# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information

import os
import sys
import wx
from traceback import print_exc, print_stack
from time import time

from Tribler.Category.Category import Category
from Tribler.Core.Search.SearchManager import SearchManager

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
        # For asking for a refresh when remote results came in
        self.gridmgr = None

        self.standardOverview = None
        self.searchkeywords = {'filesMode':[], 'libraryMode':[]}
        self.oldsearchkeywords = {'filesMode':[], 'libraryMode':[]} # previous query
        
        self.category = Category.getInstance()
        
    def getInstance(*args, **kw):
        if TorrentSearchGridManager.__single is None:
            TorrentSearchGridManager(*args, **kw)       
        return TorrentSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def register(self,torrent_db):
        self.torrent_db = torrent_db
        self.searchmgr = SearchManager(torrent_db)
        
    def set_gridmgr(self,gridmgr):
        self.gridmgr = gridmgr
    
    def getHitsInCategory(self,mode,categorykey,range,sort,reverse):
        begintime = time()
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
            okLibrary = not library or torrent.get('myDownloadHistory', False)
            
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
            
            okGood = torrent['status'] == 'good' or torrent.get('myDownloadHistory', False)
            
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
            self.standardOverview.setSearchFeedback('torrent', self.stopped, len(self.hits), self.searchkeywords[mode])
        elif mode == 'libraryMode':
            # set finished true and use other string
            self.standardOverview.setSearchFeedback('library', True, len(self.hits), self.searchkeywords[mode])
            
        
        # 3. Add remote hits that may apply. TODO: double filtering, could
        # add remote hits to self.hits before filter(torrentFilter,...)

        if mode != 'libraryMode':
            self.addStoredRemoteResults(mode, categorykey)
            self.addStoredWeb2Results(mode,categorykey,range)

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
        beginsort = time()
        
        if sort == 'rameezmetric':
            self.sort()
        else:
            # Sort on columns in list view
            cmpfunc = lambda a,b:torrent_cmp(a,b,sort)
            self.hits.sort(cmpfunc,reverse=reverse)
            
        #print >> sys.stderr, 'getHitsInCat took: %s of which search %s' % ((time() - begintime), (time()-beginsort))
        return [len(self.hits),self.hits[begin:end]]
                
                
    def setSearchKeywords(self,wantkeywords, mode):
        self.stopped = False
#        if len(wantkeywords) == 0:
#            print_stack()
        
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
                    if item['infohash'] == remoteItem['infohash']:
                        known = True
                        break
                if not known:
                    self.hits.append(remoteItem)
                    numResults+=1
            self.standardOverview.setSearchFeedback('remote', self.stopped, numResults, self.searchkeywords[mode])
        
    def gotRemoteHits(self,permid,kws,answers,mode):
        """ Called by GUIUtil when hits come in. """
        try:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got",len(answers)
            
            # Always store the results, only display when in filesMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords['filesMode'] == kws:
                numResults = 0
                catobj = Category.getInstance()
                for key,value in answers.iteritems():
                    
                    if self.torrent_db.hasTorrent(key):
                        continue # do not show results we have ourselves
                    
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

                    # Extra fiedl: Set from which peer this info originates
                    newval['query_permid'] = permid
                    if DEBUG:
                        print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: appending hit",`newval['name']`
                        #value['name'] = 'REMOTE '+value['name']
                        
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

                    # TODO: select best result?
                    if not (newval['infohash'] in self.remoteHits): 
                        self.remoteHits[newval['infohash']] = newval
                        #numResults +=1
                        #if numResults % 5 == 0:
                        #self.refreshGrid()
                    
                if mode == 'filesMode' and self.standardOverview.getSearchBusy():
                    self.refreshGrid()
                    if DEBUG:
                        print >>sys.stderr,'Refresh grid after new remote torrent hits came in'
                #    if self.notifyView(value, 'add'):
                #        numResults +=1
                #self.standardOverview.setSearchFeedback('remote', False, numResults, self.searchkeywords[mode])
                    
                return True
            elif DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got hits for",kws,"but current search is for",self.searchkeywords[mode]
            return False
        except:
            print_exc()
            return False
        
    def refreshGrid(self):
        if self.gridmgr is not None:
            self.gridmgr.refresh()
            

    def notifyView(self,value,cmd):
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: notfyView",cmd,`value`
        pass

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
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: tthread_gotWeb2Hit",`item['content_name']`

        wx.CallAfter(self.refreshGrid)
        
    def web2tonewdb(self,value):
        newval = {}
        newval['infohash'] = value['infohash']
        newval['name'] = value['content_name']
        newval['status'] = value['status']
        newval['description'] = value['description']
        newval['tags'] = value['tags']
        newval['url'] = value['url']
        newval['num_leechers'] = value['leecher']
        newval['num_seeders'] = value['views']
        newval['creation_date'] = value['date']
        newval['views'] = value['views']
        newval['web2'] = value['web2']
        newval['length'] = value['length']
        if 'preview' in value: # Apparently not always present
            newval['preview'] = value['preview']
        return newval

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
    
    
