import wx
import wx.animate
import os

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText
from Tribler.Core.Search.Bundler import Bundler
from Tribler import LIBRARYNAME
from Tribler.Core.CacheDB.SqliteCacheDBHandler import BundlerPreferenceDBHandler,\
    UserEventLogDBHandler

class SearchSideBar(wx.Panel):
    
    INDENT = 7
    
    def __init__(self, parent, size):
        wx.Panel.__init__(self, parent, size = size)
        self.guiutility =  GUIUtility.getInstance()
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.parent = parent
        
        self.nrfiltered = 0
        self.family_filter = True
        self.bundlestates = [Bundler.ALG_MAGIC, Bundler.ALG_NAME, Bundler.ALG_NUMBERS, Bundler.ALG_SIZE, Bundler.ALG_OFF]
        self.bundlestates_str = {Bundler.ALG_NAME: 'Name',
                                 Bundler.ALG_NUMBERS: 'Numbers',
                                 Bundler.ALG_SIZE: 'Size',
                                 Bundler.ALG_MAGIC: 'Magic',
                                 Bundler.ALG_OFF: 'Off'}
        self.bundletexts = []
        self.bundle_db = BundlerPreferenceDBHandler.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        header = wx.StaticText(self, -1, 'Search')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        hSizer.Add(header, 0, wx.ALIGN_CENTER_VERTICAL)
        
        self.searchState = wx.StaticText(self)
        hSizer.Add(self.searchState, 1, wx.ALIGN_CENTER_VERTICAL)
        
        ag_fname = os.path.join(self.guiutility.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        self.ag.UseBackgroundColour(True)
        self.ag.Hide()
        hSizer.Add(self.ag, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        
        self.vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        self.vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.BOTTOM, 3)

        self.searchGauge = wx.Gauge(self, size = (-1, 7))
        self.vSizer.Add(self.searchGauge, 0, wx.EXPAND|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        
        self.vSizer.AddSpacer((-1,15))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        header = wx.StaticText(self, -1, 'Family Filter')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        hSizer.Add(header)
        
        self.ffstate = wx.StaticText(self)
        hSizer.Add(self.ffstate)
        self.vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        self.vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.BOTTOM, 3)
        
        self.ffblocked = wx.StaticText(self)
        self.vSizer.Add(self.ffblocked, 0, wx.EXPAND|wx.LEFT, SearchSideBar.INDENT)
        
        self.ffbutton = LinkStaticText(self, '', None)
        self.ffbutton.Bind(wx.EVT_LEFT_UP, self.toggleFamilyFilter)
        self.vSizer.Add(self.ffbutton, 0, wx.EXPAND|wx.LEFT, SearchSideBar.INDENT)
        
        self.vSizer.AddSpacer((-1,15))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        header = wx.StaticText(self, -1, 'Bundling')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        hSizer.Add(header)
        
        #keep longest text in bundlestatetext, to define bestsize (width) for sidepanel
        self.bundlestatetext = wx.StaticText(self, -1, ' by Numbers')
        hSizer.Add(self.bundlestatetext)
        self.vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        self.vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.BOTTOM, 3)
            
        self.bundleSizer = wx.FlexGridSizer(0, 2, 0, 0)
        self.vSizer.Add(self.bundleSizer, 0, wx.EXPAND|wx.LEFT, SearchSideBar.INDENT)
        
        self.vSizer.AddSpacer((-1,15))
        
        header = wx.StaticText(self, -1, 'Associated Channels')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        self.vSizer.Add(header, 0, wx.EXPAND|wx.BOTTOM, 3)
        self.vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.BOTTOM, 3)
        
        self.nochannels = wx.StaticText(self, -1, 'None')
        self.vSizer.Add(self.nochannels, 0, wx.EXPAND|wx.LEFT, SearchSideBar.INDENT)
        
        self.channels = [LinkStaticText(self, '', icon = None) for _ in range(3)]
        for channel in self.channels:
            self.vSizer.Add(channel, 0, wx.EXPAND|wx.LEFT, SearchSideBar.INDENT)
            channel.Bind(wx.EVT_LEFT_UP, self.OnChannel)
        
        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.AddSpacer((-1, 3))
        borderSizer.Add(self.vSizer, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)

        self.SetSizer(borderSizer)
        self.SetMinSize((self.GetBestSize()[0], -1))
        
        self.Reset()
        
    def SetFF(self, family_filter):
        self.family_filter = family_filter
        self._SetLabels()
    
    def SetFiltered(self, nr):
        self.nrfiltered = nr
        self._SetLabels()
        
    def SetMaxResults(self, max):
        wx.CallAfter(self._SetMaxResults, max)
    def _SetMaxResults(self, max):
        self.Freeze()
        
        self.searchGauge.SetRange(max)
        self.searchGauge.SetValue(0)
        self.searchGauge.Show()
        self.searchState.SetLabel(' in progress')
        
        wx.CallLater(10000, self.SetFinished)
        
        self.ag.Play()
        self.ag.Show()
        
        self.Thaw()
        
    def NewResult(self):
        wx.CallAfter(self._NewResult)
    def _NewResult(self):
        maxValue = self.searchGauge.GetRange()
        newValue = min(self.searchGauge.GetValue() + 1, maxValue)
        if newValue == maxValue:
            self.SetFinished()
        else:
            self.searchGauge.SetValue(newValue)
        
    def SetFinished(self):
        self.Freeze()
        
        self.ag.Stop()
        self.ag.Hide()
        self.searchGauge.Hide()
        self.searchState.SetLabel(' completed')
        self.Layout()
        
        self.Thaw()
        
    def SetAssociatedChannels(self, channels):
        wx.CallAfter(self._SetAssociatedChannels, channels)
    def _SetAssociatedChannels(self, channels):
        #channels should be a list, of occurrences, name, permid
        self.Freeze()
        
        self.nochannels.Show(len(self.channels) == 0)
        for i in range(len(self.channels)):
            if i < len(channels):
                tooltip = "Click to go to %s's Channel."%channels[i][1]
                
                self.channels[i].SetLabel(channels[i][1])
                self.channels[i].SetToolTipString(tooltip)
                self.channels[i].channel_permid = channels[i][2]
            else:
                self.channels[i].SetLabel('')
                self.channels[i].SetToolTipString('')
        self.Layout()
        self.Thaw()
    
    def toggleFamilyFilter(self, event):
        self.parent.toggleFamilyFilter()
        
    def _SetLabels(self):
        self.Freeze()
        if self.family_filter:
            if self.nrfiltered > 0:
                if self.nrfiltered > 1:
                    self.ffblocked.SetLabel('%d results blocked'%self.nrfiltered)
                else:
                    self.ffblocked.SetLabel('1 result blocked')
                
                self.vSizer.Detach(self.ffblocked)
                self.vSizer.Insert(6, self.ffblocked, 0, wx.EXPAND|wx.LEFT, 7)
            else:
                self.ffblocked.SetLabel('')
                self.vSizer.Detach(self.ffblocked)
                self.vSizer.Insert(7, self.ffblocked)
                
            self.ffstate.SetLabel(' is On')
            self.ffbutton.SetLabel('turn off')
        else:
            self.ffstate.SetLabel(' is Off')
            self.ffbutton.SetLabel('turn on')
        self.Layout()
        self.Thaw()
    
    def Reset(self):
        self.SetBundleState(None)
        self.SetFF(True)
        self.nochannels.Show()
        
        for channel in self.channels:
            channel.SetLabel('')
            channel.SetToolTipString('')
    
    def OnRebundle(self, event):
        curstate = self.bundlestate
        selectedByMagic = -1
        for i, text in enumerate(self.bundletexts):
            if isinstance(text, LinkStaticText) and text.IsIconShown():
                selectedByMagic = self.bundlestates[i]
                break
        
        newstate = event.GetEventObject().action
        self.SetBundleState(newstate)
        
        def db_callback():
            keywords = self.torrentsearch_manager.getSearchKeywords()[0]
            self.bundle_db.storePreference(keywords, newstate)
            query = ' '.join(keywords)
            
            selectedByMagicStr = ''
            if selectedByMagic != -1:
                selectedByMagicStr = self.bundlestates_str[selectedByMagic]
            
            self.uelog.addEvent(message="Bundler GUI: %s -> %s; %s -> %s; selectedByMagic %s (%s); q=%s" 
                                % (curstate, newstate, self.bundlestates_str[curstate], 
                                   self.bundlestates_str[newstate],
                                   selectedByMagic, selectedByMagicStr, query), type = 3)
        
        self.guiutility.frame.guiserver.add_task(db_callback)
        
    def SetBundleState(self, newstate):
        if newstate is None:
            auto_guess = self.guiutility.utility.config.Read('use_bundle_magic', "boolean")
            
            keywords = self.torrentsearch_manager.getSearchKeywords()[0]
            stored_state = self.bundle_db.getPreference(keywords)
            local_override = stored_state is not None
            
            if local_override:
                newstate = stored_state
                
            elif auto_guess:
                newstate = Bundler.ALG_MAGIC
            
            else:
                newstate = Bundler.ALG_OFF # default
        
        self.bundlestate = newstate
        self.Freeze()
        
        if newstate != Bundler.ALG_OFF:
            self.bundlestatetext.SetLabel(' by %s' % self.bundlestates_str[newstate])
        else:
            self.bundlestatetext.SetLabel(' is %s' % self.bundlestates_str[newstate])
        self.torrentsearch_manager.setBundleMode(newstate)
        
        self.bundleSizer.ShowItems(False)
        self.bundleSizer.Clear(deleteWindows = True)
        self.bundletexts = []
        self.bundleSizer.Add(wx.StaticText(self, -1, 'Bundle by '))
        for i, state in enumerate(self.bundlestates):
            if newstate == state:
                text = wx.StaticText(self, -1, self.bundlestates_str[state])
                self.bundleSizer.Add(text)
                self.bundletexts.append(text)
            else:
                link = LinkStaticText(self, self.bundlestates_str[state], "wand.png")
                link.ShowIcon(False)
                link.SetIconToolTipString('Selected by Magic')
                link.Bind(wx.EVT_LEFT_UP, self.OnRebundle)
                link.action = state
                self.bundleSizer.Add(link)
                self.bundletexts.append(link)
                
            if i+1 < len(self.bundlestates):
                self.bundleSizer.AddSpacer((1, -1))
        
        self.Layout()
        self.Thaw()
    
    def SetSelectedBundleMode(self, selected_bundle_mode):
        if self.bundlestate == Bundler.ALG_MAGIC:
            self.Freeze()
            
            index = self.bundlestates.index(selected_bundle_mode)
            for i in range(len(self.bundletexts)):
                linkStaticText = self.bundletexts[i]
                if isinstance(linkStaticText, LinkStaticText):
                    if i == index: 
                        if not linkStaticText.IsIconShown():
                            linkStaticText.ShowIcon(True)
                            wx.CallAfter(linkStaticText.Blink)
                    else:
                        linkStaticText.ShowIcon(False)
            self.Thaw()
    
    def OnChannel(self, event):
        label = event.GetEventObject()
        channel_name = label.GetLabel()
        channel_permid = label.channel_permid
        
        if channel_name != '':
            self.guiutility.showChannel(channel_name, channel_permid)
    
    def SetBackgroundColour(self, colour):
        wx.Panel.SetBackgroundColour(self, colour)
        
        self.ffbutton.SetBackgroundColour(colour)
        self.ag.SetBackgroundColour(colour)
        
        for channel in self.channels:
            channel.SetBackgroundColour(colour)
        
        for sizeritem in self.bundleSizer.GetChildren():
            if sizeritem.IsWindow():
                child = sizeritem.GetWindow()
                if isinstance(child, wx.Panel):
                    child.SetBackgroundColour(colour)