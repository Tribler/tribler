import wx, os, sys, os.path
import wx.xrc as xrc
from Tribler.vwxGUI.GuiUtility import GUIUtility

OVERVIEW_MODES = ['filesMode', 'personsMode', 'profileMode', 'friendsMode', 'subscriptionMode', 'messageMode']

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
        self.guiUtility = GUIUtility.getInstance()
        self.mode = OVERVIEW_MODES[0]
        self.data = {}
        for mode in OVERVIEW_MODES:
            self.data[mode] = {}
        self.addComponents()
        self.currentPanel = None
        self.panels={}
        self.refreshMode()
        self.Refresh()
        self.guiUtility.report(self)
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        
    def setMode(self, mode, datalist):
        if self.mode != mode:
            self.mode = mode
            self.data[self.mode]['list'] = datalist
            self.refreshMode()
            self.data[self.mode]['grid'].setData(datalist)
            
    def refreshMode(self):
        # load xrc
        self.oldpanel = self.currentPanel
        self.Show(False)
        self.currentPanel = self.panels.get(self.mode)
        if not self.currentPanel:
            if self.mode == 'filesMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'filesOverview.xrc')
                panelName = 'filesOverview'
            elif self.mode == 'personsMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'personsOverview.xrc')
                panelName = 'personsOverview'
            elif self.mode == 'profileMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'profileOverview.xrc')
                panelName = 'profileOverview'
            elif self.mode == 'libraryMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'libraryOverview.xrc')
                panelName = 'libraryOverview'
            elif self.mode == 'friendsMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'friendsOverview.xrc')
                panelName = 'friendsOverview'
            elif self.mode == 'messagesMode':
                xrcResource = os.path.join('Tribler','vwxGUI', 'messagesOverview.xrc')
                panelName = 'messagesOverview'                                                   
            else:
                print 'Mode unknown'
                return
            self.res = xrc.XmlResource(xrcResource)
            # create panel
            self.currentPanel = self.panels[self.mode] = self.res.LoadPanel(self, panelName)
            
            self.data[self.mode]['grid'] = xrc.XRCCTRL(self.currentPanel, self.mode[:-4]+'Grid')
        
     
        self.currentPanel.GetSizer().Layout()
        self.currentPanel.Enable(True)
        self.currentPanel.Show(True)
        
        if self.oldpanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            self.oldpanel.Disable()
        
        self.hSizer.Add(self.currentPanel, 1, wx.ALL|wx.EXPAND, 0)
        
        #self.guiUtility.mainSizer.Layout()
        self.hSizer.Layout()
        self.currentPanel.Refresh()
        self.Show(True)
        
        
    
        
        