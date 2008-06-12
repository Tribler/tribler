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
    

DEBUG = True

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

    def register(self,torrent_db,gridmgr):
        self.torrent_db = torrent_db
        self.searchmgr = SearchManager(torrent_db)
        self.gridmgr = gridmgr
    
    def getHitsInCategory(self,mode,categorykey,range):
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
            
            print >>sys.stderr,"FILTER: lib",okLibrary,"cat",okCategory,"good",okGood
            return okLibrary and okCategory and okGood
        
        # 1. Local search puts hits in self.hits
        self.searchLocalDatabase(mode)
        
        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: search found: %d items' % len(self.hits)
        
        # 2. Filter self.hits on category and status
        self.hits = filter(torrentFilter,self.hits)

        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: torrentFilter after search found: %d items' % len(self.hits)
        
        self.standardOverview.setSearchFeedback('web2', False, -1, self.searchkeywords[mode])
        self.standardOverview.setSearchFeedback('remote', False, -1, self.searchkeywords[mode])
        if mode == 'filesMode':
            self.standardOverview.setSearchFeedback('torrent', False, len(self.hits), self.searchkeywords[mode])
        elif mode == 'libraryMode':
            # set finished true and use other string
            self.standardOverview.setSearchFeedback('library', True, len(self.hits), self.searchkeywords[mode])
            
        
        # 3. Add remote hits that may apply. TODO: double filtering, could
        # add remote hits to self.hits before filter(torrentFilter,...)
        
        self.addStoredRemoteResults(mode, categorykey)
        if DEBUG:
            print >>sys.stderr,'TorrentSearchGridManager: getHitsInCat: found after search: %d items' % len(self.hits)
        
        self.addStoredWeb2Results(mode,categorykey,range)
                
#       if self.inSearchMode(mode):
#            self.standardOverview.setSearchFeedback('torrent', True, len(self.hits))                
        
        if range[0] > len(self.hits):
            return [0,None]
        elif range[1] > len(self.hits):
            end = len(self.hits)
        else:
            end = range[1]
        begin = range[0]
        self.sort()
        return [len(self.hits),self.hits[begin:end]]
                
                
    def setSearchKeywords(self,wantkeywords, mode):
        
