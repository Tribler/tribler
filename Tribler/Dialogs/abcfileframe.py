# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

import wx
from wx.lib import masked
import os
from base64 import encodestring
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
from Tribler.utilities import friendly_time, sort_dictlist
from Tribler.unicode import str2unicode
from common import CommonTriblerList

DEBUG = False

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
    def __init__(self, parent, window_size):
        self.parent = parent
        self.mypref_db = parent.mypref_db
        self.min_rank = -1
        self.max_rank = 5
        CommonTriblerList.__init__(self, parent, window_size)

    def getColumns(self):
        format = wx.LIST_FORMAT_CENTER
        columns = [
            ('Content Name', format, 30),
            ('Rank', format, 8),
            ('Size', format, 12),
            ('Last Seen', format, 10)  
            ]
        return columns
        
    def getListKey(self):
        return ['content_name', 'rank', 'length', 'last_seen']
        
    def getCurrentSortColumn(self):
        return 1

    def getMaxNum(self):
        return 1000
        
    def getText(self, data, row, col):
        key = self.list_key[col]
        if DEBUG:
            print "fileframe: getText",key
        original_data = data[row][key]
        if key == 'length':
            length = original_data/1024/1024.0
            return '%.2f MB'%(length)
        elif key == 'last_seen':
            if original_data == 0:
                return 'Never'
            return friendly_time(original_data)
        return str2unicode(original_data)
        
    def reloadData(self):
        myprefs = self.mypref_db.getPrefList()
        keys = ['infohash', 'torrent_name', 'info', 'content_name', 'rank', 'last_seen']
        self.data = self.mypref_db.getPrefs(myprefs, keys)
        for i in xrange(len(self.data)):
            info = self.data[i]['info']
            self.data[i]['length'] = info.get('length', 0)
            if self.data[i]['torrent_name'] == '':
                self.data[i]['torrent_name'] = '-'
            if self.data[i]['content_name'] == '':
                self.data[i]['content_name'] = '-'
        
    def getMenuItems(self, min_rank, max_rank):
        menu_items = {}
        for i in range(min_rank, max_rank+1):
            id = wx.NewId()
            func = 'OnRank' + str(i - min_rank)
            func = getattr(self, func)
            if i == -1:
                label = "Fake File"
            elif i == 0:
                label = "No Rate"
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
                self.Bind(wx.EVT_MENU, self.menu_items[i]['func'], id=self.menu_items[i]['id'])
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
            
        sm.AppendMenu(self.adjustRankID, "Rank items", submenu)
        sm.Append(self.deletePrefID, 'Delete')
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()
        
    def changeRank(self, curr_idx, rank):
        torrent = self.data[curr_idx]
        torrent['rank'] = rank
        self.mypref_db.updateRank(torrent['infohash'], rank)
        self.SetStringItem(curr_idx, 2, str(rank))
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
            j += 1
        self.mypref_db.sync()


class FileList(CommonTriblerList):
    def __init__(self, parent, window_size):
        self.parent = parent
        self.torrent_db = parent.torrent_db
        self.min_rank = -1
        self.max_rank = 5
        self.loadRelevanceThreshold()
        CommonTriblerList.__init__(self, parent, window_size)

    def getColumns(self):
        format = wx.LIST_FORMAT_CENTER
        columns = [
            ('Content Name', format, 30),
            ('Recommendation', format, 8),
            ('#Downloads', format, 8),
            ('Size', format, 12),
            ('#Files', format, 5),
            ('Injected', format, 12),
            ('Tracker', format, 24)
#            ('Torrent ID', format, 8),
#            ('Seeder', format, 6),
#            ('Leecher', format, 6),  
            ]
        return columns
        
    def getListKey(self):
        return ['content_name', 'relevance', 'num_owners', 'length', 
                'num_files', 'date', 'tracker'] # , 'infohash', 'seeder', 'leecher']
        
    def getCurrentSortColumn(self):
        return 1    # reverse sort by recommendation by default
        
    def getCurrentOrders(self):
         return [0, 1, 0, 1, 0, 0, 0]

    def getMaxNum(self):
        return 1000
        
    # change display format for item data
    def getText(self, data, row, col):
        key = self.list_key[col]
        original_data = data[row][key]
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
                return 'unknown'
            return friendly_time(original_data)
