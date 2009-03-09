# written by Yuan Yuan, Jelle Roozenburg
# see LICENSE.txt for license information

import os, re
from Tribler.Category.init_category import getCategoryInfo
from FamilyFilter import XXXFilter
from Tribler.Core.BitTornado import bencode
from Tribler.Core.Utilities.unicode import str2unicode, dunno2unicode
from sets import Set
from time import time
from copy import deepcopy
from traceback import print_exc
    
from threading import Condition
import sys

from Tribler.__init__ import LIBRARYNAME

DEBUG=False
category_file = "category.conf"
    

class Category:
    
    # Code to make this a singleton
    __single = None
    __size_change = 1024 * 1024 
    
    def __init__(self, install_dir='.'):
        
        if Category.__single:
            raise RuntimeError, "Category is singleton"
        filename = os.path.join(install_dir,LIBRARYNAME, 'Category', category_file)
        Category.__single = self
        self.utility = None
        #self.torrent_db = TorrentDBHandler.getInstance() # Arno, 2009-01-30: apparently unused
        try:
            self.category_info = getCategoryInfo(filename)
            self.category_info.sort(rankcmp)
        except:
            self.category_info = []
            if DEBUG:
                print_exc()

        self.xxx_filter = XXXFilter(install_dir)
        
        
        if DEBUG:
            print >>sys.stderr,"category: Categories defined by user",self.getCategoryNames()
        
        
    # return Category instance    
    def getInstance(*args, **kw):
        if Category.__single is None:
            Category(*args, **kw)       
        return Category.__single
    getInstance = staticmethod(getInstance)
       
    def register(self,metadata_handler):
        self.metadata_handler = metadata_handler
        
    def init_from_main(self, utility):
        self.utility = utility
        self.set_family_filter(None) # init family filter to saved state

    """
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
            print >>sys.stderr,'torrcoll: Checking of %d torrents costs: %f s' % (len(data), time() - begin)
        return False
        
    # recalculate category of all torrents, remove torrents from db if not existed
    def reSortAll(self, data, parent = None):
         
        max = len(data)
        if max == 0:
            return
        import wx
        dlgHolder = []
        event = Event()
        def makeDialog():
            dlg = wx.ProgressDialog("Upgrading Database",
                                    "Upgrading Old Database to New Database",
                                    maximum = max,
                                    parent = None,
                                    style = wx.PD_AUTO_HIDE 
                                    | wx.PD_ELAPSED_TIME
                                    | wx.PD_REMAINING_TIME
                                    )
            dlgHolder.append(dlg)
            event.set()
            
            
        wx.CallAfter(makeDialog)
        
        # Wait for dialog to be ready
        event.wait()
        dlg = dlgHolder[0]
        
        count = 0
        step = int(float(max) / 20) + 1
        
        # sort each torrent file
        for i in xrange(len(data)):
            count += 1
            if count % step == 0:
                wx.CallAfter(dlg.Update, [count])
            try:
                # try alternative dir if bsddb doesnt match with current Tribler install
                rec = data[i]
                (torrent_dir,torrent_name) = self.metadata_handler.get_std_torrent_dir_name(rec)
                    
                # read the torrent file
                filesrc = os.path.join(torrent_dir,torrent_name)
                
#                print filesrc
                f = open(filesrc, "rb")
                torrentdata = f.read()          # torrent decoded string
                f.close()
            except IOError:                     # torrent file not found
                # delete the info from db
                self.torrent_db.deleteTorrent(data[i]['infohash'])
                continue   
            
            # decode the data
            torrent_dict = bencode.bdecode(torrentdata)
            content_name = dunno2unicode(torrent_dict["info"].get('name', '?'))
            
            category_belong = []
            category_belong = self.calculateCategory(torrent_dict, content_name)
            
            if (category_belong == []):
                category_belong = ['other']
            
            data[i]['category'] = category_belong    # should have updated self.data
            self.torrent_db.updateTorrent(data[i]['infohash'], updateFlag=False, category=category_belong)
        self.torrent_db.sync()
        wx.CallAfter(dlg.Destroy)   
    """   
   
    
    def getCategoryKeys(self):
        if self.category_info is None:
	   	    return []
        keys = []
        keys.append("All")
        keys.append("other")
        for category in self.category_info:
            keys.append(category['name'])
        keys.sort()
        return keys
    
    def getCategoryNames(self):
        if self.category_info is None:
            return []
        keys = []
        for category in self.category_info:
            rank = category['rank']
            if rank == -1:
                break
            keys.append((category['name'],category['displayname']))
        return keys
    
    def hasActiveCategory(self, torrent):
        try:
            name = torrent['category'][0]
        except:
            print >> sys.stderr, 'Torrent: %s has no valid category' % `torrent['content_name']`
            return False
        for category in [{'name':'other', 'rank':1}]+self.category_info:
            rank = category['rank']
            if rank == -1:
                break
            if name.lower() == category['name'].lower():
                return True
        #print >> sys.stderr, 'Category: %s was not in %s' % (name.lower(), [a['name'].lower()  for a in self.category_info if a['rank'] != -1])
        return False
    
    def getCategoryRank(self,cat):
        for category in self.category_info:
            if category['name'] == cat:
                return category['rank']
        return None
    
    # calculate the category for a given torrent_dict of a torrent file
    # return list
    def calculateCategory(self, torrent_dict, display_name):  
        # torrent_dict is the  dict of 
        # a torrent file
        # return value: list of category the torrent belongs to
        torrent_category = None

        files_list = []
        try:                                
            # the multi-files mode
            for ifiles in torrent_dict['info']["files"]:
                files_list.append((ifiles['path'][-1], ifiles['length'] / float(self.__size_change)))
        except KeyError:                    
            # single mode
            files_list.append((torrent_dict['info']["name"],torrent_dict['info']['length'] / float(self.__size_change)))

        # Check xxx
        try:
            tracker = torrent_dict.get('announce')
            if not tracker:
                tracker = torrent_dict.get('announce-list',[['']])[0][0]
            if self.xxx_filter.isXXXTorrent(files_list, display_name, torrent_dict.get('announce'), torrent_dict.get('comment')):
                return ['xxx']
        except:
            print >> sys.stderr, 'Category: Exception in explicit terms filter in torrent: %s' % torrent_dict
            print_exc()
        
        # filename_list ready
        strongest_cat = 0.0
        for category in self.category_info:    # for each category
            (decision, strength) = self.judge(category, files_list, display_name)
            if decision and (strength > strongest_cat):
                torrent_category = [category['name']]
                strongest_cat = strength
        
        if torrent_category == None:
            torrent_category = ['other']
        
        return torrent_category

    # judge whether a torrent file belongs to a certain category
    # return bool
    def judge(self, category, files_list, display_name = ''):
    
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
            if 'strength' in category:
                return (True, category['strength'])
            else:
                return (True, (1- factor))
        
        # judge each file
        matchSize = 0
        totalSize = 1e-19
        for name, length in files_list:
            totalSize += length
            # judge file size
            if ( length < category['minfilesize'] ) or \
                (category['maxfilesize'] > 0 and length > category['maxfilesize'] ):
                continue
        
            # judge file suffix
            OK = False
            for isuffix in category['suffix']:
                if name.lower().endswith( isuffix ):
                    OK = True
                    break
            if OK:
                matchSize += length
                continue        
                
            # judge file keywords
            factor = 1.0
            fileKeywords = self._getWords(name.lower())
            
            for ikeywords in category['keywords'].keys():
