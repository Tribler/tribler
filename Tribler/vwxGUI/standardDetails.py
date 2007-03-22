import wx, os, sys
import wx.xrc as xrc
from Tribler.vwxGUI.GuiUtility import GUIUtility

TORRENT_MODE = 1
PERSONS_MODE = 2

class standardDetails(wx.Panel):
    """
    Panel that shows one of the detail panels
    """
    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.mode = TORRENT_MODE
        self.addComponents()
        self.refreshMode()
        self.guiUtility = GUIUtility.getInstance()
        self.data = None
        self.Layout()
        self.Refresh()
        self.guiUtility.report(self)
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1);
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1);
        
    def refreshMode(self):
        # load xrc
        if self.mode == TORRENT_MODE:
            xrcResource = os.path.join('Tribler','vwxGUI', 'torrentDetails.xrc')
            panelName = 'torrentDetails'
        else:
            print 'Mode unknown'
            return
        self.res = xrc.XmlResource(xrcResource)
        # create panel
        self.panel = self.res.LoadPanel(self, panelName)
        
        #self.hSizer.Add(self.vSizer, 1, wx.ALL|wx.EXPAND, 0)
        self.vSizer.Add(self.panel, 1, wx.ALL|wx.EXPAND, 0)
        #self.hSizer.vSizer.Add(self.panel, 1, wx.All|wx.EXPAND|wx.STRETCH, 0)
    
    def setData(self, data):
        pass
