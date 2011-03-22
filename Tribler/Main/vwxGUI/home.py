import wx
import sys
import os
import random
from time import time, strftime

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_header import *
from Tribler.Main.vwxGUI.list_footer import *

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.tribler_topButton import SortedListCtrl
from Tribler.Category.Category import Category
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from __init__ import LIST_GREY, LIST_BLUE

from Tribler.Core.CacheDB.SqliteCacheDBHandler import NetworkBuzzDBHandler, UserEventLogDBHandler, TorrentDBHandler, BarterCastDBHandler, PeerDBHandler, ChannelCastDBHandler
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT

class Home(wx.Panel):
    def __init__(self):
        pre = wx.PrePanel()
        # the Create step is done by XRC. 
        self.PostCreate(pre)
        if sys.platform == 'linux2': 
            self.Bind(wx.EVT_SIZE, self.OnCreate)
        else:
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)

    def OnCreate(self, event):
        if sys.platform == 'linux2': 
            self.Unbind(wx.EVT_SIZE)
        else:
            self.Unbind(wx.EVT_WINDOW_CREATE)
        
        wx.CallAfter(self._PostInit)
        event.Skip()
    
    def _PostInit(self):
        self.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        #infopanel = InfoPanel(self)
        #vSizer.Add(infopanel, 0, wx.EXPAND)
        
        vSizer.AddStretchSpacer()
        
        buzzpanel = BuzzPanel(self)
        vSizer.Add(buzzpanel, 0, wx.EXPAND)
        
        self.SetSizer(vSizer)
        self.Layout()
        
class Stats(wx.Panel):
    def __init__(self):
        self.ready = False
        pre = wx.PrePanel()
        # the Create step is done by XRC. 
        self.PostCreate(pre)
    
    def Show(self):
        if not self.ready:
            self._PostInit()
        wx.Panel.Show(self)
    
    def _PostInit(self):
        self.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NetworkPanel(self), 1, wx.EXPAND|wx.BOTTOM|wx.RIGHT, 10)
        self.activity = ActivityPanel(self)
        hSizer.Add(self.activity, 1, wx.EXPAND|wx.BOTTOM, 10)
        vSizer.Add(hSizer, 0, wx.EXPAND)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NewTorrentPanel(self), 1, wx.EXPAND|wx.RIGHT, 10)
        hSizer.Add(PopularTorrentPanel(self), 1, wx.EXPAND|wx.RIGHT, 10)
        hSizer.Add(TopContributorsPanel(self), 1, wx.EXPAND)
        vSizer.Add(hSizer, 0, wx.EXPAND)
        
        self.SetSizer(vSizer)
        self.Layout()
        self.ready = True
    
    def onActivity(self, msg):
        if self.ready:
            self.activity.onActivity(msg)
        
class HomePanel(wx.Panel):
    def __init__(self, parent, title, background):
        wx.Panel.__init__(self, parent)
        
        self.guiutility = GUIUtility.getInstance()
        self.guiserver = GUITaskQueue.getInstance()
        self.SetBackgroundColour(background)
     
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.header = self.CreateHeader()
        self.header.SetTitle(title)
        self.header.SetBackgroundColour(background)
        vSizer.Add(self.header, 0, wx.EXPAND)
        
        self.panel = self.CreatePanel()
        if self.panel:
            vSizer.Add(self.panel, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 1)
        
        self.footer = self.CreateFooter()
        self.footer.SetBackgroundColour(background)
        vSizer.Add(self.footer, 0, wx.EXPAND)
        
        self.SetSizer(vSizer)
        self.Layout()
        
    def CreateHeader(self):
        return TitleHeader(self, [])
    def CreatePanel(self):
        pass
    def CreateFooter(self):
        return ListFooter(self)
    
    def DoLayout(self):
        self.Freeze()
        self.Layout()
        self.GetParent().Layout()
        self.Thaw()
        
