# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat, Arno Bakker
# see LICENSE.txt for license information

#
# WARNING: To save memory, the torrent records read from database and kept in
# memory here have some fields removed. In particular, 'info' and for buddycasted
# torrents also 'torrent_dir' and 'torrent_name'. Saves 50MB on 30000 torrent DB.
# 

import os
import sys
from base64 import encodestring
from copy import deepcopy
from traceback import print_exc, print_stack
from time import time
from bisect import insort
from sets import Set
from threading import Event

from Tribler.Core.Utilities.utilities import friendly_time, sort_dictlist, remove_torrent_from_list, find_content_in_dictlist
from Tribler.Core.Utilities.unicode import str2unicode, dunno2unicode
from Tribler.Main.Utility.constants import * #IGNORE:W0611
from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler
from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
from Tribler.Core.CacheDB.EditDist import editDist
from Tribler.Core.Search.KeywordSearch import KeywordSearch
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge

try:
    import web2
except ImportError:
    print 'Could not import web2'
    

DEBUG = True
DEBUG_RANKING = False

# Arno: save memory by reusing dict keys
# In principe, these should only be used in assignments, e.g. 
#     torrent[key_length] = 481
# In other cases you can just use 'length'.
key_length = 'length'
key_content_name = 'name'
key_torrent_name = 'torrent_name'
key_num_files = 'num_files'
key_date = 'date'
key_tracker = 'tracker'
key_leecher = 'num_leechers'
key_seeder = 'num_seeders'
key_swarmsize ='swarmsize'
key_relevance = 'relevance'
key_infohash = 'infohash'
key_myDownloadHistory = 'myDownloadHistory'
key_eventComingUp = 'eventComingUp'
key_simRank = 'simRank'
key_secret = 'secret'
key_abctorrent = 'abctorrent'

class TorrentDataManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self, utility):
        if TorrentDataManager.__single:
            raise RuntimeError, "TorrentDataManager is singleton"
        TorrentDataManager.__single = self
        self.done_init = False
        self.utility = utility
        self.rankList = []
        self.isDataPrepared = Event()
        self.data = []    # [{torrent}]
        #self.complete_data = [] # temporary storage
        self.loading_count = 1
        self.loading_count_db = 0
        self.is_data_prepared = False
        self.hits = []
        self.remoteHits = None
        self.dod = None
        self.keywordsearch = KeywordSearch()
        # initialize the cate_dict
        self.info_dict = {}    # reverse map
        self.title_dict = {} # for similar titles search
        self.initDBs()
        self.dict_FunList = {}
        self.titleIndexLength = 4
        self.done_init = True
        self.standardOverview = None
        self.searchkeywords = {'filesMode':[], 'libraryMode':[]}
        self.oldsearchkeywords = {'filesMode':[], 'libraryMode':[]} # previous query
        
        self.collected_torrent_dir = self.utility.session.get_torrent_collecting_dir()
        
        if DEBUG:
            print >>sys.stderr,'torrentManager: ready init', self.collected_torrent_dir

        
    def getInstance(*args, **kw):
        if TorrentDataManager.__single is None:
            TorrentDataManager(*args, **kw)       
        return TorrentDataManager.__single
    getInstance = staticmethod(getInstance)

    def initDBs(self):
        time1 = time()
        self.torrent_db = TorrentDBHandler.getInstance()
        self.owner_db = None#OwnerDBHandler.getInstance()
        self.category = Category.getInstance(self.utility.session.get_install_dir(), self.utility.session.get_state_dir())
        
    def ___loadData(self):
        """ Load torrent data to cache for GUI. Called by DataLoadingThread (see standardOverview) """
        try:
            self.data = self.torrent_db.loadTorrents()#(light=True,myprefs=True)
            self.is_data_prepared = True
            self.prepareData(self.data,rank=True)
            self.loading_count = len(self.data)
            self.isDataPrepared.set()
            
            self.prepareData(self.data)
        except:
            print_exc()
            raise Exception('Could not load torrent data !!')

    def ___prepareData(self,data,rank=True):
        
        count = 0
        for torrent in data:      
            # prepare to display
            torrent = self.prepareItem(torrent)
            self.info_dict[torrent["infohash"]] = torrent
            # save dict for similar titles search
            beginTitle = torrent['name'][:self.titleIndexLength].lower()
            if self.title_dict.has_key(beginTitle):
                self.title_dict[beginTitle].append(torrent)
            else:
                self.title_dict[beginTitle] = [torrent]
            if rank:
                self.updateRankList(torrent, 'add', initializing = True)
                #self.printRankList()
        
            count += 1
            if count % 1000 == 0:
                print >>sys.stderr,"torrentManager: prepared item",count
                self.loading_count = self.loading_count_db + count/2

        count = 0
        for torrent in data:      
            # prepare to display
            #torrent = self.cleanItem(torrent)

            count += 1
            if count % 1000 == 0:
                #print >>sys.stderr,"torrentManager: clean item",count
                self.loading_count = self.loading_count_db + count/2


    def loadingCountCallback(self,count):
        self.loading_count = count/2
        self.loading_count_db = self.loading_count 

