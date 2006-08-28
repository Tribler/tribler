# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

import wx
from wx.lib import masked
import os
import sys
from traceback import print_exc
from base64 import encodestring
from Tribler.utilities import friendly_time, sort_dictlist
from Tribler.unicode import str2unicode, dunno2unicode
from common import CommonTriblerList
from Utility.constants import * #IGNORE:W0611
from Tribler.Category.Category import Category
from Tribler.TrackerChecking.ManualChecking import ManualChecking
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from copy import deepcopy
from traceback import print_exc
from time import time


DEBUG = False
SHOW_TORRENT_NAME = True

relevance_display_factor = 1000.0

def showInfoHash(infohash):
    if infohash.startswith('torrent'):    # for testing
        return infohash
    try:
        n = int(infohash)
        return str(n)
    except:
        pass
    return encodestring(infohash).replace("\n","")
#    try:
#        return encodestring(infohash)
#    except:
#        return infohash

class MyPreferenceList(CommonTriblerList):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        self.mypref_db = parent.mypref_db
        self.min_rank = -1
        self.max_rank = 5
        self.reversesort = 0
        self.lastcolumnsorted = -1
        
        style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES
        self.data_manager = TorrentDataManager.getInstance()
        prefix = 'mypref'
        minid = 0
        maxid = 5
        rightalign = []
        centeralign = [
            MYPREF_TORRENTNAME,
            MYPREF_CONTENTNAME,
            MYPREF_RANK,
            MYPREF_SIZE,
            MYPREF_LASTSEEN,
        ]
        
        exclude = []
        
        self.keys = ['torrent_name', 'content_name', 'rank', 'length', 'last_seen']

        CommonTriblerList.__init__(self, parent, style, prefix, minid, maxid, 
                                     exclude, rightalign, centeralign)
        
    # change display format for item data
    def getText(self, data, row, col):
        key = self.keys[col]
        original_data = data[row][key]
        if DEBUG:
            print "mypref frame: getText",key, `original_data`
        if key == 'length':
            length = original_data/1024/1024.0
            return '%.2f MB'%(length)
        if key == 'last_seen':
            if original_data == 0:
                return '?'
            return friendly_time(original_data)
        if key == "seeder" or key == "leecher":
            if original_data == -1:
                original_data = "?"
            elif original_data == -2:
                original_data = "n/a"
        ret = str2unicode(original_data)
        return ret
        
    def reloadData(self):
        myprefs = self.mypref_db.getPrefList()
        keys = ['infohash', 'torrent_name', 'info', 'content_name', 'rank', 'last_seen']
        self.data = self.mypref_db.getPrefs(myprefs, keys)
        for i in xrange(len(self.data)):
            info = self.data[i]['info']
            self.data[i]['length'] = info.get('length', 0)
            if self.data[i]['torrent_name'] == '':
                self.data[i]['torrent_name'] = '?'
            if self.data[i]['content_name'] == '':
                self.data[i]['content_name'] = '?'
                
    def OnActivated(self, event):
        self.curr_idx = event.m_itemIndex
        
        
    def getMenuItems(self, min_rank, max_rank):
        menu_items = {}
        for i in range(min_rank, max_rank+1):
            id = wx.NewId()
            func = 'OnRank' + str(i - min_rank)
            func = getattr(self, func)
            if i == -1:
                label = self.utility.lang.get('fakefile')
            elif i == 0:
                label = self.utility.lang.get('norating')
            else:
                label = "*" * i
            menu_items[i] = {'id':id, 'func':func, 'label':label}
        return menu_items

    def OnRightClick(self, event=None):
        curr_idx = self.getSelectedItems()
        if not hasattr(self, "adjustRankID"):
            self.adjustRankID = wx.NewId()
            self.menu_items = self.getMenuItems(self.min_rank, self.max_rank)
            for i in self.menu_items:
                self.Bind(wx.EVT_MENU, self.menu_items[i]['func'], 
                           id=self.menu_items[i]['id'])
        if not hasattr(self, "deletePrefID"):
            self.deletePrefID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeletePref, id=self.deletePrefID)
            
        # menu for change torrent's rank
        sm = wx.Menu()
        
        curr_rank = self.data[curr_idx[0]]['rank']
        for i in curr_idx[1:]:
            if self.data[i]['rank'] != curr_rank:
                curr_rank = None

        submenu = wx.Menu()
        idx = self.menu_items.keys()
        idx.sort()
        idx.reverse()    
        for i in idx:    # 5..-1
            if i == curr_rank:
                label = '> '+self.menu_items[i]['label']
            else:
                label = '   '+self.menu_items[i]['label']
            submenu.Append(self.menu_items[i]['id'], label)
            
        sm.AppendMenu(self.adjustRankID, self.utility.lang.get('rankitems'), submenu)
        sm.Append(self.deletePrefID, self.utility.lang.get('delete'))
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()

    def changeRank(self, curr_idx, rank):
        torrent = self.data[curr_idx]
        torrent['rank'] = rank
        self.mypref_db.updateRank(torrent['infohash'], rank)
        self.loadList(False, False)
        #self.SetStringItem(curr_idx, 2, str(rank))
        #print "Set torrent", showInfoHash(torrent['infohash']), "rank", rank
        
    def OnRank0(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 0+self.min_rank)
        
    def OnRank1(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 1+self.min_rank)
        
    def OnRank2(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 2+self.min_rank)
        
    def OnRank3(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 3+self.min_rank)
        
    def OnRank4(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 4+self.min_rank)
        
    def OnRank5(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 5+self.min_rank)
        
    def OnRank6(self, event=None):
        selected = self.getSelectedItems()
        for i in selected:
            self.changeRank(i, 6+self.min_rank)
        
    def OnDeletePref(self, event=None):
        selected = self.getSelectedItems()
        j = 0
        for i in selected:
            infohash = self.data[i-j]['infohash']
            self.mypref_db.deletePreference(infohash)
            self.DeleteItem(i-j)
            self.data.pop(i-j)
            self.data_manager.updateFun(infohash, 'add')
            j += 1
        self.mypref_db.sync()


class MyPreferencePanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.utility = frame.utility
        
        self.mypref_db = frame.mypref_db
#        self.torrent_db = frame.torrent_db
        wx.Panel.__init__(self, parent, -1)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        # check category before load list
        
        
        self.list=MyPreferenceList(self)
        mainbox.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        label = wx.StaticText(self, -1, self.utility.lang.get('assignrating'))
        mainbox.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(mainbox)
        self.SetAutoLayout(True)
        self.Show(True)
        self.list.loadList()

    def updateColumns(self, force=False):
        self.list.loadList(False, False)


class TorrentDataManager:
    # Code to make this a singleton
    __single = None
   
    def __init__(self):
        if TorrentDataManager.__single:
            raise RuntimeError, "TorrentDataManager is singleton"
        TorrentDataManager.__single = self
        self.done_init = False
        self.torrent_db = SynTorrentDBHandler(updateFun=self.updateFun)
        self.data = self.torrent_db.getRecommendedTorrents()
        self.category = Category.getInstance()
        updated = self.category.checkResort(self)        
        if updated:
            self.data = self.torrent_db.getRecommendedTorrents()
        self.prepareData()
        self.dict_FunList = {}
        self.done_init = True
        
    def getInstance(*args, **kw):
        if TorrentDataManager.__single is None:
            TorrentDataManager(*args, **kw)       
        return TorrentDataManager.__single
    getInstance = staticmethod(getInstance)

    def prepareData(self):
        # initialize the cate_dict
        self.info_dict = {}    # reverse map
        
        for torrent in self.data:      
            # prepare to display
            torrent = self.prepareItem(torrent)
            self.info_dict[torrent["infohash"]] = torrent    

    def getCategory(self, categorykey):
        
        if (categorykey == "All"):
            return self.data
        
        rlist = []
        
        for idata in self.data:
            if not idata:
                continue
            categories = idata.get("category", [])
            if not categories:
                categories = ["other"]
            if categorykey in categories:
                rlist.append(idata)
        return rlist

    def deleteTorrent(self, infohash, delete_file=False):
        self.torrent_db.deleteTorrent(infohash, delete_file=False, updateFlag=True)

    # register update function
    def register(self, fun, key):
        try:
            self.dict_FunList[key].index(fun)
            # if no exception, fun already exist!
            print "DBObserver register error. " + str(fun.__name__) + " already exist!"
            return
        except KeyError:
            self.dict_FunList[key] = []
            self.dict_FunList[key].append(fun)
        except ValueError:
            self.dict_FunList[key].append(fun)
        except Exception, msg:
            print "TorrentDataManager unregister error.", Exception, msg
            print_exc()
        
    def unregister(self, fun, key):
        try:
            self.dict_FunList[key].remove(fun)
        except Exception, msg:
            print "TorrentDataManager unregister error.", Exception, msg
            print_exc()
        
    def updateFun(self, infohash, operate):
        if not self.done_init:    # don't call update func before init finished
            return
        #print "*** torrentdatamanager updateFun", operate
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
        for key in (torrent["category"] + ["All"]):
