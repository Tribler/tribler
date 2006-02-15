import wx
import images
from base64 import decode
from Tribler.CacheDB.CacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
from Tribler.utilities import friendly_time, sort_dictlist


def showInfoHash(infohash):
    if infohash.startswith('torrent'):    # for testing
        return infohash
    try:
        return encodestring(infohash)
    except:
        return infohash

class MyPreferenceList(wx.ListCtrl):
    def __init__(self, parent):
        self.utility = parent.utility
        self.min_rank = -1
        self.max_rank = 5
        self.menu_items = self.getMenuItems(self.min_rank, self.max_rank)
        
        self.mypref_db = MyPreferenceDBHandler()

        self.list_key = ['infohash', 'torrent_name', 'content_name', 'rank', 'size', 'last_seen']
        self.column = -1
        self.order = [0, 0, 0, 1, 1, 1]    # 1 - decrease; 0 - increase

        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(780, 500), style=style)
        
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.test)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "Torrent Hash", format=wx.LIST_FORMAT_CENTER, width=fw*10)
        self.InsertColumn(1, "Torrent Name", format=wx.LIST_FORMAT_CENTER, width=fw*10)
        self.InsertColumn(2, "Content Name", format=wx.LIST_FORMAT_CENTER, width=fw*10)
        self.InsertColumn(3, "Rank", format=wx.LIST_FORMAT_CENTER, width=fw*7)
        self.InsertColumn(4, "Size", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(5, "Last Seen", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        
        myprefs = self.mypref_db.getPrefList()
        keys = ['infohash', 'torrent_name', 'info', 'content_name', 'rank', 'last_seen']
        self.torrents = self.mypref_db.getPrefs(myprefs, keys)
        
        self.loadList()
        
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

    def loadList(self, key='rank', order=1, num=100):

        if order == 1:
            self.torrents = sort_dictlist(self.torrents, key, 'decrease')[:num]
        else:
            self.torrents = sort_dictlist(self.torrents, key, 'increase')[:num]
        #self.torrents.sort()
        
#        for i in xrange(len(self.torrents)):
#        self.listInfo[i] = (type, name, revision, tag, option, status, date, conflict)
        
        self.DeleteAllItems() 
        i = 0
        for i in xrange(len(self.torrents)):
            torrent = self.torrents[i]
            torrent['infohash'] = showInfoHash(torrent['infohash'])
            self.InsertStringItem(i, str(torrent['infohash']))
            self.SetStringItem(i, 1, str(torrent['torrent_name']))
            self.SetStringItem(i, 2, str(torrent['content_name']))
            self.SetStringItem(i, 3, str(torrent['rank']))
            info = torrent['info']
            torrent['size'] = info.get('size', 0)
            self.SetStringItem(i, 4, str(torrent['size']))
            last_seen = friendly_time(torrent['last_seen'])
            self.SetStringItem(i, 5, last_seen)
            i += 1
            
        self.Show(True)
        
    def OnColClick(self, event):
        lastColumn = self.column
        self.column = event.m_col
        if self.column == lastColumn:
            self.order[self.column] = 1 - self.order[self.column]
        key = self.list_key[event.m_col]
        self.loadList(key, self.order[self.column])
        

    def test(self, event):
        rank = event.GetItem()
        print "test", rank
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        curr_rank = self.torrents[self.curr_idx]['rank']
        if not hasattr(self, "adjustRankID"):
            self.adjustRankID = wx.NewId()
            for i in self.menu_items:
                self.Bind(wx.EVT_MENU, self.menu_items[i]['func'], id=self.menu_items[i]['id'])
                
        # menu for change torrent's rank
        sm = wx.Menu()
        sm.Append(self.adjustRankID, "Rank items:")
        idx = self.menu_items.keys()
        idx.sort()
        idx.reverse()
        for i in idx:
            if i == curr_rank:
                label = '> '+self.menu_items[i]['label']
            else:
                label = '   '+self.menu_items[i]['label']
            sm.Append(self.menu_items[i]['id'], label)
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()
        
    def changeRank(self, rank):
        torrent = self.torrents[self.curr_idx]
        torrent['rank'] = rank
        self.mypref_db.updateRank(torrent['infohash'], rank)
        self.SetStringItem(self.curr_idx, 3, str(rank))
        #print "Set torrent", showInfoHash(torrent['infohash']), "rank", rank
        
    def OnRank(self, rank):
        return lambda rank: self.changeRank(rank)
        
    def OnRank0(self, event=None):
        self.changeRank(0+self.min_rank)
        
    def OnRank1(self, event=None):
        self.changeRank(1+self.min_rank)
        
    def OnRank2(self, event=None):
        self.changeRank(2+self.min_rank)
        
    def OnRank3(self, event=None):
        self.changeRank(3+self.min_rank)
        
    def OnRank4(self, event=None):
        self.changeRank(4+self.min_rank)
        
    def OnRank5(self, event=None):
        self.changeRank(5+self.min_rank)
        
    def OnRank6(self, event=None):
        self.changeRank(6+self.min_rank)
        

class FileList(wx.ListCtrl):
    def __init__(self, parent):
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(780, 500), style=style)
        
        self.utility = parent.utility

        self.loadList()

    def loadList(self):

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "ID", format=wx.LIST_FORMAT_CENTER, width=fw*3)
        self.InsertColumn(1, "Title", format=wx.LIST_FORMAT_CENTER, width=fw*25)
        self.InsertColumn(2, "Size", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(3, "Recommendation", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(4, "Last Used Time", format=wx.LIST_FORMAT_CENTER, width=fw*16)
        
        torrents = self.utility.all_files_cache.getTorrents()
        torrents.sort()
        
        i = 0
        for torrent in torrents:
            if int(torrent['have']) == 1:
                continue
            self.InsertStringItem(i, str(torrent['id']))
            self.SetStringItem(i, 1, torrent['content_name'])
            self.SetStringItem(i, 2, torrent['content_size'])
            self.SetStringItem(i, 3, str(torrent['recommendation']))
            self.SetStringItem(i, 4, torrent['last_seen'])    
            i += 1
            
        self.Show(True)
        
        
class MyPreferencePanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=MyPreferenceList(self)
        
        self.Show()


class FilePanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=FileList(self)
        
        self.Show()

        
class ABCFileFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        size = wx.Size(800, 500)
        wx.Frame.__init__(self, None, -1, "File Frame", wx.DefaultPosition, size)
       
        self.notebook = wx.Notebook(self, -1)

        self.myPreferencePanel = MyPreferencePanel(self.notebook, self.utility)
        self.notebook.AddPage(self.myPreferencePanel, "My Preference List")
#
#        self.filePanel = FilePanel(self.notebook, self.utility)
#        self.notebook.AddPage(self.filePanel, "All File List")

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self.Show()

    def OnCloseWindow(self, event = None):
        self.utility.frame.fileFrame = None
        self.Destroy()
        
