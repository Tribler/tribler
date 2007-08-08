import wx
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
        self.text = wx.StaticText(self, -1, 'hallo')
        self.hSizer.Add(self.text, 0, wx.ALL|wx.EXPAND, 3)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.SetMinSize((-1, 19))
        self.SetBackgroundColour(wx.RED)
        self.hSizer.Layout()
        self.Layout()
        self.searchBusy = True #??
        #self.Show(True)
        
    def setMessage(self, msg):
        self.text.SetLabel(msg)
        
    def stopSearch(self):
        # call remoteSearch and Web2.0 search to stop
        pass
    
    def findMoreSearch(self):
        # call remoteSearch and Web2.0 search to find more
        self.searchBusy = True
        self.stopMoreButton.setToggled(False)
        pass
    
    def searchFinished(self):
        self.searchBusy = False
        self.stopMoreButton.setToggled(True)
        
    
    def stopMoreClicked(self, event):
        if self.searchBusy:
            self.stopSearch()
            self.searchFinished()
        else: # find more
            self.findMoreSearch()
            