#    def mergeData(self):
#        """ Called by MainThread """
#        print >>sys.stderr,"torrentManager: mergeData"
#        infohashes = []
#        
#        # Which torrents are already in self.data?
#        for torrent in self.data:
#            infohashes.append(torrent['infohash'])
#
#        # Delete already loaded torrents from complete_data    
#        i = 0
#        while i < len(self.complete_data):
#            if self.complete_data[i]['infohash'] in infohashes:
#                print >>sys.stderr,"torrentManager: mergeData: Removing",`self.complete_data[i]['name']`
#                del self.complete_data[i]
#            else:
#                i += 1
#            
#            if i % 1000 == 0:
#                print >> sys.stderr,"torrentManager: mergeData: Purged items",i
#            
#        # Add complete_data to self.data
#        self.data.extend(self.complete_data)
#        self.is_data_prepared = True

        
    def getDownloadHistCount(self):
        #[mluc]{26.04.2007} ATTENTION: data is not updated when a new download starts, although it should
        def isDownloadHistory(torrent):
            return torrent.has_key('myDownloadHistory')
        return len(filter(isDownloadHistory,self.data))
    
    def getRecommendFilesCount(self):
        count = 0
        for torrent in self.data:
            if torrent.has_key('relevance'):
                if torrent['relevance']> 5: #minmal value for a file to be considered tasteful
                    count = count + 1
        return count
        
   
    
    def ___getCategory(self, categorykey, mode):
        # categorykey can be 'all', 'Video', 'Document', ...
        # mode is 'filesMode', 'libraryMode'
        # Jie TODO:
        if not self.done_init:
            return []
        
        categorykey = categorykey.lower()
        enabledcattuples = self.category.getCategoryNames()
        enabledcatslow = ["other"]
        for catname,displayname in enabledcattuples:
            enabledcatslow.append(catname.lower())
        
        if not self.standardOverview:
            self.standardOverview = self.utility.guiUtility.standardOverview
            
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
        
        data = filter(torrentFilter, self.data)
        
        if DEBUG:
            print >>sys.stderr,'torrentManager: getCategory found: %d items' % len(data)
        # if searchkeywords are defined. Search instead of show all
        if self.inSearchMode(mode):
                data = self.search(data, mode)    #TODO RS: does it come from remote search or local search?
                self.standardOverview.setSearchFeedback('web2', False, -1, self.searchkeywords[mode])
                self.standardOverview.setSearchFeedback('remote', False, -1, self.searchkeywords[mode])
                if mode == 'filesMode':
                    self.standardOverview.setSearchFeedback('torrent', False, len(data), self.searchkeywords[mode])
                elif mode == 'libraryMode':
                    # set finished true and use other string
                    self.standardOverview.setSearchFeedback('library', True, len(data), self.searchkeywords[mode])
                    
                
                self.addRemoteResults(data, mode, categorykey)
                if DEBUG:
                    print >>sys.stderr,'torrentManager: getCategory found after search: %d items' % len(data)
        
        web2on = self.utility.config.Read('enableweb2search',"boolean")
        
        
        # ARNOTEMP
        web2on = False
        
        
        #if DEBUG:
        #    print >>sys.stderr,"torrentManager: getCategory: mode",mode,"webon",web2on,"insearch",self.inSearchMode(mode),"catekey",categorykey
        
        if mode == 'filesMode' and web2on and self.inSearchMode(mode) and \
                categorykey in ['video', 'all']:
                # if we are searching in filesmode
                self.standardOverview.setSearchFeedback('web2', False, 0)
                if self.dod:
                    self.dod.stop()
                self.dod = web2.DataOnDemandWeb2(" ".join(self.searchkeywords[mode]))
                self.dod.addItems(data)
                
                return self.dod
             
        else:
            if self.dod:
                self.dod.stop()
                self.dod = None
                
