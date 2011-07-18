import wx
import wx.animate
import os

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText
from Tribler import LIBRARYNAME

class SearchSideBar(wx.Panel):
    
    INDENT = 7
    def __init__(self, parent, size):
        wx.Panel.__init__(self, parent, size = size)
        self.guiutility =  GUIUtility.getInstance()
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.parent = parent
        
        self.nrfiltered = 0
        self.family_filter = True
        self.bundlestates = ['Name', 'Numbers', 'Size', 'Off']
        self.bundlestates_translation = ['Lev', 'Int', 'Size', None]
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        header = wx.StaticText(self, -1, 'Search progress')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        hSizer.Add(header, 1)
        
        ag_fname = os.path.join(self.guiutility.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        self.ag.UseBackgroundColour(True)
        self.ag.Hide()
        hSizer.Add(self.ag, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        self.vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.BOTTOM, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)        
        self.searchGauge = wx.Gauge(self, size = (-1, 7))
        hSizer.Add(self.searchGauge, 1)
        
        self.searchFinished = wx.StaticText(self, -1, '')
        hSizer.Add(self.searchFinished)
        self.vSizer.Add(hSizer, 0, wx.EXPAND)
        
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
        
        borderSizer = wx.BoxSizer()
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
        self.searchFinished.SetLabel('')
        
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
        self.searchFinished.SetLabel('Completed')
        self.Layout()
        
        self.Thaw()
        
    def SetAssociatedChannels(self, channels):
        wx.CallAfter(self._SetAssociatedChannels, channels)
    def _SetAssociatedChannels(self, channels):
        #channels should be a list, of occurrences, name, permid
        self.Freeze()
        
        nr = min(len(channels), 3)
        self.nochannels.Show(nr == 0)
        for i in range(nr):
            tooltip = "Click to go to %s's Channel."%channels[i][1]
            
            self.channels[i].SetLabel(channels[i][1])
            self.channels[i].SetToolTipString(tooltip)
            self.channels[i].channel_permid = channels[i][2]
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
        self.SetBundleState(0)
        self.SetFF(True)
        self.nochannels.Show()
        
        for channel in self.channels:
            channel.SetLabel('')
            channel.SetToolTipString('')
    
    def OnRebundle(self, event):
        #newstate = (self.bundlestate+1) % len(self.bundlestates)
        newstate = self.bundlestates.index(event.GetEventObject().GetLabel())
        self.SetBundleState(newstate)
        
    def SetBundleState(self, newstate):
        self.Freeze()
        
        self.bundlestatetext.SetLabel(' by %s' % self.bundlestates[newstate])
        self.torrentsearch_manager.setBundleMode(self.bundlestates_translation[newstate])
        
        self.bundleSizer.ShowItems(False)
        self.bundleSizer.Clear(deleteWindows = True)
        
        self.bundleSizer.Add(wx.StaticText(self, -1, 'Bundle by '))
        for i in range(len(self.bundlestates)):
            if newstate == i:
                self.bundleSizer.Add(wx.StaticText(self, -1, self.bundlestates[i]))
            else:
                link = LinkStaticText(self, self.bundlestates[i], None)
                link.Bind(wx.EVT_LEFT_UP, self.OnRebundle)
                self.bundleSizer.Add(link)
                
            if i+1 < len(self.bundlestates):
                self.bundleSizer.AddSpacer((1, -1))
        
        self.Layout()
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