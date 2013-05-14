# Written by Niels Zeilemaker
import os
import sys
import wx.adv

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler, NetworkBuzzDBHandler

from widgets import ActionButton, FancyPanel, TextCtrlAutoComplete, ProgressButton
from Tribler.Main.vwxGUI import forceWxThread, TRIBLER_RED, SEPARATOR_GREY, GRADIENT_LGREY, GRADIENT_DGREY
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

class TopSearchPanel(FancyPanel):
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

        FancyPanel.__init__(self, parent, border = wx.BOTTOM)
        self.SetBorderColour(SEPARATOR_GREY)
        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.AddComponents()
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
    def AddComponents(self):
        self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        
        if DEBUG:
            print >> sys.stderr, "TopSearchPanel: OnCreate"
        
        if sys.platform == 'darwin':
            self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER | wx.NO_BORDER )
            self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)
            self.searchField.SetDescriptiveText('Search Files or Channels')
            self.searchField.SetMinSize((400, 20))
        else:
            self.searchFieldPanel = FancyPanel(self, radius = 5, border = wx.ALL)        
            self.searchFieldPanel.SetBorderColour(SEPARATOR_GREY, highlight = TRIBLER_RED)  
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
        self.ag = wx.adv.AnimationCtrl(self, -1)
        self.ag.LoadFile(ag_fname)
        self.ag.SetBackgroundColour(wx.Colour(244,244,244))
        self.ag.Hide()

        download_bmp = self.Bitmap("images/download.png", wx.BITMAP_TYPE_ANY)
        self.download_btn = ActionButton(self, -1, download_bmp)
        self.download_btn.Enable(False)
        upload_bmp = self.Bitmap("images/upload.png", wx.BITMAP_TYPE_ANY)
        self.upload_btn = ActionButton(self, -1, upload_bmp)
        self.upload_btn.Enable(False)
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
        mainSizer.Add(40,0,0)

        #add buttons
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(self.download_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(self.upload_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(self.stop_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(self.delete_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(self.play_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(35,0,0)
        buttonSizer.AddStretchSpacer()
        buttonSizer.Add(self.add_btn, 0, wx.CENTER|wx.RIGHT, 5)
        buttonSizer.Add(self.settings_btn, 0, wx.CENTER|wx.RIGHT, 5)
        mainSizer.Add(buttonSizer, 1, wx.EXPAND)

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
            isMultiple = len(torrents) > 1
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
            
            enableDownload = states[1] + states[2]
            if enableDownload:
                if isMultiple:
                    self.SetButtonHandler(self.download_btn, self.OnDownload, 'Resume downloading %d torrent(s).' % enableDownload)
                elif states[1]:
                    self.SetButtonHandler(self.download_btn, self.OnResume, 'Resume downloading this torrent.')
                else:
                    self.SetButtonHandler(self.download_btn, self.OnDownload, 'Start downloading this torrent.')
            else:
                self.SetButtonHandler(self.download_btn, None)
                    
            enableUpload = states[0]
            if enableUpload:
                if isMultiple:
                    self.SetButtonHandler(self.upload_btn, self.OnUpload, 'Resume seeding %d torrent(s).' % enableUpload)
                else:
                    self.SetButtonHandler(self.upload_btn, self.OnUpload, 'Resume seeding this torrent.')
            else:
                self.SetButtonHandler(self.upload_btn, None)
            
            enableStop = states[3] + states[4]
            if enableStop:
                if isMultiple:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop %d torrent(s).' % enableStop)
                elif states[3]:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop seeding this torrent.')
                else:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop downloading this torrent.')
            else:
                self.SetButtonHandler(self.stop_btn, None)
            
            if states[5] > 1:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete %d torrent(s).' % states[5])
            elif states[5]:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete this torrent.')
            else:
                self.SetButtonHandler(self.delete_btn, None)
            
            if isMultiple:
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
        self.SetButtonHandler(self.upload_btn, None)
        self.SetButtonHandler(self.play_btn, None)
        self.SetButtonHandler(self.stop_btn, None)
        self.SetButtonHandler(self.delete_btn, None)
    
    def OnDownload(self, event = None, torrents = None):
        refresh_library = False
        torrents = torrents if torrents != None else self.__getTorrents() 
        for torrent in torrents:
            if 'stopped' in torrent.state:
                self.guiutility.library_manager.resumeTorrent(torrent)
            else:
                if self.guiutility.frame.selectedchannellist.IsShownOnScreen():
                    self.guiutility.frame.selectedchannellist.StartDownload(torrent, None)
                else:
                    self.guiutility.frame.searchlist.StartDownload(torrent, None)

                refresh_library = True
                
        if event:
            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(3000, button.Enable, True)
            
        if refresh_library:
            wx.CallLater(1000, self.guiutility.frame.librarylist.do_or_schedule_refresh, True)
            
    def OnUpload(self, event):
        for torrent in self.__getTorrents():
            if 'completed' in torrent.state:
                self.guiutility.library_manager.resumeTorrent(torrent)
        if event:
            button = event.GetEventObject()
            button.Enable(False)

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

    def OnResume(self, event = None):
        for torrent in self.__getTorrents():
            self.guiutility.library_manager.resumeTorrent(torrent)
        if event:
            button = event.GetEventObject()        
            button.Enable(False)
    
    def OnStop(self, event = None):
        for torrent in self.__getTorrents():
            self.guiutility.library_manager.stopTorrent(torrent)
        if event:
            button = event.GetEventObject()
            button.Enable(False)
    
    def OnDelete(self, event = None, silent = False):
        for torrent in self.__getTorrents():
            if not silent:
                dlg = RemoveTorrent(None, torrent)
                buttonId = dlg.ShowModal()
            else:
                buttonId = wx.ID_DELETE
                
            if buttonId in [wx.ID_DEFAULT, wx.ID_DELETE]:
                self.guiutility.library_manager.deleteTorrent(torrent, buttonId == wx.ID_DELETE)
                self.guiutility.frame.librarylist.RemoveItem(torrent.infohash)
                self.guiutility.frame.librarylist.GetManager().refresh()
                if self.guiutility.frame.librarylist.IsShownOnScreen():
                    self.ClearButtonHandlers()
                    self.guiutility.frame.librarylist.ResetBottomWindow()
            
            if self.guiutility.frame.librarylist.list.IsEmpty():
                self.guiutility.frame.librarylist.SetData([])
            
            if not silent:
                if dlg.newName:
                    if dlg.newName.IsChanged():
                        dlg2 = wx.MessageDialog(None, 'Do you want to save your changes made to this torrent?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                        if dlg2.ShowModal() == wx.ID_YES:
                            self.guiutility.channelsearch_manager.modifyTorrent(torrent.channel.id, torrent.channeltorrent_id, {'name':self.newName.GetValue()})
                        dlg2.Destroy()
                dlg.Destroy()