#            if self.inSearchMode(mode):
#                self.standardOverview.setSearchFeedback('torrent', True, len(data))                
            
            return data
                
    def getTorrents(self, hash_list):
        """builds a list with torrents that have the infohash in the list provided as an input parameter"""
        torrents_list = []
        for torrent_data in self.data:
            if torrent_data['infohash'] in hash_list:
                torrents_list.append(torrent_data)
        return torrents_list
            
    def getTorrent(self, infohash):
        return self.torrent_db.getTorrent(infohash)

    def deleteTorrent(self, infohash, delete_file=False):
        self.torrent_db.deleteTorrent(infohash, delete_file)

    # register update function
    def register(self, fun, key, library):
        if DEBUG:
            print >>sys.stderr,'torrentManager: Registered for key: %s' % key
        try:
            key = key.lower()
            self.dict_FunList[(key, library)].index(fun)
            # if no exception, fun already exist!
            if DEBUG:
                print >>sys.stderr,"torrentManager: register error. " + str(fun.__name__) + " already exist for key %s!" % str((key, library))
            return
        except KeyError:
            self.dict_FunList[(key, library)] = []
            self.dict_FunList[(key, library)].append(fun)
        except ValueError:
            self.dict_FunList[(key, library)].append(fun)
        except Exception, msg:
            if DEBUG:
                print >>sys.stderr,"torrentDataManager: register error.", Exception, msg
            print_exc()
        
        
    def unregister(self, fun, key, library):
        if DEBUG:
            print >>sys.stderr,'torrentDataManager: Unregistered for key: %s' % key
        try:
            key = key.lower()
            self.dict_FunList[(key, library)].remove(fun)
        except Exception, msg:
            if DEBUG:
                print >>sys.stderr,"torrentDataManager: unregister error.", Exception, msg
            print_exc()
            
    def unregisterAll(self, fun):
        rem = 0
        for tuple, funList in self.dict_FunList.iteritems():
            if fun in funList:
                funList.remove(fun)
                rem+=1
        if DEBUG:
            print >>sys.stderr,'torrentDataManager: UnregisteredAll function %s (%d unregisters)' % (fun.__name__, rem)
            
    def updateFun(self, infohash, operate):
        
        if not self.done_init:    # don't call update func before init finished
            return
        if not self.isDataPrepared.isSet():
            return
        if DEBUG:
            print "torrentDataManager: updateFun called, param", operate,currentThread().getName()
        if self.info_dict.has_key(infohash):
            if operate == 'add':
                self.addItem(infohash)
            elif operate == 'update':
                self.updateItem(infohash)
            elif operate == 'delete':
                self.deleteItem(infohash)
        else:
            if operate == 'update' or operate == 'delete':
                pass
            else:
                self.addItem(infohash)
                
    def notifyView(self, torrent, operate, libraryDelete = False):        
#        if torrent["category"] == ["?"]:
#            torrent["category"] = self.category.calculateCategory(torrent["info"], torrent["info"]['name'])
        
        isLibraryItem = torrent.get('myDownloadHistory', libraryDelete)
        categories = torrent.get('category', ['other']) + ["all"]
        funCalled = False
        
        for key in categories:
