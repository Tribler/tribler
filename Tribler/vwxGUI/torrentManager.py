import os
import sys
from base64 import encodestring
from Tribler.utilities import friendly_time, sort_dictlist, remove_torrent_from_list
from Tribler.unicode import str2unicode, dunno2unicode
from Utility.constants import * #IGNORE:W0611
from Tribler.Category.Category import Category
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from Tribler.CacheDB.CacheDBHandler import OwnerDBHandler
from copy import deepcopy
from traceback import print_exc, print_stack
from time import time
from bisect import insort

DEBUG = False

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
        self.loadData()
        self.dict_FunList = {}
        self.done_init = True
        self.searchkeywords = []
        if DEBUG:
            print >>sys.stderr,'torrentManager: ready init'
        
    def getInstance(*args, **kw):
        if TorrentDataManager.__single is None:
            TorrentDataManager(*args, **kw)       
        return TorrentDataManager.__single
    getInstance = staticmethod(getInstance)

    def loadData(self):
        self.torrent_db = SynTorrentDBHandler(updateFun=self.updateFun)
        self.owner_db = OwnerDBHandler()
        self.data = self.torrent_db.getRecommendedTorrents(light=False,all=True) #gets torrents with mypref
        self.category = Category.getInstance()
        updated = self.category.checkResort(self)        
        if updated:
            self.data = self.torrent_db.getRecommendedTorrents(light=False,all=True)
        self.prepareData()
        
    def prepareData(self):
        # initialize the cate_dict
        self.info_dict = {}    # reverse map
        
        for torrent in self.data:      
            # prepare to display
            torrent = self.prepareItem(torrent)
            self.info_dict[torrent["infohash"]] = torrent
            self.updateRankList(torrent, 'add', initializing = True)
        #self.printRankList()

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
        
    def getCategory(self, categorykey):
        if not self.done_init:
            return
        
        categorykey = categorykey.lower()
        def noDownloadHistory(torrent):
            return not torrent.has_key('myDownloadHistory')
        
        if categorykey == "all":
            return filter(noDownloadHistory, self.data)
        
        if categorykey == "search":
            return self.search()
        
        # See downloaded files also as category
        if (categorykey == self.utility.lang.get('mypref_list_title').lower()):
            def myfilter(a):
                return a.get('myDownloadHistory', False) and a.get('eventComingUp', '') != 'notDownloading'
            rlist = filter(myfilter, self.data) 
            if DEBUG:
                print >>sys.stderr,'torrentManager: getCategory: returns mydlhistory: %s' % str([t['content_name'] for t in rlist])
            return rlist
        
        rlist = []
        
        for idata in self.data:
            if not idata:
                continue
            categories = idata.get("category", [])
            if not categories:
                categories = ["other"]
            if categorykey in [cat.lower() for cat in categories]:
                rlist.append(idata)
                
        return filter(noDownloadHistory, rlist)

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
        self.torrent_db.deleteTorrent(infohash, delete_file=False, updateFlag=True)

    # register update function
    def register(self, fun, key):
        if DEBUG:
            print >>sys.stderr,'torrentManager: Registered for key: %s' % key
        try:
            key = key.lower()
            self.dict_FunList[key].index(fun)
            # if no exception, fun already exist!
            if DEBUG:
                print >>sys.stderr,"torrentManager: DBObserver register error. " + str(fun.__name__) + " already exist!"
            return
        except KeyError:
            self.dict_FunList[key] = []
            self.dict_FunList[key].append(fun)
        except ValueError:
            self.dict_FunList[key].append(fun)
        except Exception, msg:
            if DEBUG:
                print >>sys.stderr,"torrentDataManager: register error.", Exception, msg
            print_exc()
        
        
    def unregister(self, fun, key):
        if DEBUG:
            print >>sys.stderr,'torrentDataManager: Unregistered for key: %s' % key
        try:
            key = key.lower()
            self.dict_FunList[key].remove(fun)
        except Exception, msg:
            if DEBUG:
                print >>sys.stderr,"torrentDataManager: unregister error.", Exception, msg
            print_exc()
        
    def updateFun(self, infohash, operate):
        if not self.done_init:    # don't call update func before init finished
            return
        if DEBUG:
            print "torrentDataManager: updateFun called, param", operate
        if self.info_dict.has_key(infohash):
            if operate == 'add':
                self.addItem(infohash)
            elif operate == 'update':
                self.updateItem(infohash)
            elif operate == 'delete':
                self.deleteItem(infohash)
        else:
            if operate == 'update' or operate == 'delete':
                return
            else:
                self.addItem(infohash)
                
    def notifyView(self, torrent, operate):        