#            if key == '?':
#                continue
            try:
                for fun in self.dict_FunList[key]: # call all functions for a certain key
                    fun(torrent, operate)     # lock is used to avoid dead lock
            except Exception, msg:
                print >> sys.stderr, "abcfileframe: TorrentDataManager update error. Key: %s" % (key), Exception, msg
                print_exc()
        
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
        for key in old_torrent.keys():    # modify reference
            old_torrent[key] = torrent[key]
    
        self.notifyView(old_torrent, 'update')
    
    def deleteItem(self, infohash):
        old_torrent = self.info_dict.get(infohash, None)
        if not old_torrent:
            return
        self.info_dict.pop(infohash)
        self.data.remove(old_torrent)
        self.notifyView(old_torrent, 'delete')

    def prepareItem(self, torrent):    # change self.data
        info = torrent['info']
        torrent['length'] = info.get('length', 0)
        torrent['content_name'] = dunno2unicode(info.get('name', '?'))
        if torrent['torrent_name'] == '':
            torrent['torrnt_name'] = '?'
        torrent['num_files'] = int(info.get('num_files', 0))
        torrent['date'] = info.get('creation date', 0) 
        torrent['tracker'] = info.get('announce', '')
        torrent['leecher'] = torrent.get('leecher', -1)
        torrent['seeder'] = torrent.get('seeder', -1)
        return torrent
         
        
#class TorrentDataSource(list):
#    def __init__(self, parent, data_manager, categorykey):
#        self.data_manager = data_manager
#        self.categorykey = categorykey
#        self.reloadData()
#        
#    def reloadData(self):
#        self.clear()
#        self += self.data_manager.getCategory(self.categorykey)
#    def getCount(self):
#        return len(self.data)
#    
#    def getItem(self, index):
#        return self.data[index]

class FileList(CommonTriblerList):
    def __init__(self, parent, categorykey):
        self.done_init = False
        self.parent = parent
        self.categorykey = categorykey
        self.data_manager = TorrentDataManager.getInstance()
        self.data_manager.register(self.updateFun, self.categorykey)
        self.utility = parent.utility
        self.min_rank = -1
        self.max_rank = 5
        self.reversesort = 0
        self.lastcolumnsorted = -1
        self.loadRelevanceThreshold()
        
        style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES
        
        prefix = 'torrent'
        minid = 0
        maxid = 10
        rightalign = []
        centeralign = [
            TORRENT_TORRENTNAME,
            TORRENT_CONTENTNAME,
            TORRENT_RECOMMENDATION,
            TORRENT_SOURCES,
            TORRENT_NLEECHERS, 
            TORRENT_NSEEDERS,
            TORRENT_INJECTED,
            TORRENT_SIZE,
            TORRENT_NFILES,
            TORRENT_TRACKER,
        ]
        
        exclude = []
        
        self.keys = ['torrent_name', 'content_name', 'relevance', 'num_owners',
                      'leecher', 'seeder', 'date', 'length', 'num_files', 'tracker',
                     'category'
                    ]

        CommonTriblerList.__init__(self, parent, style, prefix, minid, maxid, 
                                     exclude, rightalign, centeralign)
        self.done_init = True
                                     
    def __del__(self):
        self.data_manager.unregister(self.updateFun, self.categorykey)
        
    def getText(self, data, row, col):
        
        key = self.keys[col]
        try:
            original_data = data[row][key]
        except Exception, msg:
            print >> sys.stderr, "abcfileframe: FileList getText error", Exception, msg, key, data[row]
            raise Exception, msg
        if key == 'relevance':
            # should this change, also update
            return '%.2f'%(original_data/relevance_display_factor)
        if key == 'infohash':
            return showInfoHash(original_data)
        if key == 'length':
            length = original_data/1024/1024.0
            return '%.2f MB'%(length)
        if key == 'date':
            if original_data == 0:
                return '?'
            return friendly_time(original_data)
        if key == "seeder" or key == "leecher":
            if original_data == -1:
                original_data = "?"
            elif original_data == -2:
                original_data = "n/a"
        return str2unicode(original_data)
        
    def reloadData(self):
        self.data = self.data_manager.getCategory(self.categorykey)
        def showFile(data):
            if data['relevance'] < self.relevance_threshold:
                return False
            else:
                return True
            
        self.data = filter(showFile, self.data)    
                        
    def OnDeleteTorrent(self, event=None):
        selected = self.getSelectedItems()
        selected_list = [self.data[i]['infohash'] for i in selected]
        for infohash in selected_list:
            self.data_manager.deleteTorrent(infohash, True)
            
    def OnRightClick(self, event=None):
        if not hasattr(self, "deleteTorrentID"):
            self.deleteTorrentID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeleteTorrent, id=self.deleteTorrentID)
        if not hasattr(self, "downloadTorrentID"):
            self.downloadTorrentID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDownload, id=self.downloadTorrentID)
        if not hasattr(self, "check"):
            self.check = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnCheck, id = self.check)
            
        # menu for change torrent's rank
        sm = wx.Menu()
        sm.Append(self.check,self.utility.lang.get('checkstatus'))
        sm.Append(self.downloadTorrentID, self.utility.lang.get('download'))
        sm.Append(self.deleteTorrentID, self.utility.lang.get('delete'))
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()
        
    def OnCheck(self, event):