#            if key == '?':
#                continue
            try:
                key = key.lower()
                if isLibraryItem:
                    for fun in self.dict_FunList.get((key, True), []): # call all functions for a certain key
                        fun(torrent, libraryDelete and 'delete' or operate)
                        funCalled = True
                # Always notify discovered files (also for library items)
                for fun in self.dict_FunList.get((key, False), []):
                    fun(torrent, operate)
                    funCalled = True
                    
            except Exception, msg:
                #print >> sys.stderr, "abcfileframe: TorrentDataManager update error. Key: %s" % (key), Exception, msg
                #print_exc()
                pass
            
        return funCalled # return if a view was actually notified
    
    def addItem(self, infohash):
        if self.info_dict.has_key(infohash):
            return
        torrent = self.getTorrent(infohash)
        if not torrent:
            return
        item = self.prepareItem(torrent)
        self.data.append(item)
        self.info_dict[infohash] = item
        self.updateRankList(item, 'add')
        self.notifyView(item, 'add')
    
    
    def setBelongsToMyDowloadHistory(self, infohash, b, secret = False):
        """Set a certain new torrent to be in the download history or not
        Should not be changed by updateTorrent calls"""
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        
        if b:
            old_torrent[key_myDownloadHistory] = True
        else:
            if old_torrent.has_key(key_myDownloadHistory):
                del old_torrent[key_myDownloadHistory]
        
        self.notifyView(old_torrent, 'update', libraryDelete = not b)
        
        
        self.updateRankList(old_torrent, 'update')

#        Jie TODO: let buddycast know the deleted torrent
#        if b:    # update buddycast after view was updated
#            #self.utility.buddycast.addMyPref(infohash)    # will be called somewhere
#            pass
#        else:
#            print >> sys.stderr, self.utility
#            self.utility.buddycast.delMyPref(infohash)
#            
                
    def addNewPreference(self, infohash): 
        if self.info_dict.has_key(infohash):
            return
        torrent = self.getTorrent(infohash)
        if not torrent:
            return
        item = self.prepareItem(torrent)
        torrent[key_myDownloadHistory] = True
        self.data.append(item)
        self.info_dict[infohash] = item
        self.notifyView(item, 'add')
        
    def updateItem(self, infohash):
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        torrent = self.getTorrent(infohash)
        if not torrent:
            return
        item = self.prepareItem(torrent)
        
        #old_torrent.update(item)
        for key in torrent.keys():    # modify reference
            old_torrent[key] = torrent[key]
    
        self.updateRankList(torrent, 'update')
        self.notifyView(old_torrent, 'update')
    
    def deleteItem(self, infohash):
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        self.info_dict.pop(infohash)
        # Replaces remove() function because of unicode error
        #self.data.remove(old_torrent)
        remove_torrent_from_list(self.data, old_torrent)
        self.updateRankList(old_torrent, 'delete')
        self.notifyView(old_torrent, 'delete')

    def prepareItem(self, torrent):    # change self.data
        
#        info = torrent['info']
#        if not info.get('name'):
#            print 'torrentMgr: Error in torrent. No name found',info.get('name')
#        
#        torrent[key_length] = info.get('length', 0)
        torrent[key_content_name] = dunno2unicode(torrent.get('name', '?'))
        if key_torrent_name not in torrent or torrent[key_torrent_name] == '':
            torrent[key_torrent_name] = '?'
            print_stack()
            print >> sys.stderr, torrent, key_torrent_name not in torrent, `torrent[key_torrent_name]`
