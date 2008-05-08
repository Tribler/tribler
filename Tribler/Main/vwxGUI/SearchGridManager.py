# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information

import os
import sys
from traceback import print_exc, print_stack
from time import time

from Tribler.Category.Category import Category
from Tribler.Core.Search.SearchManager import SearchManager

try:
    import web2
except ImportError:
    print 'Could not import web2'
    

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
        self.searchmgr = SearchManager(torrent_db)
        self.gridmgr = gridmgr
    
    def getHitsInCategory(self,mode,categorykey,range):
        # mode is 'filesMode', 'libraryMode'
        # categorykey can be 'all', 'Video', 'Document', ...
        print >>sys.stderr,"TorrentSearchGridManager: getHitsInCategory:",mode,categorykey,range
        
        categorykey = categorykey.lower()
        enabledcattuples = self.category.getCategoryNames()
        enabledcatslow = ["other"]
        for catname,displayname in enabledcattuples:
            enabledcatslow.append(catname.lower())
        
        if not self.standardOverview:
            self.standardOverview = self.guiUtility.standardOverview
            
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
        
        #web2on = self.utility.config.Read('enableweb2search',"boolean")
        
        
        # ARNOTEMP
        web2on = False
        
        
        #if DEBUG:
        #    print >>sys.stderr,"TorrentSearchGridManager: getCategory: mode",mode,"webon",web2on,"insearch",self.inSearchMode(mode),"catekey",categorykey
        
        if mode == 'filesMode' and web2on and self.inSearchMode(mode) and \
            categorykey in ['video', 'all']:
            # if we are searching in filesmode
            self.standardOverview.setSearchFeedback('web2', False, 0)
            if self.dod:
                self.dod.stop()
                
            # TODO
                
            self.dod = web2.DataOnDemandWeb2(" ".join(self.searchkeywords[mode]))
            self.dod.addItems(self.hits)
            
            return [-1,self.dod] # TODO: totalitems?
             
        else:
            if self.dod:
                self.dod.stop()
                self.dod = None
                
#            if self.inSearchMode(mode):
#                self.standardOverview.setSearchFeedback('torrent', True, len(self.hits))                
            
            if range[0] > len(self.hits):
                return [0,None]
            elif range[1] > len(self.hits):
                end = len(self.hits)
            else:
                end = range[1]
            begin = range[0]
            
            return [len(self.hits),self.hits[begin:end]]
                
                
    def setSearchKeywords(self,wantkeywords, mode):
        self.searchkeywords[mode] = wantkeywords
        if mode == 'filesMode':
            self.remoteHits = {}
         
    def stopSearch(self):
        # TODO
        if self.dod:
            dod.stop()
         
    def inSearchMode(self, mode):
        return bool(self.searchkeywords[mode])
    
    def searchLocalDatabase(self,mode):
        """ Called by GetHitsInCategory() to search local DB. Caches previous query result. """
        if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: search: returning old hit list",len(self.hits)
            return self.hits
            
        if DEBUG:
            print >>sys.stderr,"TorrentSearchGridManager: search: Want",self.searchkeywords[mode]
        
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
                print >> sys.stderr, "Adding %d remote results (%d in category)" % (len(self.remoteHits), len(catResults))
            
            
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
        try:
            if DEBUG:
                print >>sys.stderr,"TorrentSearchGridManager: gotRemoteHist: got",len(answers)
            
            # Always store the results, only display when in filesMode
            # We got some replies. First check if they are for the current query
            if self.searchkeywords['filesMode'] == kws:
                numResults = 0
                catobj = Category.getInstance()
                for key,value in answers.iteritems():
                    
                    if self.searchmgr.has_torrent(key):
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
        