#        print "########## checked"
        selected = self.getSelectedItems()
#        print "selected len: " + str(len(selected))
        check_list = []
        for i in selected:
            # for manual checking
            torrent_copy = deepcopy(self.data[i])
            check_list.append(torrent_copy)
            
            # for display
            torrent_copy = deepcopy(self.data[i])
            torrent_copy["seeder"] = "checking"
            torrent_copy["leecher"] = "checking"
            self.data[i] = torrent_copy
            self.updateRow(i)
        
        t = ManualChecking(check_list)
        t.start()   
        
    def updateRow(self, index):                 # update a single row
        active_columns = self.columns.active
        if not active_columns:
            return
        
        num = len(self.data)        
        if self.num > 0 and self.num < num:
            num = self.num
        
        if (num == 0):
            return
        if (index > num):
            return
        
        for col, rank in active_columns:
            txt = self.getText(self.data, index, col)
            self.SetStringItem(index, rank, txt)
            
            item = self.GetItem(index)
            status = self.data[index].get('status', 'unknown')
            if status == 'good':
                item.SetTextColour(wx.BLUE)
            elif status == 'dead':
                item.SetTextColour(wx.RED)
            self.SetItem(item)  
            
    def updateFun(self, torrent, operate):    # must pass torrent instead of infohash to avoid reading db
        if not self.done_init:
            return
        #print "*** filelist updateFun", operate, self.categorykey, torrent['info']['name']
        if operate == "update":
            try:
                index = self.info_dict[torrent["infohash"]]
                self.data[index] = torrent
                self.invokeLater(self.updateRow, [index])                
            except KeyError:
                pass
            except Exception, msg:
                print >> sys.stderr, "abcfileframe: File List updateFun Error", Exception, msg
                print_exc()
        elif operate == "add":
            # avoid one torrent displayed in the File List twice 
            try:    
                index = self.info_dict[torrent["infohash"]]
            except KeyError:
                pass
            except Exception, msg:
                print >> sys.stderr, "abcfileframe: File List updateFun Error", Exception, msg
                print_exc()
            
            self.data.append(torrent)
            index = len(self.data) - 1
            self.invokeLater(self.addRow, [index])            
        elif operate == "delete":
            self.invokeLater(self.loadList, [])            
