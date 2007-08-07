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
        self.clearButton = tribler_topButton(self, -1, wx.DefaultPosition, wx.DefaultSize, name='clearSearch')
        self.clearButton.Bind(wx.EVT_LEFT_UP, self.onMouseClick)
        self.hSizer.Add(self.clearButton, 0, wx.ALL, 3)
        self.text = wx.StaticText(self, -1, 'hallo')
        self.hSizer.Add(self.text, 0, wx.ALL|wx.EXPAND, 3)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.SetMinSize((-1, 50))
        self.hSizer.Layout()
        self.Layout()
        self.Refresh()
        self.Show(True)
        
    def setMessage(self, msg):
        self.text.SetLabel(msg)
        
    def onMouseClick(self, event=None):
        self.guiUtility.standardOverview.toggleSearchDetailsPanel(False)
        event.Skip()