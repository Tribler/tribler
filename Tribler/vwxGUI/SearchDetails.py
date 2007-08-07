import wx
from Tribler.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton

class SearchDetailsPanel(wx.Panel):
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        self.addComponents()
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.clearButton = tribler_topButton(self, name='clearSearch', size=wx.Size(100,50))
        self.hSizer.Add(self.clearButton, 0, wx.ALL, 3)
        self.text = wx.StaticText(self, -1, 'hallo')
        self.hSizer.Add(self.text, 0, wx.ALL|wx.EXPAND, 3)
        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        #self.SetMinSize((200, 50))
        self.hSizer.Layout()
        self.Layout()
        self.Refresh()
        self.Show(True)