#            self.loadList()
    
    def OnActivated(self, event):
        self.curr_idx = event.m_itemIndex
        self.download(self.curr_idx)
        
    def OnDownload(self, event):
        first_idx = self.GetFirstSelected()
        if first_idx < 0:
            return
        self.download(first_idx)
        
    def download(self, idx):
        src = os.path.join(self.data[idx]['torrent_dir'], 
                            self.data[idx]['torrent_name'])
        if self.data[idx]['content_name']:
            name = self.data[idx]['content_name']
        else:
            name = showInfoHash(self.data[idx]['infohash'])
        #start_download = self.utility.lang.get('start_downloading')
        #str = name + "?"
        if os.path.isfile(src):
            str = self.utility.lang.get('download_start') + u' ' + name + u'?'
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('click_and_download'), 
                                    wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                ret = self.parent.clickAndDownload(src)
                if ret == 'OK':
                    self.parent.frame.updateMyPref()
                    infohash = self.data[idx]['infohash']
                    self.data_manager.updateFun(infohash, 'delete')
        else:
            str = self.utility.lang.get('delete_torrent') % name
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete_dead_torrent'), 
                                    wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                infohash = self.data[idx]['infohash']
                self.data_manager.updateFun(infohash, 'delete')
     
    def addRow(self, index):   
        active_columns = self.columns.active
        if not active_columns:
            return
        
        num = len(self.data)
        if self.num > 0 and self.num < num:
            num = self.num
        
        # if reach the limitation of file number displayed in List, return    
        if index > num - 1:
            return
        
        first_col = active_columns[0][0]
        self.InsertStringItem(index, self.getText(self.data, index, first_col))
        for col,rank in active_columns[1:]:
            txt = self.getText(self.data, index, col)
            self.SetStringItem(index, rank, txt)
        self.info_dict[self.data[index]["infohash"]] = index
        item = self.GetItem(index)
        status = self.data[index].get('status', 'unknown')
        if status == 'good':
            item.SetTextColour(wx.BLUE)
        elif status == 'dead':
            tem.SetTextColour(wx.RED)
        self.SetItem(item)    
            
    def loadList(self, reload=True, sorted=True):
        self.DeleteAllItems() 
        self.loading()

        active_columns = self.columns.active
        if not active_columns:
            return
        
        if reload:
            self.reloadData()
        
        if sorted:
            key = self.keys[self.lastcolumnsorted]
            self.data = sort_dictlist(self.data, key, self.reversesort)
            
        num = len(self.data)
        if self.num > 0 and self.num < num:
            num = self.num
            
        self.DeleteAllItems() 
        
        first_col = active_columns[0][0]
        #self.check_filename(self.data)
        for i in xrange(num):
            self.InsertStringItem(i, self.getText(self.data, i, first_col))
            for col,rank in active_columns[1:]:
                txt = self.getText(self.data, i, col)
                self.SetStringItem(i, rank, txt)
            self.info_dict[self.data[i]["infohash"]] = i
            item = self.GetItem(i)
            status = self.data[i].get('status', 'unknown')
            if status == 'good':
                item.SetTextColour(wx.BLUE)
            elif status == 'dead':
                item.SetTextColour(wx.RED)
            self.SetItem(item)            
            
        self.Show(True)
        
    def setRelevanceThreshold(self,value):
        self.relevance_threshold = value

    def getRelevanceThreshold(self):
        return self.relevance_threshold

    def loadRelevanceThreshold(self):
        self.relevance_threshold = self.parent.utility.config.Read("rec_relevance_threshold", "int" )

    def saveRelevanceThreshold(self):
        self.parent.utility.config.Write( "rec_relevance_threshold", self.relevance_threshold)
        self.parent.utility.config.Flush()