#                pass
                try:
                    fileKeywords.index(ikeywords)
                    #print ikeywords
                    factor *= 1 - category['keywords'][ikeywords]
                except:
                    pass
            if factor < 0.5:
                # print filename_list[index] + '#######################'
                matchSize += length
   
        # match file   
        if (matchSize / totalSize) >= category['matchpercentage']:
            if 'strength' in category:
                return (True, category['strength'])
            else:
                return (True, (matchSize/ totalSize))
            
        return (False, 0)
    
    
    WORDS_REGEXP = re.compile('[a-zA-Z0-9]+')
    def _getWords(self, string):
        return self.WORDS_REGEXP.findall(string)
    
    
    def family_filter_enabled(self):
        """
        Return is xxx filtering is enabled in this client
        """
        if self.utility is None:
            return False
        state = self.utility.config.Read('family_filter')
        if state in ('1', '0'):
            return state == '1'
        else:
            self.utility.config.Write('family_filter', '1')
            self.utility.config.Flush()
            return True
    
    def set_family_filter(self, b=None):
        assert b in (True, False, None)
        old = self.family_filter_enabled()
        if b != old or b is None: # update category data if initial call, or if state changes
            if b is None:
                b=old
            if self.utility is None:
                return
            #print >> sys.stderr , b
            if b:
                self.utility.config.Write('family_filter', '1')
            else:
                self.utility.config.Write('family_filter', '0')
            self.utility.config.Flush()
            # change category data
            for category in self.category_info:
                if category['name'] == 'xxx':
                    if b:
                        category['old-rank'] = category['rank']
                        category['rank'] = -1
                    elif category['rank'] == -1:
                        category['rank'] = category['old-rank']
                    break


    def get_family_filter_sql(self, _getCategoryID, table_name=''):
        if self.family_filter_enabled():
            forbiddencats = [cat['name'] for cat in self.category_info if cat['rank'] == -1]
            if table_name:
                table_name+='.'
            if forbiddencats:
                return " and %scategory_id not in (%s)" % (table_name, ','.join([str(_getCategoryID([cat])) for cat in forbiddencats]))
        return ''
                
    
        
        
def rankcmp(a,b):
    if not ('rank' in a):
        return 1
    elif not ('rank' in b):
        return -1
    elif a['rank'] == -1:
        return 1
    elif b['rank'] == -1:
        return -1
    elif a['rank'] == b['rank']:
        return 0
    elif a['rank'] < b['rank']:
        return -1
    else:
        return 1
    
