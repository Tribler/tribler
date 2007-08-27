import wx, os
from Tribler.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.vwxGUI.GuiUtility import GUIUtility

class SearchDetailsPanel(wx.Panel):
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        
        self.addComponents()
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        #(self, -1, wx.DefaultPosition, wx.Size(16,16),name='down')
        self.stopMoreButton = SwitchButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchStop')
        self.stopMoreButton.Bind(wx.EVT_LEFT_UP, self.stopMoreClicked)
        self.stopMoreButton.SetToolTipString(self.guiUtility.utility.lang.get('searchStop'))        
        self.clearButton = tribler_topButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchClear')        
        self.clearButton.SetToolTipString(self.guiUtility.utility.lang.get('searchClear'))
        self.hSizer.Add([9,5],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.hSizer.Add(self.stopMoreButton, 0, wx.ALL, 1)
        self.hSizer.Add(self.clearButton, 0, wx.ALL, 1)
        
        self.hSizer.Add([8,5],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.textPanel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.text = wx.StaticText(self.textPanel, -1, '')
        self.text.SetForegroundColour(wx.Colour(255,255,255))
        sizer.Add(self.text, 1, wx.ALL, 0)
        self.textPanel.SetSizer(sizer)
        self.textPanel.SetAutoLayout(1)
        self.textPanel.SetForegroundColour(wx.WHITE)        
        self.textPanel.SetBackgroundColour(wx.Colour(53,53,53))
        
        self.text.SetSize((-1, 15))
        self.hSizer.Add(self.textPanel, 1, wx.TOP|wx.EXPAND, 3)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.SetMinSize((-1, 19))
        self.SetBackgroundColour(wx.Colour(53,53,53))
        self.hSizer.Layout()
        self.Layout()
        self.searchBusy = True #??
        #self.Show(True)
        self.results = {}
        
    def setMessage(self, type, finished, num, keywords = []):
        if type:
            self.results[type] = num
        
        total = sum([v for v in self.results.values() if v != -1])
        
        if keywords:
            self.keywords = " ".join(keywords)
          
        if finished:  
            msg = self.guiUtility.utility.lang.get('finished_search') % (self.keywords, total)
            self.stopMoreClicked()
        else:
            msg = self.guiUtility.utility.lang.get('going_search') % (self.keywords, total)
        
            
        self.text.SetLabel(msg)
        tt = []
        
        for pair in self.results.items():
            key, value = pair
            if value == -1:
                continue
            tt.append(self.guiUtility.utility.lang.get('search_'+key) % value)
            
        tt.sort()
        tt = os.linesep.join(tt)
        self.textPanel.SetToolTipString(tt)
        self.text.SetToolTipString(tt)
        
    def startSearch(self):
        self.stopMoreButton.setToggled(False)
        self.searchBusy = True
        
    def stopSearch(self):
        # call remoteSearch and Web2.0 search to stop
        dod = self.guiUtility.standardOverview.getGrid().dod
        if dod:
            dod.stop()
    
    def findMoreSearch(self):
        # call remoteSearch and Web2.0 search to find more
        self.startSearch()
        grid = self.guiUtility.standardOverview.getGrid()
        if grid.dod:
            grid.dod.requestMore(grid.items)
    
    def searchFinished(self):
        self.searchBusy = False
        self.stopMoreButton.setToggled(True)
        self.setMessage(None, True, 0, None)
    
    def stopMoreClicked(self, event = None):
        if event:
            event.Skip()
        if self.searchBusy:
            self.stopSearch()
            self.searchFinished()
        #else: # find more
        #    self.findMoreSearch()
            