class FilePanel(wx.Panel):
    def __init__(self, frame, parent ,categorykey):
        self.parent = parent
        self.frame = frame
        self.categorykey = categorykey
        self.utility = frame.utility
        
        wx.Panel.__init__(self, parent, -1)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        # Arno: Somehow the list gets painted over the other controls below it in
        # the window if we specifiy a size of  the list, so don't.
        self.list = FileList(self, self.categorykey)
        self.list.Show(True)
        mainbox.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        botbox = self.createBotUtility()
        mainbox.Add(botbox, 0, wx.EXPAND|wx.ALL, 5)

        self.SetSizer(mainbox)
        self.SetAutoLayout(True)
        self.Show(True)

        self.Bind(masked.EVT_NUM, self.OnSetRelevanceThreshold, self.relev_ctl)

    def createBotUtility(self):
        botbox = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self, -1, self.utility.lang.get('recommendinstructions'))
        botbox.Add(label, 0, wx.EXPAND|wx.ALL, 5)
        
        relev_box = wx.BoxSizer(wx.HORIZONTAL)
        relev_box.Add(wx.StaticText(self, -1, self.utility.lang.get('recommendfilter')), 0, wx.ALIGN_CENTER_VERTICAL)
        self.relev_ctl = self.utility.makeNumCtrl(self, self.list.getRelevanceThreshold()/relevance_display_factor, min = 0.0, max = 65536.0, fractionWidth = 2)
        relev_box.Add(self.relev_ctl, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        relev_box.Add(wx.StaticText(self, -1, self.utility.lang.get('recommendfilterall')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        botbox.Add(relev_box, 1, wx.EXPAND|wx.ALL, 5)
        return botbox

    def updateFileList(self,relevance_threshold=0):
        self.list.setRelevanceThreshold(relevance_threshold)
        self.list.loadList()

    def clickAndDownload(self, src):
        return self.utility.queue.addtorrents.AddTorrentFromFile(src, forceasklocation = False)

    def OnSetRelevanceThreshold(self,event=None):
        value = self.relev_ctl.GetValue()
        value = int(value * relevance_display_factor)
        self.updateFileList(value)

    def updateColumns(self, force=False):
        self.list.loadList(False, False)

class ABCFileFrame(wx.Frame):
    def __init__(self, parent):
        
        self.utility = parent.utility
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('tb_file_short'), 
                          size=self.utility.frame.fileFrame_size, 
                          pos=self.utility.frame.fileFrame_pos)    

        self.main_panel = self.createMainPanel()
        
        self.count = 0                          
        self.loadFileList = False

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_IDLE, self.updateFileList)        
        
        self.Show()
        
    def createMainPanel(self):
        main_panel = wx.Panel(self)
        
        self.createNoteBook(main_panel)
        bot_box = self.createBottomBoxer(main_panel)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        mainbox.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        mainbox.Add(bot_box, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        main_panel.SetSizer(mainbox)
        
        return main_panel

    def loadDatabase(self):
        self.mypref_db = self.utility.mypref_db
        
    def createNoteBook(self, main_panel):
        self.loadDatabase()
        self.notebook = wx.Notebook(main_panel, -1)
        
#        self.filePanel = AllFilePanel(self, self.notebook)
        keys = Category.getInstance().getCategoryKeys()
        self.filePanels = []
        for key in keys:
#            if key == 'xxx':
#                continue
            panel = FilePanel(self, self.notebook, key)
            self.filePanels.append(panel)
            self.notebook.AddPage(panel, key)
        self.myPreferencePanel = MyPreferencePanel(self, self.notebook)
#        self.notebook.AddPage(self.filePanel, self.utility.lang.get('file_list_title'))
        self.notebook.AddPage(self.myPreferencePanel, self.utility.lang.get('mypref_list_title'))
        
        
    def createBottomBoxer(self, main_panel):
        bot_box = wx.BoxSizer(wx.HORIZONTAL)
        button = wx.Button(main_panel, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.OnCloseWindow, button)
        bot_box.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        return bot_box

    def updateMyPref(self):    # used by File List
        self.myPreferencePanel.list.loadList()
        
    def updateFileList(self, event=None):
        # Arno: on Linux, the list does not get painted properly before this
        # idle handler is called, which is weird. Hence, I wait for the next
        # idle event and load the filelist there.
        self.count += 1
        if not self.loadFileList and self.count >= 2:
            self.Unbind(wx.EVT_IDLE)
            for panel in self.filePanels:
                panel.list.loadList()
#            self.filePanel.list.loadList()
            self.count = 0
            #self.filePanel.list.Show(True)
        
    def OnCloseWindow(self, event = None):
        for panel in self.filePanels:
                panel.list.saveRelevanceThreshold()
#        self.filePanel.list.saveRelevanceThreshold()
        self.utility.frame.fileFrame_size = self.GetSize()
        self.utility.frame.fileFrame_pos = self.GetPosition()
        self.utility.frame.fileFrame = None
        self.utility.abcfileframe = None
        
        self.Destroy()
        
