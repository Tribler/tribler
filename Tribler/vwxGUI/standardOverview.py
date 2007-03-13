import wx, os, sys, os.path
import wx.xrc as xrc

TORRENT_MODE = 1
PERSON_MODE = 2

class standardOverview(wx.Panel):
    """
    Panel that shows one of the overview panels
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
        
        self.Layout()
        self.Refresh()
        
        
        
    def addComponents(self):
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.vSizer)
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        
    def refreshMode(self):
        # load xrc
        if self.mode == TORRENT_MODE:
            xrcResource = os.path.join('Tribler','vwxGUI', 'torrentOverview.xrc')
            panelName = 'torrentOverview'
        else:
            print 'Mode unknown'
            return
        self.res = xrc.XmlResource(xrcResource)
        # create panel
        self.panel = self.res.LoadPanel(self, panelName)
        self.vSizer.Add(self.panel, 1, wx.ALL, 0)
        