#        torrent[key_num_files] = int(info.get('num_files', 0))
#        torrent[key_date] = info.get('creation date', 0) 
#        torrent[key_tracker] = info.get('announce', '')
#        torrent[key_leecher] = torrent.get('num_leechers', -1)
#        torrent[key_seeder] = torrent.get('num_seeders', -1)
        torrent[key_swarmsize] = torrent['num_seeders'] + torrent['num_leechers']

        # No deletions here, that slows down enormously
        
        # Thumbnail is read from file only when it is shown on screen by
        # thumbnailViewer or detailsPanel
        return torrent


    def cleanItem(self, torrent):    # change self.data
        # Arno: to save mem I delete some fields here
        del torrent['info']
        
        if 'torrent_dir' in torrent and torrent['torrent_dir'] == self.collected_torrent_dir:
            # Will be determined on the fly
            #print "torrentManager: deleting torrent_dir"
            del torrent['torrent_dir']
            del torrent['torrent_name']

         
    def updateRankList(self, torrent, operate, initializing = False):
        "Update the ranking list, so that it always shows the top20 most similar torrents"
        
        if DEBUG_RANKING:
            print >>sys.stderr,'torrentManager: UpdateRankList: %s, for: %s' % (operate, repr(torrent.get('name')))
        
        sim = torrent.get('relevance')
        good = sim > 0 and torrent.get('status') == 'good' and not torrent.get('myDownloadHistory', False)
        infohash = torrent.get('infohash')
        updated = False
        dataTuple = (sim, infohash)
        
        if operate == 'add' and good:
            insort(self.rankList, dataTuple)
            
        
        elif operate == 'update':
            # Check if not already there
            for rankedTuple in self.rankList:
                infohashRanked = rankedTuple[1]
                if infohash == infohashRanked:
                    updated = True
                    self.rankList.remove(rankedTuple)
                    self.updateRemovedItem(infohash, initializing)
                    self.recompleteRankList()
                    break
                    
            if good:
                # be sure that ungood torrents are at the bottom of the list
                insort(self.rankList, dataTuple)
            
        elif operate == 'delete':
            for rankedTuple in self.rankList:
                infohashRanked = rankedTuple[1]
                if infohash == infohashRanked:
                    updated = True
                    self.rankList.remove(rankedTuple)
                    self.updateRemovedItem(infohash, initializing)
                    self.recompleteRankList()
                    break
                
                
        # Always leave rankList with <=20 items
        #assert initializing or len(self.data) < 20 or len(self.rankList) in [20,21],'torrentManager: Error, ranklist had length: %d' % len(self.rankList)
        
        droppedItemInfohash = None
        if len(self.rankList) == 21:
            (sim, droppedItemInfohash) = self.rankList.pop(0)

            
        if updated or dataTuple in self.rankList:
            # Only update the items when something changed in the ranking list

            if droppedItemInfohash:
                # if we have added a new ranked item, one is dropped out of the list
                # the rank of this one will be removed
                self.updateRemovedItem(droppedItemInfohash, initializing)
                
            self.updateRankedItems(initializing)
