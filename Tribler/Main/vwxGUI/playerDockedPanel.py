import wx
import wx.xrc as xrc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Video.VideoPlayer import VideoPlayer
from safeguiupdate import FlaglessDelayedInvocation
from Tribler.Main.vwxGUI.bgPanel import ImagePanel

DEBUG = False

class playerDockedPanel(wx.Panel, FlaglessDelayedInvocation):
    def __init__(self, *args, **kw):
        """
        PUT THE PLAYER HERE
        """
        
        self.initDone = False
        
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        FlaglessDelayedInvocation.__init__(self)
        self.guiUtility = GUIUtility.getInstance()

        self.triblerStyles = TriblerStyles.getInstance()
        self.videoplayer = VideoPlayer.getInstance()
        
        self.addComponents()


    def addComponents(self):
#        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.vSizer = wx.BoxSizer(wx.VERTICAL)        
        self.videoPreview = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(260,146),name='videoPreview')                               
        self.vSizer.Add(self.videoPreview, 0, wx.LEFT, 0)
        
        self.videoPreviewControls = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(260,16),name='videoPreviewControls')                               
        self.vSizer.Add(self.videoPreviewControls, 0, wx.LEFT, 0)

        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.Layout()
        self.Parent.Layout()
        self.GetParent().Layout()
        self.Refresh()

        