class InfoPanel(HomePanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Welcome to Tribler' , LIST_BLUE)
    
    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)
        
        text = wx.StaticText(panel, -1, "Welcome to Tribler\nblablabla")
        sizer = wx.BoxSizer()
        sizer.Add(text, 1, wx.EXPAND|wx.ALL, 5)
        panel.SetSizer(sizer)
        return panel

class NetworkPanel(HomePanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Network info' , LIST_BLUE)
        
        self.torrentdb = TorrentDBHandler.getInstance()
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.remotetorrenthandler = RemoteTorrentHandler.getInstance()
        self.timer = None
        
        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])
        self.UpdateStats()
        
    def CreatePanel(self):
        def getBoldText(parent, text):
            statictext = wx.StaticText(parent, -1, text)
            font = statictext.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            statictext.SetFont(font)
            return statictext
        
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.nrTorrents = wx.StaticText(panel)
        self.nrFiles = wx.StaticText(panel)
        self.totalSize = wx.StaticText(panel)
        self.queueSize = wx.StaticText(panel)
        self.nrChannels = wx.StaticText(panel)
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        
        gridSizer.Add(wx.StaticText(panel, -1, 'Number files'), 0, wx.LEFT, 10)
        gridSizer.Add(self.nrFiles, 0, wx.EXPAND|wx.LEFT, 10)
        gridSizer.Add(wx.StaticText(panel, -1, 'Total size'), 0, wx.LEFT, 10)
        gridSizer.Add(self.totalSize, 0, wx.EXPAND|wx.LEFT, 10)
        gridSizer.Add(wx.StaticText(panel, -1, 'Torrents collected'), 0, wx.LEFT, 10)
        gridSizer.Add(self.nrTorrents, 0, wx.EXPAND|wx.LEFT, 10)
        gridSizer.Add(wx.StaticText(panel, -1, 'Torrents in queue'), 0, wx.LEFT, 10)
        gridSizer.Add(self.queueSize, 0, wx.EXPAND|wx.LEFT, 10)
        gridSizer.Add(wx.StaticText(panel, -1, 'Channels found'), 0, wx.LEFT, 10)
        gridSizer.Add(self.nrChannels, 0, wx.EXPAND|wx.LEFT, 10)
        
        vSizer.Add(gridSizer, 0, wx.EXPAND)
        panel.SetSizer(vSizer)
        return panel
    
    def OnNotify(self, subject, type, infohash):
        if self.IsShownOnScreen():
            self.UpdateStats()
             
    def UpdateStats(self):
        def db_callback():
            stats = self.torrentdb.getTorrentsStats()
            wx.CallAfter(self._UpdateStats, stats)
        
        self.guiserver.add_task(db_callback, id = "NetworkPanel_UpdateStats")
        
    def _UpdateStats(self, stats):
        self.nrTorrents.SetLabel(str(stats[0]))
        self.totalSize.SetLabel(self.guiutility.utility.size_format(stats[1]))
        self.nrFiles.SetLabel(str(stats[2]))
        self.queueSize.SetLabel('%d (%d sources)'%self.remotetorrenthandler.getQueueSize())
        self.nrChannels.SetLabel(str(self.channelcastdb.getNrChannels()))
        
        if self.timer:
            self.timer.Restart(10000)
        else:
            self.timer = wx.CallLater(10000, self.UpdateStats)