#        if torrent["category"] == ["?"]:
#            torrent["category"] = self.category.calculateCategory(torrent["info"], torrent["info"]['name'])
        
        if torrent.get('myDownloadHistory'):
            categories = [self.utility.lang.get('mypref_list_title')]
        else:
            categories = torrent.get('category', ['other']) + ["All"]
                                            
        for key in categories:
#            if key == '?':
#                continue
            try:
                key = key.lower()
                for fun in self.dict_FunList[key]: # call all functions for a certain key
                    fun(torrent, operate)     # lock is used to avoid dead lock
            except Exception, msg:
                #print >> sys.stderr, "abcfileframe: TorrentDataManager update error. Key: %s" % (key), Exception, msg
                #print_exc()
                pass
        
    def addItem(self, infohash):
        if self.info_dict.has_key(infohash):
            return
        torrent = self.torrent_db.getTorrent(infohash, num_owners=True)
        if not torrent:
            return
        torrent['infohash'] = infohash
        item = self.prepareItem(torrent)
        self.data.append(item)
        self.info_dict[infohash] = item
        self.updateRankList(item, 'add')
        self.notifyView(item, 'add')
    
    
    def setBelongsToMyDowloadHistory(self, infohash, b):
        """Set a certain new torrent to be in the download history or not"
        Should not be changed by updateTorrent calls"""
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        
        # EventComing up, to let the detailPanel update already
        if b:    # add to my pref
            old_torrent['eventComingUp'] = 'downloading'
        else:    # remove from my pref
            old_torrent['eventComingUp'] = 'notDownloading'
        
        self.notifyView(old_torrent, 'delete')
        
        del old_torrent['eventComingUp']
        if b:
            old_torrent['myDownloadHistory'] = True
        else:
            if old_torrent.has_key('myDownloadHistory'):
                del old_torrent['myDownloadHistory']
            
        self.notifyView(old_torrent, 'add')
        
        self.updateRankList(old_torrent, 'update')
        
        if b:    # update buddycast after view was updated
            #self.utility.buddycast.addMyPref(infohash)    # will be called somewhere
            pass
        else:
            self.utility.buddycast.delMyPref(infohash)

                
    def addNewPreference(self, infohash): 
        if self.info_dict.has_key(infohash):
            return
        torrent = self.torrent_db.getTorrent(infohash, num_owners=True)
        if not torrent:
            return
        torrent['infohash'] = infohash
        item = self.prepareItem(torrent)
        torrent['myDownloadHistory'] = True
        self.data.append(item)
        self.info_dict[infohash] = item
        self.notifyView(item, 'add')
        
    def updateItem(self, infohash):
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        torrent = self.torrent_db.getTorrent(infohash, num_owners=True)
        if not torrent:
            return
        torrent['infohash'] = infohash
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
        info = torrent['info']
        torrent['length'] = info.get('length', 0)
        torrent['content_name'] = dunno2unicode(info.get('name', '?'))
        if torrent['torrent_name'] == '':
            torrent['torrent_name'] = '?'
        torrent['num_files'] = int(info.get('num_files', 0))
        torrent['date'] = info.get('creation date', 0) 
        torrent['tracker'] = info.get('announce', '')
        torrent['leecher'] = torrent.get('leecher', -1)
        torrent['seeder'] = torrent.get('seeder', -1)
        torrent['swarmsize'] = torrent['seeder'] + torrent['leecher']
        if torrent.has_key('simRank'):
            raise Exception('simRank in database!')
            del torrent['simRank']
        # Thumbnail is read from file only when it is shown on screen by
        # thumbnailViewer or detailsPanel
        return torrent
         
    def updateRankList(self, torrent, operate, initializing = False):
        "Update the ranking list, so that it always shows the top20 most similar torrents"
        
        #print 'UpdateRankList: %s, for: %s' % (operate, repr(torrent.get('content_name')))
        
        sim = torrent.get('relevance')
        good = torrent.get('status') == 'good' and not torrent.get('myDownloadHistory', False)
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
        assert initializing or len(self.rankList) in [20,21],'torrentManager: Error, ranklist had length: %d' % len(self.rankList)
        
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
        
        #self.printRankList()
        
    def updateRemovedItem(self, infohash, initializing):
        if self.info_dict.has_key(infohash):
            torrent = self.info_dict[infohash]
            #print 'Del rank %d of %s' % (torrent.get('simRank', -1), repr(torrent.get('content_name')))
            if torrent.has_key('simRank'):
                del torrent['simRank']
            if not initializing:
                self.notifyView(torrent, 'update')
        else:
            raise Exception('(removeRank) Not found infohash: %s in info_dict.' % repr(infohash))
            
    
    def updateRankedItems(self, initializing):
        rank = len(self.rankList)
        for (sim, infohash) in self.rankList:
            if self.info_dict.has_key(infohash):
                torrent = self.info_dict[infohash]
                #print 'Give rank %d to %s' % (rank, repr(torrent.get('content_name')))
                torrent['simRank'] = rank
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
        print 'Ranklist:'
        rank = 1
        
        for (sim, infohash) in self.rankList:
            if self.info_dict.has_key(infohash):
                torrent = self.info_dict[infohash]
                print '%d: %.2f, %s' % (rank, torrent.get('relevance', -1), repr(torrent.get('content_name', 'no name')))
            else:
                print_stack()
                print 'Not found infohash: %s in info_dict.' % repr(infohash)
            rank += 1
        
        self.rankList.reverse()
        
        print 'Checking all torrents'
        wrong = right = 0
        for infohash, torrent in self.info_dict.items():
            inRankList = False
            for (s, infohashRanked) in self.rankList:
                if infohash == infohashRanked:
                    inRankList = True
            if not inRankList:
                if torrent.has_key('simRank'):
                    wrong += 1
                    print 'Torrent %s was not in ranklist: sim: %f, rank: %d' % (repr(torrent.get('content_name')), torrent.get('relevance'), torrent['simRank'])
                else:
                    right+=1
        print '%d right, %d wrong torrents' % (right, wrong)
        if wrong > 0:
            raise Exception('wrong torrents')
            
    def setSearchKeywords(self,wantkeywords):
        self.searchkeywords = wantkeywords
         
    def search(self):
        if DEBUG:
            print >>sys.stderr,"torrentDataManager: search: Want",self.searchkeywords
        hits = []
        if len(self.searchkeywords) == 0:
            return hits
        for torrent in self.data:
            if torrent.has_key('myDownloadHistory'):
                continue
            low = torrent['content_name'].lower()
            for wantkw in self.searchkeywords:
                # only search in alive torrents
                if low.find(wantkw) != -1 and torrent['status'] == 'good':
                    if DEBUG:
                        print >>sys.stderr,"torrentDataManager: search: Got hit",`wantkw`,"found in",`torrent['content_name']`
                    hits.append(torrent)
        return hits

    def getFromSource(self,source):
        hits = []
        for torrent in self.data:
            if torrent['source'] == source:
                hits.append(torrent)
        return hits
    
    def getSimItems(self, infohash, num=15):
        return self.owner_db.getSimItems(infohash, num)