#            if not initializing:
#                print 'RankList is now: %s' % self.rankList
        
        if DEBUG_RANKING:
            self.printRankList()
        
    def updateRemovedItem(self, infohash, initializing):
        if self.info_dict.has_key(infohash):
            torrent = self.info_dict[infohash]
            if DEBUG_RANKING:
                print >>sys.stderr,'torrentManager: Del rank %d of %s' % (torrent.get('simRank', -1), repr(torrent.get('name')))
            if torrent.has_key('simRank'):
                del torrent['simRank']
            if not initializing:
                self.notifyView(torrent, 'update')
        elif DEBUG_RANKING:
            raise Exception('(removeRank) Not found infohash: %s in info_dict.' % repr(infohash))
            
    
    def updateRankedItems(self, initializing):
        rank = len(self.rankList)
        for (sim, infohash) in self.rankList:
            if self.info_dict.has_key(infohash):
                torrent = self.info_dict[infohash]
                if DEBUG_RANKING:
                    print >>sys.stderr,'torrentManager: Give rank %d to %s' % (rank, repr(torrent.get('name')))
                torrent[key_simRank] = rank
                if not initializing:
                    self.notifyView(torrent, 'update')
            else:
                raise Exception('Not found infohash: %s in info_dict.' % repr(infohash))
            rank -= 1
        
            
            
    def recompleteRankList(self):
        """
        Get most similar item with status=good, not in library and not in ranklist 
        and insort it in ranklist
        """
        highest_sim = 0
        highest_infohash = None
        for torrent in self.data:
            sim = torrent.get('relevance')
            good = torrent.get('status') == 'good' and not torrent.get('myDownloadHistory', False)
            infohash = torrent.get('infohash')
            
            if sim > 0 and good and (sim, infohash) not in self.rankList:
                # item is not in rankList
                if sim > highest_sim:
                    highest_sim = sim
                    highest_infohash = infohash
                    
        if highest_infohash:
            insort(self.rankList, (highest_sim, highest_infohash))
        
    def printRankList(self):
        self.rankList.reverse()
        print >>sys.stderr,'torrentManager: Ranklist:'
        rank = 1
        
        for (sim, infohash) in self.rankList:
            if self.info_dict.has_key(infohash):
                torrent = self.info_dict[infohash]
                print >>sys.stderr,'torrentManager: %d: %.2f, %s' % (rank, torrent.get('relevance', -1), repr(torrent.get('name', 'no name')))
            else:
                print_stack()
                print >>sys.stderr,'torrentManager: Not found infohash: %s in info_dict.' % repr(infohash)
            rank += 1
        
        self.rankList.reverse()
        
        print >>sys.stderr,'torrentManager: Checking all torrents'
        wrong = right = 0
        for infohash, torrent in self.info_dict.items():
            inRankList = False
            for (s, infohashRanked) in self.rankList:
                if infohash == infohashRanked:
                    inRankList = True
            if not inRankList:
                if torrent.has_key('simRank'):
                    wrong += 1
                    print >>sys.stderr,'torrentManager: Torrent %s was not in ranklist: sim: %f, rank: %d' % (repr(torrent.get('name')), torrent.get('relevance'), torrent['simRank'])
                else:
                    right+=1
        print >>sys.stderr,'torrentManager: %d right, %d wrong torrents' % (right, wrong)
        if wrong > 0:
            raise Exception('wrong torrents')
            
    def setSearchKeywords(self,wantkeywords, mode):
        self.searchkeywords[mode] = wantkeywords
         
    def inSearchMode(self, mode):
        return bool(self.searchkeywords[mode])
    
    def search(self, data, mode):
