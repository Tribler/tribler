# Written by Niels Zeilemaker
import os
import sys
import wx.animate

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler, NetworkBuzzDBHandler

from widgets import ActionButton, GradientPanel, RoundedPanel, TextCtrlAutoComplete, ProgressButton
from Tribler.Main.vwxGUI import forceWxThread, TRIBLER_RED
from Tribler.Main.vwxGUI.widgets import _set_font
from Tribler.Main.vwxGUI.list_bundle import BundleListView
from Tribler.Main.vwxGUI.channel import SelectedChannelList
from Tribler.Main.Utility.GuiDBHandler import GUI_PRI_DISPERSY, startWorker
import time

DEBUG = False

class TopSearchPanelStub():

    def NextPage(self):
        pass
    
    def PrevPage(self):
        pass
    
    def SearchFocus(self):
        pass
    
    def Refresh(self):
        pass
    
    def Layout(self):
        pass

class TopSearchPanel(GradientPanel):
    def __init__(self, parent):
        if DEBUG:
            print >> sys.stderr , "TopSearchPanel: __init__"
        
        self.loaded_bitmap = None
        
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.installdir = self.utility.getPath()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.nbdb = None
        self.collectedTorrents = {}

        GradientPanel.__init__(self, parent, border = wx.BOTTOM)
        self.AddComponents()
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
    def AddComponents(self):
        self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BACKGROUND))
        
        if DEBUG:
            print >> sys.stderr, "TopSearchPanel: OnCreate"
        
        if sys.platform == 'darwin':
            self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER | wx.NO_BORDER )
            self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)
            self.searchField.SetDescriptiveText('Search Files or Channels')
            self.searchField.SetMinSize((400, 20))
        else:
            self.searchFieldPanel = RoundedPanel(self)            
            self.searchField = TextCtrlAutoComplete(self.searchFieldPanel, style=wx.NO_BORDER, entrycallback = self.complete, selectcallback = self.OnAutoComplete)
            # Since we have set the style to wx.NO_BORDER, the default height will be too large. Therefore, we need to set the correct height.
            _, height = self.GetTextExtent("Gg")
            self.searchField.SetMinSize((-1, height))
            self.searchFieldPanel.SetMinSize((400, 25))
            self.searchFieldPanel.SetBackgroundColour(self.searchField.GetBackgroundColour())
            self.searchField.Bind(wx.EVT_KILL_FOCUS, self.searchFieldPanel.OnKillFocus)
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)

        self.go = ProgressButton(self, -1)
        self.go.SetMinSize((50, 25))
        self.go.Bind(wx.EVT_LEFT_UP, self.OnSearchKeyDown)

        ag_fname = os.path.join(self.guiutility.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        self.ag.UseBackgroundColour(True)
        self.ag.SetBackgroundColour(wx.Colour(244,244,244))
        self.ag.Hide()

        download_bmp = self.Bitmap("images/download.png", wx.BITMAP_TYPE_ANY)
        self.download_btn = ActionButton(self, -1, download_bmp)
        self.download_btn.Enable(False)
        stop_bmp = self.Bitmap("images/pause.png", wx.BITMAP_TYPE_ANY)
        self.stop_btn = ActionButton(self, -1, stop_bmp)
        self.stop_btn.Enable(False)
        delete_bmp = self.Bitmap("images/delete.png", wx.BITMAP_TYPE_ANY)
        self.delete_btn = ActionButton(self, -1, delete_bmp)
        self.delete_btn.Enable(False)
        play_bmp = self.Bitmap("images/play.png", wx.BITMAP_TYPE_ANY)
        self.play_btn = ActionButton(self, -1, play_bmp)
        self.play_btn.Enable(False)
        add_bmp = self.Bitmap("images/add.png", wx.BITMAP_TYPE_ANY)
        self.add_btn = ActionButton(self, -1, add_bmp)
        self.SetButtonHandler(self.add_btn, self.OnAdd, 'Download an external torrent.')
        settings_bmp = self.Bitmap("images/settings.png", wx.BITMAP_TYPE_ANY)
        self.settings_btn = ActionButton(self, -1, settings_bmp)
        self.SetButtonHandler(self.settings_btn, self.OnSettings, 'Change settings.')

        mainSizer = wx.BoxSizer(wx.HORIZONTAL)

        if sys.platform != 'darwin':
            vSizer = wx.BoxSizer(wx.VERTICAL)
            vSizer.AddStretchSpacer()
            vSizer.Add(self.searchField, 0, wx.EXPAND | wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.LEFT | wx.RIGHT, 5)
            vSizer.AddStretchSpacer()
            self.searchFieldPanel.SetSizer(vSizer)
            vSizer.Layout()

        #Add searchbox etc.
        self.searchSizer = wx.BoxSizer(wx.VERTICAL)
        searchBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        if sys.platform == 'darwin':
            searchBoxSizer.Add(self.searchField, 1, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        else:
            searchBoxSizer.Add(self.searchFieldPanel, 1, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)    
        searchBoxSizer.Add(self.go, 0, wx.CENTER | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5) #add searchbutton
        searchBoxSizer.Add(self.ag, 0, wx.CENTER | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5) #add animation
        self.searchSizer.Add(searchBoxSizer, 1, wx.EXPAND)
        #finished searchSizer, add to mainSizer
        mainSizer.Add(self.searchSizer, 0, wx.EXPAND|wx.LEFT, 10)
        mainSizer.AddSpacer((40,0))

        #add buttons
        self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
        
        #add buttons horizontally
        buttonBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonBoxSizer.Add(self.download_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonBoxSizer.Add(self.stop_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonBoxSizer.Add(self.delete_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonBoxSizer.Add(self.play_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonBoxSizer.Add(wx.StaticLine(self, -1, style=wx.LI_VERTICAL), 0, wx.EXPAND|wx.ALL, 5)
        buttonBoxSizer.Add(self.add_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonBoxSizer.Add(self.settings_btn, 0, wx.CENTER|wx.RIGHT, 5)
        self.buttonSizer.Add(buttonBoxSizer, 1)
        mainSizer.Add(self.buttonSizer,0,wx.EXPAND)

        #niels: add strechingspacer, all controls added before 
        #this spacer will be aligned to the left of the screen
        #all controls added after, will be to the right
        mainSizer.AddStretchSpacer()
        self.SetSizer(mainSizer)
        self.Layout()
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
        
    def OnAutoComplete(self):
        self.uelog.addEvent(message="TopSearchPanel: user used autocomplete", type = 2)  
    
    def OnSearchKeyDown(self, event = None):
        if self.go.IsEnabled():
            if DEBUG:
                print >> sys.stderr, "TopSearchPanel: OnSearchKeyDown"
            
            if getattr(self.searchField, 'ShowDropDown', False):
                self.searchField.ShowDropDown(False)
                
            self.guiutility.dosearch()
            
            self.go.Enable(False)
            wx.CallLater(2500, self.go.Enable, True)

    def OnSettings(self, event):
        self.guiutility.ShowPage('settings')
    
    def OnAdd(self, event):
        dlg = AddTorrent(None, self.guiutility.frame)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()
    
    def OnStats(self, event):
        self.guiutility.ShowPage('stats')
        
    def StartSearch(self):
        if getattr(self.searchField, 'ShowDropDown', False):
            self.searchField.ShowDropDown(False)
            self.guiutility.frame.searchlist.ResetBottomWindow()
                
    def complete(self, term):
        """autocompletes term."""
        if len(term) > 1:
            if self.nbdb == None:
                self.nbdb = NetworkBuzzDBHandler.getInstance()
            return self.nbdb.getTermsStartingWith(term, num=7)
        return []

    def SearchFocus(self):
        if self.guiutility.guiPage == 'home':
            if getattr(self.GetParent(), 'home', False):
                self.GetParent().home.SearchFocus()
        else:
            self.searchField.SetFocus()
            self.searchField.SelectAll()

    def Bitmap(self, path, type):
        namelist = path.split("/")
        path = os.path.join(self.installdir, LIBRARYNAME, "Main", "vwxGUI", *namelist)
        return wx.Bitmap(path, type)

    def AddCollectedTorrent(self, coltorrent):
        self.collectedTorrents[coltorrent.infohash] = coltorrent
        self.TorrentsChanged()    
    
    def __getTorrents(self):
        torrents = None
        
        page = self.guiutility.guiPage
        if page in ['search_results', 'selectedchannel', 'playlist','my_files']:
            list = self.guiutility.GetSelectedPage()
            items = list.GetExpandedItems()
            torrents = [item[1].original_data for item in items if isinstance(item[1].original_data, Torrent) or isinstance(item[1].original_data, CollectedTorrent)]
        return torrents
   
    def TorrentsChanged(self):
        self.RefreshTorrents(self.__getTorrents())
        
    def RefreshTorrents(self, torrents):
        inDownloads = self.guiutility.guiPage == 'my_files'
        
        if torrents:
            usedCollectedTorrents = set()
            states = [0,0,0,0,0,0,0] #we have 7 different states, able to resume seeding, resume downloading, download, stop seeding, stop downloading, delete, or play
            for torrent in torrents:
                if 'stopped' in torrent.state:
                    if 'completed' in torrent.state:
                        states[0] += 1
                    else:
                        states[1] += 1
                        
                elif not torrent.state:
                    states[2] += 1
                
                if 'active' in torrent.state:
                    if 'completed' in torrent.state:
                        states[3] += 1
                    else:
                        states[4] += 1
                    
                if torrent.state or inDownloads:
                    states[5] += 1
            
                if torrent.infohash in self.collectedTorrents:
                    coltorrent = self.collectedTorrents[torrent.infohash]
                    if coltorrent.isPlayable():
                        states[6] += 1
                        
                    usedCollectedTorrents.add(torrent.infohash)
            
            enableDownload = states[0] + states[1] + states[2]
            if enableDownload:
                if enableDownload > 1:
                    self.SetButtonHandler(self.download_btn, self.OnDownload, 'Resume downloading/seeding the selected torrents.')
                elif states[0]:
                    self.SetButtonHandler(self.download_btn, self.OnResume, 'Resume seeding this torrent.')
                elif states[1]:
                    self.SetButtonHandler(self.download_btn, self.OnResume, 'Resume downloading this torrent.')
                else:
                    self.SetButtonHandler(self.download_btn, self.OnDownload, 'Start downloading this torrent.')
            else:
                self.SetButtonHandler(self.download_btn, None)
                    
            enableStop = states[3] + states[4]
            if enableStop:
                if enableStop > 1:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop downloading/seeding the selected torrents.')
                elif states[3]:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop seeding this torrent.')
                else:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop downloading this torrent.')
            else:
                self.SetButtonHandler(self.stop_btn, None)
            
            if states[5] > 1:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete the selected torrents.')
            elif states[5]:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete the selected torrent.')
            else:
                self.SetButtonHandler(self.delete_btn, None)
            
            if states[6] > 1:
                self.SetButtonHandler(self.play_btn, self.OnPlay, 'Start playing one of the selected torrents.')
            elif states[6]:
                self.SetButtonHandler(self.play_btn, self.OnPlay, 'Start playing this torrent.')
            else:
                self.SetButtonHandler(self.play_btn, None)

            for infohash in self.collectedTorrents.keys():
                if infohash not in usedCollectedTorrents:
                    del self.collectedTorrents[infohash]
        else:
            self.ClearButtonHandlers()
            
    def SetButtonHandler(self, button, handler = None, tooltip = None):
        button.Enable(bool(handler))
        if handler:
            button.Bind(wx.EVT_LEFT_UP, handler)
            if tooltip:
                button.SetToolTipString(tooltip)
            else:
                button.SetToolTip(None)
        else:
            button.SetToolTip(None)
            
    def ClearButtonHandlers(self):
        self.SetButtonHandler(self.download_btn, None)
        self.SetButtonHandler(self.play_btn, None)
        self.SetButtonHandler(self.stop_btn, None)
        self.SetButtonHandler(self.delete_btn, None)
    
    def OnDownload(self, event):
        refresh_library = False
        for torrent in self.__getTorrents():
            if 'stopped' in torrent.state:
                self.guiutility.library_manager.resumeTorrent(torrent)
            else:
                if self.guiutility.frame.searchlist.IsShownOnScreen():
                    self.guiutility.frame.searchlist.StartDownload(torrent, None)
                elif self.guiutility.frame.selectedchannellist.IsShownOnScreen():
                    self.guiutility.frame.selectedchannellist.StartDownload(torrent, None)
                else:
                    response = self.guiutility.torrentsearch_manager.downloadTorrent(torrent, selectedFiles = None)
                    if response:
                        self.guiutility.Notify('Downloading .Torrent file (%s)'%response, icon = wx.ART_INFORMATION)
                refresh_library = True
        button = event.GetEventObject()
        button.Enable(False)
        if refresh_library:
            wx.CallLater(1000, self.guiutility.frame.librarylist.do_or_schedule_refresh, True)

    def OnPlay(self, event):
        #Select the first playable torrent. Return if none can be found
        torrent = None
        for t in self.__getTorrents():
            if t.infohash in self.collectedTorrents:
                coltor = self.collectedTorrents[t.infohash]
                if coltor.isPlayable():
                    torrent = coltor
                    break
            
        if not torrent:
            return
        
        playable_files = torrent.videofiles

        if len(playable_files) > 1: #Create a popup
            playable_files.sort()
            
            dialog = wx.SingleChoiceDialog(self, 'Tribler currently only supports playing one file at a time.\nSelect the file you want to play?', 'Which file do you want to play?',playable_files)
        
            (_, selected_file) = max([(size, filename) for filename, size in torrent.files if filename in torrent.videofiles])
         
            if selected_file in playable_files:
                dialog.SetSelection(playable_files.index(selected_file))
            
            if dialog.ShowModal() == wx.ID_OK:
                selected_file = dialog.GetStringSelection()
            else:
                selected_file = None
            dialog.Destroy()
            
            if selected_file:
                self.guiutility.library_manager.playTorrent(torrent, selected_file)
                if not self.guiutility.frame.searchlist.IsShownOnScreen():
                    self.uelog.addEvent(message="Torrent: torrent play from channel", type = 2)
                else:
                    self.uelog.addEvent(message="Torrent: torrent play from other", type = 2)       
            
        elif len(playable_files) == 1:
            self.guiutility.library_manager.playTorrent(torrent)
            
            if not self.guiutility.frame.searchlist.IsShownOnScreen():
                self.uelog.addEvent(message="Torrent: torrent play from channel", type = 2)
            else:
                self.uelog.addEvent(message="Torrent: torrent play from other", type = 2)   

        button = event.GetEventObject()
        button.Enable(False)

    def OnResume(self, event):
        for torrent in self.__getTorrents():
            self.guiutility.library_manager.resumeTorrent(torrent)
        button = event.GetEventObject()        
        button.Enable(False)
    
    def OnStop(self, event):
        for torrent in self.__getTorrents():
            self.guiutility.library_manager.stopTorrent(torrent)
        button = event.GetEventObject()
        button.Enable(False)
    
    def OnDelete(self, event):
        for torrent in self.__getTorrents():
            dlg = RemoveTorrent(None, torrent)
            buttonId = dlg.ShowModal()
            if buttonId == wx.ID_DEFAULT:
                self.guiutility.library_manager.deleteTorrent(torrent)
                self.guiutility.frame.librarylist.RemoveItem(torrent)
                self.guiutility.frame.librarylist.do_or_schedule_refresh()
                if self.guiutility.frame.librarylist.IsShownOnScreen():
                    self.ClearButtonHandlers()
                    self.guiutility.SetBottomSplitterWindow(None)
            elif buttonId == wx.ID_DELETE:
                self.guiutility.library_manager.deleteTorrent(torrent, True)
                self.guiutility.frame.librarylist.RemoveItem(torrent)
                self.guiutility.frame.librarylist.do_or_schedule_refresh()
                if self.guiutility.frame.librarylist.IsShownOnScreen():
                    self.ClearButtonHandlers()
                    self.guiutility.SetBottomSplitterWindow(None)
            
            if self.guiutility.frame.librarylist.list.IsEmpty():
                self.guiutility.frame.librarylist.SetData([])
            
            if dlg.newName:
                if dlg.newName.IsChanged():
                    dlg2 = wx.MessageDialog(None, 'Do you want to save your changes made to this torrent?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                    if dlg2.ShowModal() == wx.ID_YES:
                        self.guiutility.channelsearch_manager.modifyTorrent(torrent.channel.id, torrent.channeltorrent_id, {'name':self.newName.GetValue()})
                    dlg2.Destroy()
            dlg.Destroy() 