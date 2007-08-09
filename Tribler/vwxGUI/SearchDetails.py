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
        self.clearButton = tribler_topButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchClear')
        self.stopMoreButton = SwitchButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='searchStop')
        self.stopMoreButton.Bind(wx.EVT_LEFT_UP, self.stopMoreClicked)
        self.hSizer.Add(self.clearButton, 0, wx.ALL, 1)
        self.hSizer.Add(self.stopMoreButton, 0, wx.ALL, 1)
        self.textPanel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.text = wx.StaticText(self.textPanel, -1, 'hallo')
        sizer.Add(self.text, 1, wx.ALL, 0)
        self.textPanel.SetSizer(sizer)
        self.textPanel.SetAutoLayout(1)
        self.textPanel.SetBackgroundColour(wx.WHITE)
        
        self.text.SetSize((-1, 15))
        self.hSizer.Add(self.textPanel, 1, wx.LEFT|wx.EXPAND, 10)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.SetMinSize((-1, 19))
        self.SetBackgroundColour(wx.WHITE)
        self.hSizer.Layout()
        self.Layout()
        self.searchBusy = True #??
        #self.Show(True)
        self.results = {}
        
    def setMessage(self, type, finished, num):
        self.results[type] = num
        total = sum(self.results.values())
        if not total:
            msg = self.guiUtility.utility.lang.get('start_search')
        elif not finished:
            msg = self.guiUtility.utility.lang.get('going_search') % sum(self.results.values())
        else:
            msg = self.guiUtility.utility.lang.get('finished_search') % sum(self.results.values())
        self.text.SetLabel(msg)
        tt = ''
        items = self.results.items()
        items.sort()
        for pair in items:
            key, value = pair
            tt += self.guiUtility.utility.lang.get('search_'+key) % value
            if items.index(pair) != len(items)-1:
                tt +=os.linesep
        self.textPanel.SetToolTipString(tt)
        self.text.SetToolTipString(tt)
        
    def stopSearch(self):
        # call remoteSearch and Web2.0 search to stop
        dod = self.guiUtility.standardOverview.getGrid().dod
        if dod:
            dod.stop()
    
    def findMoreSearch(self):
        # call remoteSearch and Web2.0 search to find more
        self.searchBusy = True
        self.stopMoreButton.setToggled(False)
        grid = self.guiUtility.standardOverview.getGrid()
        if grid.dod:
            grid.dod.requestMore(grid.items)
    
    def searchFinished(self):
        self.searchBusy = False
        self.stopMoreButton.setToggled(True)
        
    
    def stopMoreClicked(self, event):
        if self.searchBusy:
            self.stopSearch()
            self.searchFinished()
        else: # find more
            self.findMoreSearch()
            