#        if key == 'seeder' or key == 'leecher':
#            if original_data < 0:
#                return '-'
        return str2unicode(original_data)
        
    def loadList(self, reload=True):

        if reload:
            self.reloadData()
        
        self.data = sort_dictlist(self.data, self.list_key[self.sort_column], self.orders[self.sort_column])

        # remove everything below relevance threshold
        for i in xrange(len(self.data)-1,-1,-1):
            if self.data[i]['relevance'] < self.relevance_threshold:
                del self.data[i]

        if self.num <= 0 or self.num>len(self.data):
            self.num = len(self.data)
        
        self.DeleteAllItems() 
        i = 0
        for i in xrange(self.num):
            self.InsertStringItem(i, self.getText(self.data, i, 0))
            for j in range(1, len(self.list_key)):
                self.SetStringItem(i, j, self.getText(self.data, i, j))
            src = os.path.join(self.data[i]['torrent_dir'], self.data[i]['torrent_name'])
            if os.path.isfile(src):
                item = self.GetItem(i)
                item.SetTextColour(wx.BLUE)
                self.SetItem(item)
            i += 1
            
        self.Show(True)        
        
    def reloadData(self):
        torrent_list = self.torrent_db.getOthersTorrentList()
        key = ['infohash', 'torrent_name', 'torrent_dir', 'relevance', 'info', 'num_owners']
        self.data = self.torrent_db.getTorrents(torrent_list, key)
        self.data = filter(lambda x:x['info'], self.data)

        for i in xrange(len(self.data)):
            info = self.data[i]['info']
            self.data[i]['length'] = info.get('length', 0)
            self.data[i]['content_name'] = info.get('name', 'unknown')
            if self.data[i]['torrent_name'] == '':
                self.data[i]['torrent_name'] = 'unknown'
            self.data[i]['content_name'] = info.get('name', 'unknown')
#            self.data[i]['seeder'] = -1
#            self.data[i]['leecher'] = -1
            self.data[i]['num_files'] = info.get('num_files', 0)
            self.data[i]['date'] = info.get('creation date', 0) #friendly_time(info.get('creation date', 0))
            self.data[i]['tracker'] = info.get('announce', '')
            
    def OnDeleteTorrent(self, event=None):
        selected = self.getSelectedItems()
        j = 0
        for i in selected:
            infohash = self.data[i-j]['infohash']
            self.torrent_db.deleteTorrent(infohash)
            self.DeleteItem(i-j)
            self.data.pop(i-j)
            j += 1
        self.torrent_db.sync()
            
    def OnRightClick(self, event=None):
        if not hasattr(self, "deleteTorrentID"):
            self.deleteTorrentID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeleteTorrent, id=self.deleteTorrentID)
            
        # menu for change torrent's rank
        sm = wx.Menu()
        sm.Append(self.deleteTorrentID, 'Delete')
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()
        
    def OnActivated(self, event):
        self.curr_idx = event.m_itemIndex
        src = os.path.join(self.data[self.curr_idx]['torrent_dir'], self.data[self.curr_idx]['torrent_name'])
        if os.path.isfile(src):
            if self.data[self.curr_idx]['content_name']:
                name = self.data[self.curr_idx]['content_name']
            else:
                name = showInfoHash(self.data[self.curr_idx]['infohash'])
            str = "Start downloading " + name + "?"
            dlg = wx.MessageDialog(self, str,
                                   'Click and Download',
                                   #wx.OK | wx.ICON_INFORMATION
                                   wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION
                                   )
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                src = os.path.join(self.data[self.curr_idx]['torrent_dir'], self.data[self.curr_idx]['torrent_name'])
                if os.path.isfile(src):
                    self.parent.clickAndDownload(src)
                    self.DeleteItem(self.curr_idx)
                    del self.data[self.curr_idx]
                    self.parent.frame.updateMyPref()

    def setRelevanceThreshold(self,value):
        self.relevance_threshold = value

    def getRelevanceThreshold(self):
        return self.relevance_threshold

    def loadRelevanceThreshold(self):
        self.relevance_threshold = self.parent.utility.config.Read( "rec_relevance_threshold", "int" )

    def saveRelevanceThreshold(self):
        self.parent.utility.config.Write( "rec_relevance_threshold", self.relevance_threshold)
        self.parent.utility.config.Flush()



class MyPreferencePanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.utility = frame.utility
        
        self.mypref_db = frame.mypref_db
        self.torrent_db = frame.torrent_db
        wx.Panel.__init__(self, parent, -1)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        self.list=MyPreferenceList(self, frame.window_size)
        mainbox.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        label = wx.StaticText(self, -1, "Right click on a torrent to assign a 1--5 star rating")
        mainbox.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(mainbox)
        self.SetAutoLayout(True)
        #self.Fit()
        self.Show(True)


class FilePanel(wx.Panel):
    def __init__(self, frame, parent):
        self.parent = parent
        self.frame = frame
        self.utility = frame.utility
        
        self.mypref_db = frame.mypref_db
        self.torrent_db = frame.torrent_db
        wx.Panel.__init__(self, parent, -1)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        #self.list=FileList(self, frame.window_size)
        # Arno: Somehow the list gets painted over the other controls below it in
        # the window if we specifiy a size of  the list, so don't.
        self.list=FileList(self, None)
        mainbox.Add(self.list, 1, wx.EXPAND|wx.ALL, 5)
        label = wx.StaticText(self, -1, self.utility.lang.get('recommendinstructions'))
        mainbox.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)

        self.relev_ctl = self.utility.makeNumCtrl(self, self.list.getRelevanceThreshold()/relevance_display_factor, min = 0.0, max = 65536.0, fractionWidth = 1)
        relev_box = wx.BoxSizer(wx.HORIZONTAL)
        relev_box.Add(wx.StaticText(self, -1, self.utility.lang.get('recommendfilter')), 0, wx.ALIGN_CENTER_VERTICAL)
        relev_box.Add(self.relev_ctl, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        relev_box.Add(wx.StaticText(self, -1, self.utility.lang.get('recommendfilterall')), 0, wx.ALIGN_CENTER_VERTICAL)
        mainbox.Add(relev_box, 0, wx.EXPAND|wx.ALL, 5)

        self.SetSizer(mainbox)
        self.SetAutoLayout(True)
        #self.Fit()
        self.Show(True)

        self.Bind(masked.EVT_NUM, self.OnSetRelevanceThreshold, self.relev_ctl )

    def clickAndDownload(self, src):
        self.utility.queue.addtorrents.AddTorrentFromFile(src, forceasklocation = False)

    def OnSetRelevanceThreshold(self,event=None):
        value = self.relev_ctl.GetValue()
        value = int(value * relevance_display_factor)
        self.frame.updateFile(value)


class ABCFileFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        
        width = 600
        height = 400
        self.window_size = wx.Size(width, height)
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('tb_file_short'), size=wx.Size(width+20, height+60))
       
        self.mypref_db = self.utility.mypref_db
        self.torrent_db = self.utility.torrent_db
        
        mainpanel = wx.Panel(self)
        # 1. Topbox contains the notebook
        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        self.notebook = wx.Notebook(mainpanel, -1)

        self.filePanel = FilePanel(self, self.notebook)
        self.notebook.AddPage(self.filePanel, "Recommended Torrents")

        self.myPreferencePanel = MyPreferencePanel(self, self.notebook)
        self.notebook.AddPage(self.myPreferencePanel, "My Download History")

        mainbox.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)

        # 2. Bottom box contains "Close" button
        botbox = wx.BoxSizer(wx.HORIZONTAL)

        button = wx.Button(mainpanel, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.OnCloseWindow)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        # 3. Pack boxes together
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        mainpanel.SetSizer(mainbox)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.SetSize(self.utility.frame.fileFrame_size)
        self.SetPosition(self.utility.frame.fileFrame_pos)
        self.Show()

    def updateMyPref(self):
        self.myPreferencePanel.list.loadList()
        
    def updateFile(self,relevance_threshold=0):
        self.filePanel.list.setRelevanceThreshold(relevance_threshold)
        self.filePanel.list.loadList()

    def OnCloseWindow(self, event = None):
        self.filePanel.list.saveRelevanceThreshold()
        self.utility.frame.fileFrame_size = self.GetSize()
        self.utility.frame.fileFrame_pos = self.GetPosition()
        self.utility.frame.fileFrame = None
        self.utility.abcfileframe = None
        
        self.Destroy()
        
