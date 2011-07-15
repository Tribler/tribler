import wx
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText

class SearchSideBar(wx.Panel):
    def __init__(self, parent, size):
        wx.Panel.__init__(self, parent, size = size)
        self.torrentsearch_manager = GUIUtility.getInstance().torrentsearch_manager
        self.parent = parent
        
        self.nrfiltered = 0
        self.family_filter = True
        self.bundlestates = ['Name', 'Size', 'Numbers', 'Off']
        self.bundlestates_translation = ['Lev', 'Size', 'Int', None]
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
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
        self.vSizer.Add(self.ffblocked, 0, wx.EXPAND|wx.LEFT, 7)
        
        self.ffbutton = LinkStaticText(self, '', None)
        self.ffbutton.Bind(wx.EVT_LEFT_UP, self.toggleFamilyFilter)
        self.vSizer.Add(self.ffbutton, 0, wx.EXPAND|wx.LEFT, 7)
        
        self.vSizer.AddSpacer((-1,20))
        
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
        self.vSizer.Add(self.bundleSizer, 0, wx.EXPAND|wx.LEFT, 7)
        
        borderSizer = wx.BoxSizer()
        borderSizer.Add(self.vSizer, 1, wx.EXPAND|wx.ALL, 7)

        self.SetSizer(borderSizer)
        self.SetMinSize((self.GetBestSize()[0], -1))
        
        self.Reset()
        
    def SetFF(self, family_filter):
        self.family_filter = family_filter
        self._SetLabels()
    
    def SetFiltered(self, nr):
        self.nrfiltered = nr
        self._SetLabels()
    
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
                self.vSizer.Insert(2, self.ffblocked, 0, wx.EXPAND|wx.LEFT, 7)
            else:
                self.ffblocked.SetLabel('')
                self.vSizer.Detach(self.ffblocked)
                self.vSizer.Insert(3, self.ffblocked)
                
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
    
    def SetBackgroundColour(self, colour):
        wx.Panel.SetBackgroundColour(self, colour)
        
        self.ffbutton.SetBackgroundColour(colour)
        for sizeritem in self.bundleSizer.GetChildren():
            if sizeritem.IsWindow():
                child = sizeritem.GetWindow()
                if isinstance(child, wx.Panel):
                    child.SetBackgroundColour(colour)