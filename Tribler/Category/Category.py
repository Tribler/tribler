
# written by Yuan Yuan

import os
from Tribler.Category.init_category import getCategoryInfo
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from BitTornado import bencode
from Tribler.unicode import str2unicode, dunno2unicode
from sets import Set
from time import time
from copy import deepcopy
import sys
import wx

category_file = "category.conf"

def init(config_dir = None):
    filename = make_filename(config_dir, category_file)
    Category.getInstance(filename)
    
def make_filename(config_dir, filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir,filename)    

class Category:
    
    # Code to make this a singleton
    __single = None
    __size_change = 1024 * 1024
    
    def __init__(self, filename):
        if Category.__single:
            raise RuntimeError, "Category is singleton"
        Category.__single = self
        self.torrent_db = SynTorrentDBHandler()
        self.category_info = getCategoryInfo(filename)
        
    # return Category instance    
    def getInstance(*args, **kw):
        if Category.__single is None:
            Category(*args, **kw)       
        return Category.__single
    getInstance = staticmethod(getInstance)
        
    # check to see whether need to resort torrent file
    # return bool
    def checkResort(self, data_manager):
        data = data_manager.data
        if not data:
            data = data_manager.torrent_db.getRecommendedTorrents(all = True)
        if not data:
            return False
        torrent = data[0]
        if torrent["category"] == ["?"]:
            data = data_manager.torrent_db.getRecommendedTorrents(all = True)
            self.reSortAll(data)
            return True
        return False
        
    # recalculate category of all torrents, remove torrents from db if not existed
    def reSortAll(self, data, parent = None):
         
        max = len(data)
        if max == 0:
            return
        dlg = wx.ProgressDialog("Upgrading Database",
                               "Upgrading Old Database to New Database",
                               maximum = max,
                               parent = None,
                               style = wx.PD_AUTO_HIDE 
                                | wx.PD_ELAPSED_TIME
                                | wx.PD_REMAINING_TIME
                                )
        count = 0
        step = int(float(max) / 20) + 1
        
        # sort each torrent file
        for i in xrange(len(data)):
            count += 1
            if count % step == 0:
                dlg.Update(count)
            try:                                # read the torrent file
                filesrc = os.path.join(data[i]['torrent_dir'], data[i]['torrent_name'])
#                print filesrc
                f = open(filesrc, "rb")
                torrentdata = f.read()          # torrent decoded string
                f.close()
            except IOError:                     # torrent file not found
                # delete the info from db
                self.torrent_db.deleteTorrent(data[i]['infohash'], updateFlag=False)
                continue   
            
            # decode the data
            torrent_dict = bencode.bdecode(torrentdata)["info"]
            content_name = dunno2unicode(torrent_dict.get('name', '?'))
            
            category_belong = []
            category_belong = self.calculateCategory(torrent_dict, content_name)
            
            if (category_belong == []):
                category_belong = ['other']
            
            data[i]['category'] = category_belong    # should have updated self.data
            self.torrent_db.updateTorrent(data[i]['infohash'], updateFlag=False, category=category_belong)
        self.torrent_db.sync()
        dlg.Update(count)   
    
    def getCategoryKeys(self):
        keys = []
        keys.append("All")
        keys.append("other")
        for category in self.category_info:
            keys.append(category['name'])
        keys.sort()
        return keys
    
    # calculate the category for a given torrent_dict of a torrent file
    # return list
    def calculateCategory(self, torrent_dict, display_name):  # torrent_dict is the info dict of 
                                                # a torrent file
        
        # return value: list of category the torrent belongs to
        torrent_category = []

        filename_list = []
        filesize_list = []        
        try:                                # the multi-files mode
            for ifiles in torrent_dict["files"]:
                filepath = ifiles["path"]
                #print filepath
                pathlen = len(filepath)
                
                filename_list.append(filepath[pathlen - 1])
                filesize_list.append(ifiles['length'] / self.__size_change)               
        except KeyError:                    # single mode
            filename_list.append(torrent_dict["name"])
            filesize_list.append(torrent_dict['length'] / self.__size_change)        
                                 
        # filename_list ready
        for category in self.category_info:    # for each category
            if (self.judge(category, filename_list, filesize_list, display_name) == True):        
                torrent_category.append(category['name'])

        if torrent_category == []:
            torrent_category = ['other']

        return torrent_category

    # judge whether a torrent file belongs to a certain category
    # return bool
    def judge(self, category, filename_list, filesize_list, display_name = ''):
    
        # judge file keywords
        display_name = display_name.lower()
        factor = 0.0
        for ikeywords in category['keywords'].keys():
            if display_name.find( ikeywords ) != -1:
                factor += category['keywords'][ikeywords]
        if factor >= 1:
                # print filename_list[index] + '#######################'
            return True  
        
        # judge each file
        matchSize = 0
        totalSize = 1e-19
        for index in range( len( filesize_list ) ):
            totalSize += filesize_list[index]
            # judge file size
            if ( filesize_list[index] < category['minfilesize'] ) or ( filesize_list[index] > category['maxfilesize'] ):
                continue
        
            # change to lower case
            filename_list[index] = filename_list[index].lower()

            # judge file suffix
            OK = 0
            for isuffix in category['suffix']:
                if filename_list[index].endswith( isuffix ):
                    OK = 1
                    break
            if ( OK == 1 ):
                matchSize += filesize_list[index]
                continue        
                
            # judge file keywords
            factor = 1.0
            for ikeywords in category['keywords'].keys():
                if filename_list[index].find( ikeywords ) != -1:
                    factor *= 1 - category['keywords'][ikeywords]
            if (1 - factor) > 0.5:
                # print filename_list[index] + '#######################'
                matchSize += filesize_list[index]
   
        # match file   
        if (matchSize / totalSize) >= category['matchpercentage']:
            return True
            
        return False
    
