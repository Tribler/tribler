import wx
import images

class MyPreferenceList(wx.ListCtrl):
    def __init__(self, parent):
        self.utility = parent.utility
        
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
        self.utility = parent.utility
        
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.test)

        self.loadList()

    def loadList(self):

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "ID", format=wx.LIST_FORMAT_CENTER, width=fw*3)
        self.InsertColumn(1, "Title", format=wx.LIST_FORMAT_CENTER, width=fw*25)
        self.InsertColumn(2, "Size", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(3, "My Rank", format=wx.LIST_FORMAT_CENTER, width=fw*7)
        self.InsertColumn(4, "Last Used Time", format=wx.LIST_FORMAT_CENTER, width=fw*16)
        
        self.torrents = self.utility.all_files_cache.getPreferences()
        #self.torrents.sort()
        
        i = 0
        for torrent in self.torrents:
            self.InsertStringItem(i, str(torrent['id']))
            self.SetStringItem(i, 1, str(torrent['content_name']))
            self.SetStringItem(i, 2, torrent['content_size'])
            self.SetStringItem(i, 3, str(torrent['my_rank']))
            self.SetStringItem(i, 4, torrent['last_seen'])    
            i += 1

        self.Show(True)
        
    def test(self, event):
        rank = event.GetItem()
        print "test", rank
        
    def OnRightClick(self, event=None):
        self.curr_idx = event.m_itemIndex
        curr_rank = self.torrents[self.curr_idx]['my_rank']
        if not hasattr(self, "adjustRankID"):
            self.adjustRankID = wx.NewId()
            self.num_ranks = 5
            self.rankID = []
            self.OnRank = []
            self.OnRank.append(self.OnRank0)
            self.OnRank.append(self.OnRank1)
            self.OnRank.append(self.OnRank2)
            self.OnRank.append(self.OnRank3)
            self.OnRank.append(self.OnRank4)
            self.OnRank.append(self.OnRank5)
            for i in xrange(self.num_ranks+1):
                self.rankID.append(wx.NewId())
            for i in xrange(self.num_ranks+1):
                self.Bind(wx.EVT_MENU, self.OnRank[i], id=self.rankID[i])
                
        # menu for change torrent's rank
        sm = wx.Menu()
        sm.Append(self.adjustRankID, "Rank items:")
        for i in xrange(self.num_ranks, -1, -1):
            if i == 0:
                label = "No rating"
            else:
                label = ""
                for j in xrange(i):
                    label += "*"
            if i == curr_rank:
                item = wx.MenuItem(sm, self.rankID[i], label)
                bmp = images.getSmilesBitmap()
                item.SetBitmap(bmp)
                sm.AppendItem(item)
            else:
                sm.Append(self.rankID[i], label)
        
        self.PopupMenu(sm, event.GetPosition())
        sm.Destroy()
        
    def changeRank(self, rank):
        torrent = self.torrents[self.curr_idx]
        torrent['my_rank'] = rank
        self.utility.all_files_cache.updateTorrentRank(torrent['id'], rank)
        self.SetStringItem(self.curr_idx, 3, str(rank))
        print "Set torrent", torrent['id'], "rank", rank
        
    def OnRank0(self, event=None):
        self.changeRank(0)
        
    def OnRank1(self, event=None):
        self.changeRank(1)
        
    def OnRank2(self, event=None):
        self.changeRank(2)
        
    def OnRank3(self, event=None):
        self.changeRank(3)
        
    def OnRank4(self, event=None):
        self.changeRank(4)
        
    def OnRank5(self, event=None):
        self.changeRank(5)
        

class FileList(wx.ListCtrl):
    def __init__(self, parent):
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
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
        
        
class SharedFolderList(wx.ListCtrl):
    def __init__(self, parent):
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(800, 500), style=style)
        
        self.utility = parent.utility

        self.loadList()

    def loadList(self):

        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, "File Name", format=wx.LIST_FORMAT_CENTER, width=fw*15)
        self.InsertColumn(1, "Size", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(2, "Time", format=wx.LIST_FORMAT_CENTER, width=fw*8)
        self.InsertColumn(3, "Shared By # Friends", format=wx.LIST_FORMAT_CENTER, width=fw*8)

        self.InsertStringItem(0, 'Star Wars III')
        self.SetStringItem(0, 1, '735M')
        self.SetStringItem(0, 2, '18:23, Sep 21, 2005')
        self.SetStringItem(0, 3, '8')
        
        self.InsertStringItem(1, 'Love Story')
        self.SetStringItem(1, 1, '635M')
        self.SetStringItem(1, 2, '7:22, Sep 23, 2005')
        self.SetStringItem(1, 3, '5')
        
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

        
class SharedFolderPanel(wx.Panel):
    def __init__(self, parent, utility, dialog = None):
        self.utility = utility
        wx.Panel.__init__(self, parent, -1)

        self.list=SharedFolderList(self)
        
        self.Show()

        
class ABCFileFrame(wx.Frame):
    def __init__(self, parent):
        self.utility = parent.utility
        size = wx.Size(800, 500)
        wx.Frame.__init__(self, None, -1, "File Frame", wx.DefaultPosition, size)
       
        self.notebook = wx.Notebook(self, -1)

        self.myPreferencePanel = MyPreferencePanel(self.notebook, self.utility)
        self.notebook.AddPage(self.myPreferencePanel, "My Preference List")

        self.filePanel = FilePanel(self.notebook, self.utility)
        self.notebook.AddPage(self.filePanel, "All File List")

        #self.sharePanel = SharedFolderPanel(self.notebook, self.utility)
        #self.notebook.AddPage(self.sharePanel, "Shared Folder")
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self.Show()

    def OnCloseWindow(self, event = None):
        self.utility.frame.fileFrame = None
        self.Destroy()
        