class NewTorrentPanel(HomePanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Newest Torrents' , LIST_BLUE)
        self.Layout()
        
        self.torrentdb = TorrentDBHandler.getInstance()
        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])
    
    def CreatePanel(self):
        self.list = SortedListCtrl(self, 1, style = wx.LC_REPORT|wx.LC_NO_HEADER)
        self.list.InsertColumn(0, 'Torrent')
        self.list.setResizeColumn(0)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.list.SetMinSize((1, 80))
        return self.list
    
    def OnNotify(self, subject, type, infohash):
        if self.IsShownOnScreen():
            self.UpdateStats(infohash)
            
    def UpdateStats(self, infohash):
        def db_callback():
            torrent = self.torrentdb.getTorrent(infohash, include_mypref=False)
            if torrent:
                wx.CallAfter(self._UpdateStats, torrent)
        
        self.guiserver.add_task(db_callback, id = "NewTorrentPanel_UpdateStats")
        
    def _UpdateStats(self, torrent):
        self.list.InsertStringItem(0, torrent['name'])
        size = self.list.GetItemCount()
        if size > 10:
            self.list.DeleteItem(size-1)
    
    def OnDoubleClick(self, event):
        selected = self.list.GetFirstSelected()
        if selected != -1:
            selected_file = self.list.GetItemText(selected)
            self.guiutility.dosearch(selected_file)

