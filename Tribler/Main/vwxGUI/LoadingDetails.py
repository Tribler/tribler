import wx, os
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

class LoadingDetailsPanel(wx.Panel):
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        
        self.addComponents()
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)

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
        
    def setMessage(self,msg):
        self.text.SetLabel(msg)
        
            