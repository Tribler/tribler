# Written by Niels Zeilemaker

import wx.animate
from GuiUtility import GUIUtility
from Tribler.Main.Utility.utility import Utility
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler, NetworkBuzzDBHandler
from Tribler.Core.simpledefs import NTFY_TERM
from Tribler.Core.APIImplementation.miscutils import NamedTimer
from Tribler.Core.Session import Session

from bgPanel import bgPanel
from tribler_topButton import *
from traceback import print_exc

DEBUG = False

class TopSearchPanel(bgPanel):
    def __init__(self, parent, channelonly):
        if DEBUG:
            print >> sys.stderr , "TopSearchPanel: __init__"
        
        self.channelonly = channelonly
        self.loaded_bitmap = None
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility 
        self.installdir = self.utility.getPath()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.nbdb = NetworkBuzzDBHandler.getInstance()
         
        bgPanel.__init__(self, parent, 'top_search')
        
        if self.channelonly:
            self.selectTab('channels')
        else:
            self.selectTab('home')
        
    def OnAutoComplete(self):
        self.uelog.addEvent(message="TopSearchPanel: user used autocomplete", type = 2)  
    
    def OnSearchKeyDown(self, event = None):
        if self.go.IsEnabled():
            if DEBUG:
                print >> sys.stderr, "TopSearchPanel: OnSearchKeyDown"
            
            if getattr(self.searchField, 'ShowDropDown', False):
                self.searchField.ShowDropDown(False)
                
            self.guiUtility.dosearch()
            
            self.go.Enable(False)
            wx.CallLater(2500, self.go.Enable, True)
    
    def StartSearch(self):
        if not self.results.IsEnabled():
            self.results.Enable()
                  
        self.selectTab('search_results')
        self.results.SetValue(True)
        
        if getattr(self.searchField, 'ShowDropDown', False):
            self.searchField.ShowDropDown(False)
    
    def OnResults(self, event):
        self._selectPage('search_results')

    def OnChannels(self, event):
        self._selectPage('channels')
   
    def OnSettings(self, event):
        self._selectPage('settings')
    
    def OnHome(self, event):
        self._selectPage('home')
        
    def OnLibrary(self, event):
        self._selectPage('my_files')
    
    def OnStats(self, event):
        self._selectPage('stats')
        
    def NextPage(self):
        self._DoPage(1)
    def PrevPage(self):
        self._DoPage(-1)
        
    def _DoPage(self, increment):
        pages = [self.home.GetValue(), self.results.GetValue(), self.channels.GetValue(), self.settings.GetValue(), self.my_files.GetValue()]
        if not self.results.IsEnabled():
            pages.pop(1)
            
        curPage = 0
        for i in range(len(pages)):
            if pages[i]:
                curPage = i
                break
        
        curPage = (curPage + increment) % len(pages)
        if curPage < 0:
            curPage = len(pages) - 1
            
        if increment > 0:
            pageNames = ['home', 'search_results', 'channels', 'my_files', 'my_files']
        else:
            pageNames = ['home', 'search_results', 'channels', 'channels', 'my_files']
            
        if not self.results.IsEnabled():
            pageNames.remove('search_results')
        self._selectPage(pageNames[curPage])
    
    def _selectPage(self, page):
        if self.guiUtility.guiPage != page:
            self.guiUtility.ShowPage(page)
        
    def selectTab(self, tab):
        self.Freeze()
        
        if not self.channelonly:
            self.home.SetValue(tab == 'home')
            self.results.SetValue(tab == 'search_results')
            
        self.channels.SetValue(tab in ['channels', 'selectedchannel', 'mychannel'])
        self.settings.SetValue(tab == 'settings')
        self.my_files.SetValue(tab == 'my_files')
        
        
        if tab != 'settings': #if settings is clicked do nothing
            if not self.channelonly:
                self.searchSizer.ShowItems(tab != 'home')
                
            if tab != 'home': #if !home is clicked, show bitmap
                if not self.bitmap:
                    self.setBitmap(self.loaded_bitmap)
                    
            else: #if home is clicked, hide bitmap
                self.loaded_bitmap = self.bitmap
                self.setBitmap(None)
                self.SearchFocus()
        
        self.Layout()
        self.Thaw()
                
    def complete(self, term):
        """autocompletes term."""
        if len(term) > 1:
            return self.nbdb.getTermsStartingWith(term, num=7)
        return []

    def SearchFocus(self):
        if not self.channelonly:
            if self.home.GetValue():
                if getattr(self.parent, 'home', False):
                    self.parent.home.SearchFocus()
            else:
                self.searchField.SetFocus()
                self.searchField.SelectAll()

    def Bitmap(self, path, type):
        namelist = path.split("/")
        path = os.path.join(self.installdir, LIBRARYNAME, "Main", "vwxGUI", *namelist)
        return wx.Bitmap(path, type)
        
    def _PostInit(self):
        if DEBUG:
            print >> sys.stderr, "TopSearchPanel: OnCreate"
        
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        
        if not self.channelonly:
            if sys.platform == 'darwin':
                self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER)
                self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
            else:
                self.searchField = TextCtrlAutoComplete(self, entrycallback = self.complete, selectcallback = self.OnAutoComplete)
            self.searchField.SetMinSize((400, -1))
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)
            
            self.go = tribler_topButton(self,-1,name = 'Search_new')
            self.go.SetMinSize((50, 24))
            self.go.Bind(wx.EVT_LEFT_UP, self.OnSearchKeyDown)
        
        def createToggle(label, event):
            button = wx.ToggleButton(self, -1, label)
            button.Bind(wx.EVT_TOGGLEBUTTON, event)
            return button
        
        if not self.channelonly:
            self.channels = createToggle('Channels', self.OnChannels)
        else:
            self.channels = createToggle('Channel', self.OnChannels)
        self.settings = createToggle('Settings', self.OnSettings)
        self.my_files = createToggle('Library', self.OnLibrary)
        
        if not self.channelonly:
            self.results = createToggle('Results', self.OnResults)
            self.results.Disable()
        
            self.home = createToggle('Home', self.OnHome)
        
        if not self.channelonly:
            if sys.platform == 'win32':
                self.files_friends = wx.StaticBitmap(self, -1, self.Bitmap("images/search_files_channels.png", wx.BITMAP_TYPE_ANY))
                self.tribler_logo2 = wx.StaticBitmap(self, -1, self.Bitmap("images/logo4video2_win.png", wx.BITMAP_TYPE_ANY))
            else:
                self.files_friends = wx.StaticText(self, -1, "Search Files or Channels")
                self.tribler_logo2 = wx.StaticBitmap(self, -1, self.Bitmap("images/logo4video2.png", wx.BITMAP_TYPE_ANY))
                if sys.platform == 'linux2':
                    self.files_friends.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "Nimbus Sans L"))
                elif sys.platform == 'darwin': # mac
                    self.files_friends.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))
            
            self.tribler_logo2.Bind(wx.EVT_LEFT_UP, self.OnStats)
        
        
        self.notifyPanel = wx.Panel(self)
        self.notifyPanel.SetBackgroundColour("yellow")
        self.notifyIcon = wx.StaticBitmap(self.notifyPanel, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        self.notify = wx.StaticText(self.notifyPanel)
        
        notifyS = wx.BoxSizer(wx.HORIZONTAL)
        notifyS.Add(self.notifyIcon, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)
        notifyS.Add(self.notify, 1, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        self.notifyPanel.SetSizer(notifyS)
        self.notifyPanel.Hide()
        
        self.__do_layout()
        self.Layout()
        
        self.Bind(wx.EVT_SIZE, self.OnResize)
        
    def __do_layout(self):
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if not self.channelonly:
            #Add searchbox etc.
            self.searchSizer = wx.BoxSizer(wx.VERTICAL)
    
            #Search for files or channels label
            self.searchSizer.Add(self.files_friends, 0, wx.TOP, 20) 
            if sys.platform == 'win32': #platform specific spacer
                self.searchSizer.AddSpacer((0, 6))
            else:
                self.searchSizer.AddSpacer((0, 3))
            
            searchBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
            searchBoxSizer.Add(self.searchField, 1, wx.TOP|wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 1) #add searchbox
            searchBoxSizer.Add(self.go, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT |wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5) #add searchbutton
            self.searchSizer.Add(searchBoxSizer, 0, wx.EXPAND)
            
            #finished searchSizer, add to mainSizer
            mainSizer.Add(self.searchSizer, 0, wx.LEFT, 10)
        
            #niels: add strechingspacer, all controls added before 
            #this spacer will be aligned to the left of the screen
            #all controls added after, will be to the right
            mainSizer.AddStretchSpacer()
        
            #add buttons
            self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
            
            #add buttons horizontally
            buttonBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
            buttonBoxSizer.Add(self.home, 0, wx.RIGHT, 5)
            buttonBoxSizer.Add(self.results, 0, wx.RIGHT, 5)
            buttonBoxSizer.Add(self.channels, 0, wx.RIGHT, 5)
            buttonBoxSizer.Add(self.settings, 0, wx.RIGHT, 5)
            buttonBoxSizer.Add(self.my_files)
            
            self.buttonSizer.Add(buttonBoxSizer, 0, wx.TOP, 3)

            self.buttonSizer.Add(self.notifyPanel, 0, wx.ALIGN_RIGHT | wx.TOP, 5)
            mainSizer.Add(self.buttonSizer)
            
            mainSizer.AddSpacer((15, 0))
            
            mainSizer.Add(self.tribler_logo2, 0, wx.TOP, 3)
            mainSizer.AddSpacer((10, 0))
            
        else:
            self.buttonSizer = mainSizer
            mainSizer.AddStretchSpacer()
            
            mainSizer.Add(self.notifyPanel, 0, wx.ALL, 5)
            mainSizer.Add(self.channels, 0, wx.ALL, 5)
            mainSizer.Add(self.settings, 0, wx.ALL, 5)
            mainSizer.Add(self.my_files, 0, wx.ALL, 5)
        
        self.SetSizer(mainSizer)
    
    def OnResize(self, event):
        self.Refresh()
        event.Skip()
    
    def Notify(self, msg, icon= -1):
        self.notify.SetLabel(msg)
        self.notify.SetSize(self.notify.GetBestSize())
        
        if icon != -1:
            self.notifyIcon.Show()
            self.notifyIcon.SetBitmap(wx.ArtProvider.GetBitmap(icon, wx.ART_FRAME_ICON))
        else:
            self.notifyIcon.Hide()
        
        self.Freeze()
        self.notifyPanel.Show()
        #NotifyLabel size changed, thus call Layout
        self.buttonSizer.Layout()
        self.Thaw()
        
        wx.CallLater(5000, self.HideNotify)

    def HideNotify(self):
        self.notifyPanel.Hide()