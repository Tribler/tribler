# written by Yuan Yuan
# see LICENSE.txt for license information

import os
from Tribler.Category.init_category import getCategoryInfo
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from BitTornado import bencode
from Tribler.unicode import str2unicode, dunno2unicode
from sets import Set
from time import time
from copy import deepcopy
from traceback import print_exc
import sys

DEBUG=False
category_file = "category.conf"

def init(install_dir = None, config_dir = None):
    filename = make_filename(install_dir, category_file)
    Category.getInstance(filename, config_dir)
    
def make_filename(config_dir, filename):
    if config_dir is None:
        return filename
    else:
        return os.path.join(config_dir,filename)    

class Category:
    
    # Code to make this a singleton
    __single = None
    __size_change = 1024 * 1024 
    
    def __init__(self, filename, config_dir):
        if Category.__single:
            raise RuntimeError, "Category is singleton"
        Category.__single = self
        self.torrent_db = SynTorrentDBHandler()
        self.category_info = getCategoryInfo(filename)
        self.config_dir = config_dir
        
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
#===============================================================================
#        if not data:
#            data = data_manager.torrent_db.getRecommendedTorrents(all = True)
#===============================================================================
        if not data:
            return False

#        data = data_manager.torrent_db.getRecommendedTorrents(all = True)
#        self.reSortAll(data)
#        return True
        torrent = data[0]
        if torrent["category"] == ["?"]:
            #data = data_manager.torrent_db.getRecommendedTorrents(all = True)
            self.reSortAll(data)
#            del data
            return True
        
        begin = time()
        for item in data:
            if len(item['category']) > 1:
                #data = data_manager.torrent_db.getRecommendedTorrents(all = True)
                self.reSortAll(data)
#                del data
                return True
        if DEBUG:
            print 'torrcoll: Checking of %d torrents costs: %f s' % (len(data), time() - begin)
        return False
        
    # recalculate category of all torrents, remove torrents from db if not existed
    def reSortAll(self, data, parent = None):
         
        max = len(data)
        if max == 0:
            return
        import wx
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
            try:
                # try alternative dir if bsddb doesnt match with current Tribler install
                if not os.path.exists(data[i]['torrent_dir']):
                    data[i]['torrent_dir'] = os.path.join(self.config_dir, "torrent2")
            
                                                # read the torrent file
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
        dlg.Destroy()   
    
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
        torrent_category = None

        filename_list = []
        filesize_list = []        
        try:                                # the multi-files mode
            for ifiles in torrent_dict["files"]:
                filepath = ifiles["path"]
                #print filepath
                pathlen = len(filepath)
                
                filename_list.append(filepath[pathlen - 1])
                filesize_list.append(ifiles['length'] / float(self.__size_change))               
        except KeyError:                    # single mode
            filename_list.append(torrent_dict["name"])
            filesize_list.append(torrent_dict['length'] / float(self.__size_change))        
                                 
        # filename_list ready
        strongest_cat = 0.0
        for category in self.category_info:    # for each category
            (decision, strength) = self.judge(category, filename_list, filesize_list, display_name)
            
            # Either take category xxx or the strongest of the rest
            if (decision and category['name'].lower() == 'xxx'):
                return [category['name']]
            
            if decision and (strength > strongest_cat):
                torrent_category = [category['name']]
                strongest_cat = strength
        
        if torrent_category == None:
            torrent_category = ['other']
        
        return torrent_category

    # judge whether a torrent file belongs to a certain category
    # return bool
    def judge(self, category, filename_list, filesize_list, display_name = ''):
    
        # judge file keywords
        display_name = display_name.lower()                
        factor = 1.0
        fileKeywords = self._getWords(display_name)
        
        for ikeywords in category['keywords'].keys():
            try:
                fileKeywords.index(ikeywords)
                factor *= 1 - category['keywords'][ikeywords]
            except:
                pass
        if (1 - factor) > 0.5:
            return (True, (1- factor))
        
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
            fileKeywords = self._getWords(filename_list[index])
            # special for xxx
            if category["name"] == "xxx":
                if filename_list[index].find("xxx") != -1:
                    factor = 0            
            for ikeywords in category['keywords'].keys():
#                pass
                try:
                    fileKeywords.index(ikeywords)
#                    print ikeywords
                    factor *= 1 - category['keywords'][ikeywords]
                except:
                    pass
            if (1 - factor) > 0.5:
                # print filename_list[index] + '#######################'
                matchSize += filesize_list[index]
   
        # match file   
        if (matchSize / totalSize) >= category['matchpercentage']:
            return (True, (matchSize/ totalSize))
            
        return (False, 0)
    
    def _getWords(self, string):
        strLen = len(string)
        strList = []
        left = -1
    
        for index in range(strLen):
            if left == -1:
                if string[index].isalnum() == True:
                    left = index
                else:
                    continue
            if string[index].isalnum() == True:
                continue
            else:
                s = string[left:index]
                if s != "" and not s.isdigit():
                    strList.append(s)
                left = -1
        if left != -1:
            s = string[left:index + 1]
            if s != "" and not s.isdigit():
                strList.append(s)
        return strList  