#        if len(wantkeywords) == 0:
#            print_stack()
        
        self.searchkeywords[mode] = wantkeywords
        if mode == 'filesMode':
            self.remoteHits = {}
            if self.dod:
                self.dod.clear()

    def inSearchMode(self, mode):
        return bool(self.searchkeywords.get(mode))
         
    def stopSearch(self):
        # TODO
        if self.dod:
            self.dod.stop()
     
    def getCurrentHitsLen(self):
        return len(self.hits)
    
    def searchLocalDatabase(self,mode):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return self.hits
            
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: searchLocalDB: Want",self.searchkeywords[mode]
        
        if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
            return self.hits
        
        self.hits = self.searchmgr.search(self.searchkeywords[mode])
        
        return self.hits

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
            self.standardOverview.setSearchFeedback('remote', False, numResults, self.searchkeywords[mode])
        
    def gotRemoteHits(self,permid,kws,answers,mode):
        """ Called by GUIUtil when hits come in. """
        print >>sys.stderr,"rmote each time, so we can call sort here, hehe" 
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
                    
                if mode == 'filesMode' and self.standardOverview.getSearchBusy():
                    self.refreshGrid()
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
        print >>sys.stderr,"TorrentSearchGridManager: notfyView ###########################",cmd,`value`

    #
    # Move to Web2SearchGridManager
    #
    def searchWeb2(self,initialnum):
        if self.dod:
            self.dod.stop()
        self.dod = web2.DataOnDemandWeb2(" ".join(self.searchkeywords['filesMode']),guiutil=self.guiUtility)
        self.dod.request(initialnum)
        self.dod.register(self.tthread_gotWeb2Hit)
        
    def tthread_gotWeb2Hit(self,item):
        """ Called by Web2DBSearchThread*s* """
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: tthread_gotWeb2Hit",`item['content_name']`
        print >>sys.stderr,"webondemand each time, so we can call sort here, hehe"
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
        newval['views'] = value['views']
        newval['web2'] = value['web2']
        newval['length'] = value['length']
        if 'preview' in value: # Apparently not always present
            newval['preview'] = value['preview']
        return newval

    def addStoredWeb2Results(self,mode,categorykey,range):
        web2on = self.guiUtility.utility.config.Read('enableweb2search',"boolean")
        
        #if DEBUG:
        #    print >>sys.stderr,"TorrentSearchGridManager: getCategory: mode",mode,"webon",web2on,"insearch",self.inSearchMode(mode),"catekey",categorykey
        
        if mode == 'filesMode' and web2on and self.inSearchMode(mode) and \
            categorykey in ['video', 'all']:
            # if we are searching in filesmode
            #self.standardOverview.setSearchFeedback('web2', False, 0)
            
            if self.dod:
                # Arno: ask for more when needed (=only one page left to display)
                if DEBUG:
                    print >>sys.stderr,"TorrentSearchManager: web2: requestMore?",range[1],self.dod.getNumRequested()
                pagesize = range[1] - range[0]
                diff = self.dod.getNumRequested() - range[1]
                if diff <= pagesize:
                    if DEBUG:
                        print >>sys.stderr,"TorrentSearchManager: web2: requestMore diff",diff
                    self.dod.requestMore(pagesize)
                    
                data = self.dod.getDataSafe()
                if DEBUG:
                    print >>sys.stderr,"TorrentSearchManager: getHitsInCat: web2: Got total",len(data)
                numResults = 0
                for value in data:
                    
                    # Translate to NEWDB/FileItemPanel format, doing this in 
                    # web2/video/genericsearch.py breaks something
                    newval = self.web2tonewdb(value)
                    self.hits.append(newval)
                    numResults += 1

                self.standardOverview.setSearchFeedback('web2', False, numResults, self.searchkeywords[mode])
    
    #Rameez: The following code will call normalization functions and then 
    #sort and merge the combine torrent and youtube results
    def sort(self):
        self.normalizeResults()
        self.statisticalNormalization()
        #Rameez: now sort combined (i.e after the above two normalization procedures)
        for i in range( len(self.hits)-1):
            for j in range (i+1, len(self.hits)):
                if self.hits[i].get('normScore') < self.hits[j].get('normScore'):
                    temp = self.hits[i]
                    self.hits[i]= self.hits[j]
                    self.hits[j] = temp
                            
    
    def normalizeResults(self):
        torrent_total = 0
        youtube_total = 0
        
        #Rameez: normalize torrent results
        for i in range(len(self.hits)):
            if not self.hits[i].has_key('views'):
                torrent_total += self.hits[i].get('num_seeders')
        
        for i in range(len(self.hits)):
            if not self.hits[i].has_key('views'):
                self.hits[i]['normScore'] = self.hits[i].get('num_seeders')/float(torrent_total)

        #Rameez: normalize youtube results
        for i in range(len(self.hits)):
            if self.hits[i].has_key('views') and self.hits[i].get('views') != "unknown":
                youtube_total += int(self.hits[i].get('views'))
        
        for i in range(len(self.hits)):
            if self.hits[i].has_key('views') and self.hits[i].get('views') != "unknown":
                self.hits[i]['normScore'] = self.hits[i].get('views')/float(youtube_total)
    
        
    
    def statisticalNormalization(self):
        count = 0
        tot = 0
        #Rameez: statistically normalize torrent results
        for i in range(len(self.hits)):
            if not self.hits[i].has_key('views'):
                if self.hits[i].has_key('normScore'):
                    tot += self.hits[i]['normScore']
                    count +=1
        
        if count > 0:
            mean = tot/count
        else:
            mean = 0
        
        sum = 0
        for i in range(len(self.hits)):
            if not self.hits[i].has_key('views'):
                if self.hits[i].has_key('normScore'):
                    temp = self.hits[i]['normScore'] - mean
                    temp = temp * temp
                    sum += temp
        
        if count > 1:
            dev = sum /(count-1)
        else:
            dev = 0
        
        stdDev = sqrt(dev)
        
        for i in range(len(self.hits)):
            if not self.hits[i].has_key('views'):
                if self.hits[i].has_key('normScore'):
                    if stdDev > 0:
                        self.hits[i]['normScore'] = (self.hits[i]['normScore']-mean)/ stdDev
        
        
        
        uCount = 0
        uTot = 0        
        #Rameez: statistically normalize youtube results
        for i in range(len(self.hits)):
            if self.hits[i].has_key('views') and self.hits[i].get('views') != "unknown":
                uTot += self.hits[i]['normScore'] 
                uCount += 1
        
        if uCount > 0:
            uMean = uTot/uCount
        else:
            uMean = 0
        
        uSum = 0
        
        
        for i in range(len(self.hits)):
            if self.hits[i].has_key('views') and self.hits[i].get('views') != "unknown":
                temp = self.hits[i]['normScore'] - uMean
                temp = temp * temp
                uSum += temp
        
        
        if uCount > 1:
            uDev = uSum /(uCount-1)
        else:
            uDev = 0
        
        ustdDev = sqrt(uDev)

        for i in range(len(self.hits)):
            if self.hits[i].has_key('views') and self.hits[i].get('views') != "unknown":
                if ustdDev > 0:
                    self.hits[i]['normScore'] = (self.hits[i]['normScore'] - uMean)/ustdDev



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
        
        self.gridmgr = None

        self.standardOverview = None
        self.searchkeywords = {'personsMode':[], 'friendsMode':[]}
        self.oldsearchkeywords = {'personsMode':[], 'friendsMode':[]} # previous query
        
        
    def getInstance(*args, **kw):
        if PeerSearchGridManager.__single is None:
            PeerSearchGridManager(*args, **kw)       
        return PeerSearchGridManager.__single
    getInstance = staticmethod(getInstance)

    def register(self,peer_db,friend_db,gridmgr):
        self.psearchmgr = SearchManager(peer_db)
        self.fsearchmgr = SearchManager(friend_db)
        self.gridmgr = gridmgr
    
    def getHits(self,mode,range):
        # mode is 'personsMode', 'friendsMode'
        if DEBUG:
            print >>sys.stderr,"PeerSearchGridManager: getHitsIn:",mode,range
        
        if not self.standardOverview:
            self.standardOverview = self.guiUtility.standardOverview
            
        # Local search puts hits in self.hits
        self.searchLocalDatabase(mode)
        
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

        if len(wantkeywords) == 0:
            print_stack()
        
        self.searchkeywords[mode] = wantkeywords

    def inSearchMode(self, mode):
        if DEBUG:
            print >>sys.stderr,"PeerSearchGridManager: inSearchMode?",self.searchkeywords[mode]
        
        return bool(self.searchkeywords[mode])
         
    def stopSearch(self):
        pass

    def searchLocalDatabase(self,mode):
        """ Called by getHits() to search local DB. Caches previous query result. """
        if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"PeerSearchGridManager: searchLocalDB: returning old hit list",len(self.hits)
            return self.hits
            
        if DEBUG:
            print >>sys.stderr,"PeerSearchGridManager: searchLocalDB: Want",self.searchkeywords[mode]
        
        if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
            return self.hits
        
        if mode == 'personsMode':
            self.hits = self.psearchmgr.search(self.searchkeywords[mode])
        else:
            self.hits = self.fsearchmgr.search(self.searchkeywords[mode])
        
        return self.hits
    
        
