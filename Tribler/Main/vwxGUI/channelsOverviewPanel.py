# Written by Richard Gwin

import wx
import wx.xrc as xrc
import random, sys, os
from time import time
import urllib
import cStringIO

class channelsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
        self.utility = None
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
        pass





 
