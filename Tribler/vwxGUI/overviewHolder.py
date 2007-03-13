import wx, os, sys
import wx.xrc as xrc

class overviewHolder(wx.Panel):
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
        self.refreshMode()
        
        self.Refresh(True)
        self.Update()
        
        
    def refreshMode(self):
        # load xrc
        if mode == TORRENT_MODE:
            xrcResource = 'torrentOverview.xrc'
            panelName = ''
        else:
            print 'Mode unknown'
            return
        self.res = xrc.XmlResource(xrcResource)
        # create panel
        self.panel = self.res.LoadPanel(self.GetParent(), panelName)
        