#        if self.searchkeywords[mode] == self.oldsearchkeywords[mode] and len(self.hits) > 0:
#            if DEBUG:
#                print >>sys.stderr,"torrentDataManager: search: returning old hit list",len(self.hits)
#            return self.hits
            
        if DEBUG:
            print >>sys.stderr,"torrentDataManager: search: Want",self.searchkeywords[mode]
        
        if len(self.searchkeywords[mode]) == 0 or len(self.searchkeywords[mode]) == 1 and self.searchkeywords[mode][0] == '':
            return data
        
        self.hits = self.keywordsearch.search(data, self.searchkeywords[mode])
        
        return self.hits

    def addRemoteResults(self, data, mode, cat):
        if self.remoteHits and self.remoteHits[0] == self.searchkeywords[mode]:
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
            
            catResults = filter(catFilter, self.remoteHits[1])
            if DEBUG:
                print >> sys.stderr, "Adding %d remote results (%d in category)" % (len(self.remoteHits[1]), len(catResults))
            
            
            for remoteItem in catResults:
                if find_content_in_dictlist(data, remoteItem) == -1:
                    data.append(remoteItem)
                    numResults+=1
            self.standardOverview.setSearchFeedback('remote', False, numResults, self.searchkeywords[mode])
        
        
    def remoteSearch(self,kws,maxhits=None):
        if DEBUG:
            print >>sys.stderr,"torrentDataManager: remoteSearch",kws
        
        haystack = []
        for torrent in self.data:
            if torrent['status'] != 'good':
                continue
            haystack.append(torrent)
        hits = self.keywordsearch.search(haystack,kws)
        if maxhits is None:
            return hits
        else:
            return hits[:maxhits]

    
    def gotRemoteHits(self,permid,kws,answers,mode='filesMode'):
        """ Called by standardOverview """
        try:
            if DEBUG:
                print >>sys.stderr,"torrentDataManager: gotRemoteHist: got",len(answers)
            
            # We got some replies. First check if they are for the current query
            if self.searchkeywords[mode] == kws and self.standardOverview.getSearchBusy():
                self.remoteHits = (self.searchkeywords[mode], [])
                numResults = 0
                catobj = Category.getInstance()
                for key,value in answers.iteritems():
                    
                    if self.info_dict.has_key(key):
                        continue # do not show results we have ourselves
                    
                    value['infohash'] = key
                    # Set from which peer this info originates
                    value['query_permid'] = permid
                    # We trust the peer
                    value['status'] = 'good'
                    
                    # Add values to enable filters (popular/rec/size) to work
                    value['swarmsize'] = value['num_seeders']+value['num_leechers']
                    value['relevance'] = 0
                    value['date'] = None # gives '?' in GUI
                    
                    if DEBUG:
                        print >>sys.stderr,"torrentDataManager: gotRemoteHist: appending hit",`value['name']`
                        #value['name'] = 'REMOTE '+value['name']
                        
                    # Filter out results from unwanted categories
                    flag = False
                    for cat in value['category']:
                        rank = catobj.getCategoryRank(cat)
                        if rank == -1:
                            if DEBUG:
                                print >>sys.stderr,"torrentDataManager: gotRemoteHits: Got",`value['name']`,"from banned category",cat,", discarded it."
                            flag = True
                            break
                    if flag:
                        continue
                        
                    self.hits.append(value)
                    self.remoteHits[1].append(value)
                    if self.notifyView(value, 'add'):
                        numResults +=1
                self.standardOverview.setSearchFeedback('remote', False, numResults, self.searchkeywords[mode])
                return True
            elif DEBUG:
                print >>sys.stderr,"torrentDataManager: gotRemoteHist: got hits for",kws,"but current search is for",self.searchkeywords[mode]
            return False
        except:
            print_exc()
            return False

    def getFromSource(self,source):
        hits = []
        for torrent in self.data:
            if torrent['source'] == source:
                hits.append(torrent)
        return hits
    
    def getSimItems(self, infohash, num=15):
        # TODO:
        return []
        return self.owner_db.getSimItems(infohash, num)

    def getSimilarTitles(self, storrent, num=30):
#        starttime = time()
        title = storrent['name']
        beginTitle = title[:self.titleIndexLength].lower()
        infohash = storrent['infohash']
        simTorrents = []
        for torrent in self.title_dict.get(beginTitle, []):
            if torrent['infohash'] != infohash and torrent['status'] == 'good':
                distance = editDist(torrent.get('name',''), title)
                if distance < 0.45:
                    insort(simTorrents, (distance, torrent['name'], torrent['infohash']))
                    if len(simTorrents) > num:
                        simTorrents = simTorrents[:-1]
                
        result = [self.info_dict[a[2]] for a in simTorrents]
#        for r in result:
#            print result.index(r)+1, simTorrents[result.index(r)][0], r['name']
#        print 'Searched %d similar titles in %f s' % (len(self.data), time()-starttime)
        return result
        
    def getNumDiscoveredFiles(self):

        if DEBUG:
            print >>sys.stderr,"torrentManager: getNumDisc: loaded",self.loading_count 
        self.standardOverview.setLoadingCount(self.loading_count)
        
        if not self.is_data_prepared:
            return -1
        else:
            ntorrents = self.metadata_handler.get_num_torrents()
            if ntorrents < 0:    # metadatahandler is not ready to load torents yet
                ntorrents = len(self.data)
            return ntorrents
        
    def setSecret(self, infohash, b):
        if b:
            self.torrent_db.updateTorrent(infohash, **{'secret':True})
        else:
            self.torrent_db.updateTorrent(infohash, **{'secret':False})
        
            
