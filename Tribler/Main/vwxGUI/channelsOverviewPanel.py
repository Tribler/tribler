# Written by Richard Gwin

import wx
import wx.xrc as xrc
from wx.wizard import Wizard,WizardPageSimple,EVT_WIZARD_PAGE_CHANGED,EVT_WIZARD_PAGE_CHANGING,EVT_WIZARD_CANCEL,EVT_WIZARD_FINISHED
import random, sys, os
from time import time
from traceback import print_exc,print_stack
import urllib
import cStringIO
from Tribler.Core.CacheDB.sqlitecachedb import bin2str

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Core.simpledefs import *
from Tribler.Core.SessionConfig import SessionConfigInterface



class channelsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
        self.initDone = False
        self.elementsName = []
        self.elements = {}
        self.data = {} #data related to profile information, to be used in details panel
        self.mypref = None
        self.currentPortValue = None
 
        self.reload_counter = -1
        self.reload_cache = [None, None, None]
        
        # SELDOM cache
        self.bartercast_db = None
        self.barterup = 0
        self.barterdown = 0

        self.myTorrentList = None
        self.utility = None
        self.myChannelName = None
        self.num_votes = None
        
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


    def myChannelClicked(self, event):
        self.channelsDetails.loadChannel(self, self.myTorrentList, self.utility.session.get_permid(), self.myChannelName, False)


    def setTorrentList(self , torrentlist):
        self.myTorrentList = torrentlist

    def isMyChannel(self):
        return True


    def setMyChannelInfo(self):
        # get torrent list
        torrentList = self.channelcast_db.getTorrentsFromPublisherId(bin2str(self.utility.session.get_permid()))
        self.torrentList = torrentList

        # convert torrentList to proper format (dictionnary)
        torrent_list = []
        for item in self.torrentList:
            torrent = dict(zip(self.torrent_db.value_name_for_channel, item))
            torrent_list.append(torrent)
        self.myTorrentList = torrent_list

        self.num_votes = self.channelcast_db.getSubscribersCount(bin2str(self.utility.session.get_permid()))

        if self.num_votes == 0:
            self.myChannelName = "My Channel (No subscribers)"
        elif self.num_votes == 1:
            self.myChannelName = "My Channel (1 subscriber)" 
        else:
            self.myChannelName = "My Channel (%s subscribers)" % self.num_votes 






 
