# Written by Richard Gwin

import wx
import wx.xrc as xrc
import random, sys, os
from time import time
import urllib
import cStringIO

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton



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
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility

#        self.standardOverview = self.guiUtility.standardOverview
#        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
#        self.channelcast_db = self.utility.session.open_dbhandler(NTFY_CHANNELCAST)
#        self.torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
#        self.vcdb = self.utility.session.open_dbhandler(NTFY_VOTECAST)
#        self.channelsDetails = self.guiUtility.frame.channelsDetails
#        self.setMyChannelInfo()

    def setTorrentList(self , torrentlist):
        self.myTorrentList = torrentlist

    def isMyChannel(self):
        return True






 