class PopularTorrentPanel(NewTorrentPanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Popular Torrents' , LIST_BLUE)
        self.Layout()
        
        self.torrentdb = TorrentDBHandler.getInstance()
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(10000, False)
        self.RefreshList()
    
    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.RefreshList()
            
    def RefreshList(self):
        def db_callback():
            familyfilter_sql = Category.getInstance().get_family_filter_sql(self.torrentdb._getCategoryID)
            if familyfilter_sql:
                familyfilter_sql = familyfilter_sql[4:]
            
            topTen = self.torrentdb._db.getAll("CollectedTorrent", ("infohash", "name", "(num_seeders+num_leechers) as popularity"), where = familyfilter_sql , order_by = "(num_seeders+num_leechers) DESC", limit= 10)
            wx.CallAfter(self._RefreshList, topTen)
        
        self.guiserver.add_task(db_callback, id = "PopularTorrentPanel_RefreshList")
    
    def _RefreshList(self, topTen):
        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen:
            if item[2] > 0:
                self.list.InsertStringItem(sys.maxint, item[1])
        self.list.Thaw()

class TopContributorsPanel(HomePanel):             
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Top Contributors' , LIST_BLUE)
        self.Layout()
        
        self.peerdb = PeerDBHandler.getInstance()
        self.barterdb = BarterCastDBHandler.getInstance()
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(10000, False)
        self.RefreshList()
    
    def CreatePanel(self):
        self.list = SortedListCtrl(self, 2, style = wx.LC_REPORT|wx.LC_NO_HEADER)
        self.list.InsertColumn(0, 'Name')
        self.list.InsertColumn(1, 'Up', wx.LIST_FORMAT_RIGHT)
        self.list.setResizeColumn(0)
        
        return self.list

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.RefreshList()
    
    def RefreshList(self):
        def db_callback():
            topTen = self.barterdb.getTopNPeers(10)
            wx.CallAfter(self._RefreshList, topTen)
        self.guiserver.add_task(db_callback, id = "TopContributorsPanel_RefreshList")
    
    def _RefreshList(self, topTen):
        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen['top']:
            name = self.peerdb.getPeer(item[0], 'name')
            if name:
                pos = self.list.InsertStringItem(sys.maxint, name)
                self.list.SetStringItem(pos, 1, self.guiutility.utility.size_format(item[1], 1))
        
        self.list.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self.list.Layout()
        self.list.Thaw()
        
    def OnDoubleClick(self, event):
        pass
    

class ActivityPanel(NewTorrentPanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Recent Activity' , LIST_BLUE)

    def onActivity(self, msg):
        msg = strftime("%H:%M:%S ") + msg
        self.list.InsertStringItem(0, msg)
        size = self.list.GetItemCount()
        if size > 50:
            self.list.DeleteItem(size-1)
                
class BuzzPanel(HomePanel):
    INACTIVE_COLOR = (255, 51, 0)
    ACTIVE_COLOR = (0, 105, 156)
    
    TERM_BORDERS = [15, 8, 8]
    DISPLAY_SIZES = [3,5,5]
    REFRESH_EVERY = 5
    
    def __init__(self, parent):
        self.nbdb = NetworkBuzzDBHandler.getInstance()
        self.xxx_filter = Category.getInstance().xxx_filter
        
        HomePanel.__init__(self, parent, 'Network Buzz', LIST_GREY)
         
        self.tags = []
        self.buzz_cache = [[],[],[]]
        self.last_shown_buzz = None
        
        row1_font = self.GetFont()
        row1_font.SetPointSize(row1_font.GetPointSize() + 10)
        row1_font.SetWeight(wx.FONTWEIGHT_BOLD)
        
        row2_font = self.GetFont()
        row2_font.SetPointSize(row2_font.GetPointSize() + 4)
        row2_font.SetWeight(wx.FONTWEIGHT_BOLD)
        
        row3_font = self.GetFont()
        row3_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.TERM_FONTS = [row1_font, row2_font, row3_font]

        self.header.Bind(wx.EVT_ENTER_WINDOW, lambda event: self.OnLeaveWindow())
        self.footer.Bind(wx.EVT_ENTER_WINDOW, lambda event: self.OnLeaveWindow())
        self.panel.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.panel.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)

        self.vSizer.Add(self.getStaticText('...collecting buzz information...'), 0, wx.ALIGN_CENTER)
        
        self.GetBuzzFromDB()  
        self.refresh = 1
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self.timer)
        self.timer.Start(1000, False)
    
    def CreateHeader(self):
        header = FamilyFilterHeader(self, [])
        header.SetFF(self.guiutility.getFamilyFilter())
        return header

    def CreateFooter(self):
        return TitleFooter(self)

    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(self.vSizer)
        
        return panel
    
    def toggleFamilyFilter(self):
        self.guiutility.toggleFamilyFilter()
        self.header.SetFF(self.guiutility.getFamilyFilter())
        self.ForceUpdate()
    
    def ForceUpdate(self):
        self.GetBuzzFromDB()
        self.refresh = 1
        
    def GetBuzzFromDB(self):
        # needs fine-tuning:
        # (especially for cold-start/fresh Tribler install?)
        samplesize = NetworkBuzzDBHandler.DEFAULT_SAMPLE_SIZE
        
        self.buzz_cache = [[],[],[]]
        buzz = self.nbdb.getBuzz(samplesize, with_freq=True, flat=True)
        for i in range(len(buzz)):
            random.shuffle(buzz[i])
            self.buzz_cache[i] = buzz[i]
    
    def OnRefreshTimer(self, event = None):
        self.refresh -= 1
        if self.refresh <= 0:
            if self.IsShownOnScreen() and self.guiutility.ShouldGuiUpdate():
                # simple caching
                # (does not check for possible duplicates within display_size-window!)
                if any(len(row) < 10 for row in self.buzz_cache):
                    self.guiserver.add_task(self.GetBuzzFromDB, id = "BuzzPanel_GetBuzzFromDB")
                
                if self.guiutility.getFamilyFilter():
                    xxx_filter = self.xxx_filter.isXXX
                    self.header.SetFF(True)
                else:
                    xxx_filter = lambda *args, **kwargs: False
                    self.header.SetFF(False)
                
                # consume cache
                # Note: if a term is fetched from two different row caches, it is shown in the
                # higher-frequency row, regardless of which information is fresher.
                filtered_buzz = [[],[],[]]
                empty = True
                added_terms = set()
                for i in range(len(filtered_buzz)):
                    while len(filtered_buzz[i]) < BuzzPanel.DISPLAY_SIZES[i] and len(self.buzz_cache[i]):
                        term, freq = self.buzz_cache[i].pop(0)
                        if term not in added_terms and not xxx_filter(term, isFilename=False):
                            filtered_buzz[i].append((term, freq))
                            added_terms.add(term)
                            empty = False
                
                if empty:
                    filtered_buzz = None
                self.DisplayTerms(filtered_buzz)
                self.last_shown_buzz = filtered_buzz
            self.refresh = BuzzPanel.REFRESH_EVERY
            
        self.footer.SetTitle('Update in %d...'%self.refresh)
    
    def getStaticText(self, term, font = None):
        if len(self.tags) > 0:
            text = self.tags.pop()
            text.SetLabel(term)
        else:
            text = wx.StaticText(self.panel, wx.ID_ANY, term)
            text.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        
        if font:
            text.SetFont(font)
        text.SetForegroundColour(BuzzPanel.INACTIVE_COLOR)
        text.SetToolTipString("Click to search for '%s'"%term)
        return text
    
    def DisplayTerms(self, rows):
        if rows:
            self.Freeze()
            self.vSizer.ShowItems(False)
            self.vSizer.Clear()
            
            cur_tags = []
            for i in range(len(rows)):
                row = rows[i]
                if len(row) == 0:
                    # don't bother adding an empty hsizer
                    continue
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.AddStretchSpacer(2)
                
                for term, freq in row:
                    text = self.getStaticText(term, self.TERM_FONTS[i])
                    cur_tags.append(text)
                    
                    hSizer.Add(text, 0, wx.BOTTOM, self.TERM_BORDERS[i])
                    hSizer.AddStretchSpacer()
                hSizer.AddStretchSpacer()                    
                self.vSizer.Add(hSizer, 0, wx.EXPAND)
        
            self.vSizer.ShowItems(True)
            self.vSizer.Layout()
        
            # destroy all unnecessary statictexts
            for text in self.tags:
                text.Destroy()
            self.tags = cur_tags
        
            self.DoLayout()
            self.Thaw()
    
    def DoPauseResume(self):
        def IsEnter(control):
            if getattr(control, 'GetWindow', False):
                control = control.GetWindow()
                
            if getattr(control, 'enter', False): 
                return True
        
            if getattr(control, 'GetChildren', False): 
                children = control.GetChildren()
                for child in children:
                    if IsEnter(child):
                        return True
            return False
        
        enter = getattr(self.panel, 'enter', False) or IsEnter(self)
        timerstop = not enter #stop timer if one control has enter==true
        
        if timerstop != self.timer.IsRunning():
            if enter:
                self.timer.Stop()
                self.footer.SetTitle('Update has paused')
            else:
                self.timer.Start(1000, False)
                self.footer.SetTitle('Resuming update')
    
    def OnMouse(self, event):
        if event.Entering() or event.Moving():
            self.OnEnterWindow(event)
        elif event.Leaving():
            self.OnLeaveWindow(event)
        elif event.LeftUp():
            self.OnClick(event)
    
    def OnEnterWindow(self, event):
        evtobj = event.GetEventObject()
        evtobj.enter = True
        self.DoPauseResume()
        
        if evtobj != self:
            self.ShowSelected(evtobj)
        
    def OnLeaveWindow(self, event = None):
        if event:
            evtobj = event.GetEventObject()
            evtobj.enter = False
        
        self.DoPauseResume()
        self.ShowSelected()

    def ShowSelected(self, statictext = None):
        if statictext:
            statictext.enter = True
            statictext.SetForegroundColour(BuzzPanel.ACTIVE_COLOR)
            statictext.Refresh()
        
        for column in self.panel.GetChildren():
            if column != statictext and isinstance(column, wx.StaticText):
                if column.ForegroundColour != BuzzPanel.INACTIVE_COLOR:
                    column.enter = False
                    column.SetForegroundColour(BuzzPanel.INACTIVE_COLOR)
                    column.Refresh()

    def OnClick(self, event):
        evtobj = event.GetEventObject()
        term = evtobj.GetLabel()
        if term <> '...collecting buzz information...':
            self.guiutility.dosearch(term)
            
            #Deselect all terms + doresume
            self.ShowSelected()
            self.DoPauseResume()
            
            uelog = UserEventLogDBHandler.getInstance()
            uelog.addEvent(message=repr((term, self.last_shown_buzz)))