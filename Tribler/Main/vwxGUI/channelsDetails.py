# Written by Richard Gwin 

import wx
import wx.xrc as xrc
from binascii import hexlify
from time import sleep,time
import math
from traceback import print_exc, print_stack
import cStringIO
import urlparse
from wx.lib.stattext import GenStaticText as StaticText

import threading
import os, sys


from font import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

from Tribler.Video.VideoPlayer import VideoPlayer

from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import *

from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.channelsDetailsItem import channelsDetailsItem
from Tribler.Main.vwxGUI.tribler_topButton import *

from Tribler.Subscriptions.rss_client import TorrentFeedThread

from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Core.BuddyCast.channelcast import ChannelCastCore
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename

from Tribler.__init__ import LIBRARYNAME

DETAILS_MODES = ['filesMode',  'libraryMode', 'channelsMode']

DEBUG = False


# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 14
    FS_ITEM = 12
    FS_REMOVE_TEXT = 11
    FS_RSS = 12
    FS_RSS_TEXT = 11
    FS_RSSFEEDBACK_TEXT = 11
    FS_CONTAIN_TEXT = 10
    FS_UPDATE_TEXT = 10
    FS_FILETITLE_SEL = 14 # size of title in expanded torrent
    FS_MAX_SUBSCRIPTION_TEXT = 11
elif sys.platform == 'linux2':
    FS_FILETITLE = 12
    FS_ITEM = 8
    FS_REMOVE_TEXT = 8
    FS_RSS = 10
    FS_RSS_TEXT = 8
    FS_RSSFEEDBACK_TEXT = 8
    FS_CONTAIN_TEXT = 7
    FS_UPDATE_TEXT = 7
    FS_FILETITLE_SEL = 14 
    FS_MAX_SUBSCRIPTION_TEXT = 8
else:
    FS_FILETITLE = 11
    FS_ITEM = 6
    FS_REMOVE_TEXT = 7
    FS_RSS = 10
    FS_RSS_TEXT = 7
    FS_RSSFEEDBACK_TEXT = 7
    FS_CONTAIN_TEXT = 8
    FS_UPDATE_TEXT = 4
    FS_FILETITLE_SEL = 10 
    FS_MAX_SUBSCRIPTION_TEXT = 5



class channelsDetails(bgPanel):
    def __init__(self, *args,**kwds):
        ##bgPanel.__init__(self,*args,**kwds)
        ##self.Hide()
        self.initialized = False
        self.publisher_id = None
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.backgroundColour = wx.Colour(216,233,240)
        self.xpos = self.ypos = 0
        self.tile = True
        self.bitmap = None
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        wx.CallAfter(bgPanel._PostInit,self)

        self.Hide()
        self.currentPage=0
        self.lastPage=0
        self.totalItems=0
        self.torrentsPerPage=15
        self.torrentLength=320
        self.torrentColour=(255,51,0)
        self.torrentColourSel=(0,105,156)

        self.parent = None


        # if channels details panel is viewing my channel
        self.mychannel = False

 
        # list of torrents
        self.torrents=[] 
        self.torrentList = None 

        # publisher id
        self.pubisher_id = None # in str mode

        # subscription state
        self.subscribed = False

        # rss
        self.torrentfeed = TorrentFeedThread.getInstance()
        self.rssFeed = None
        self.oldrssFeed = 1

        # empty state
        self.isempty = True
        
        self.vcdb = self.utility.session.open_dbhandler(NTFY_VOTECAST)
        self.torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.utility.session.open_dbhandler(NTFY_CHANNELCAST)

        self.origin = None 


        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        self.buddycast_factory = BuddyCastFactory.getInstance()
        self.channelcast = self.buddycast_factory.channelcast_core

        self.guiserver = GUITaskQueue.getInstance()
#        self.guiserver.add_task(self.guiservthread_refresh_torrents, 0)
        self.guiserver.add_task(self.guiservthread_updateincomingtorrents, 0)
        self.x=466
        self.addComponents()


        self.tl = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","tl.png"))
        self.tr = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","tr.png"))
        self.bl = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","bl.png"))
        self.br = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","br.png"))


        self.roundCorners()

        self.refreshScrollButtons()
        self.Refresh()
        bgPanel._PostInit(self)
        self.SetBackgroundColour(self.backgroundColour)

        self.hideElements()
        self.Refresh()

        if sys.platform != 'darwin':
            self.Show()

        #self.guiserver = GUITaskQueue.getInstance()
        #self.guiserver.add_task(self.guiservthread_updateincomingtorrents, 0)



    def addComponents(self):

        # main Sizer
        self.vSizer = wx.BoxSizer(wx.VERTICAL)

        # hSizer0
        self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer1
        self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer2
        self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer3
        self.hSizer3 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer4
        self.hSizer4 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizerChannels
        self.hSizerChannels = wx.BoxSizer(wx.HORIZONTAL)

        # vSizerLeft
        self.vSizerLeft = wx.BoxSizer(wx.VERTICAL)
       
        # vSizerRight
        self.vSizerRight = wx.BoxSizer(wx.VERTICAL)

        # vSizerContents
        self.vSizerContents = wx.BoxSizer(wx.VERTICAL) ## list of items within a particular channel
        self.vSizerContents.SetMinSize((self.x - 87,100))

        # channel title
        self.channelTitle =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(self.x-135,36))        
        self.channelTitle.SetBackgroundColour((216,233,240))
        self.channelTitle.SetForegroundColour(wx.BLACK)
        self.channelTitle.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))
        self.channelTitle.SetMinSize((self.x-135,36))

        # subscription text
        self.SubscriptionText = wx.StaticText(self,-1,"Unsubscribe",wx.Point(0,0),wx.Size(70,36),wx.ALIGN_RIGHT)  
        self.SubscriptionText.SetBackgroundColour((216,233,240))
        self.SubscriptionText.SetForegroundColour(wx.BLACK)
        self.SubscriptionText.SetFont(wx.Font(FS_REMOVE_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.SubscriptionText.SetMinSize((70,36))



        # rss text
        self.rssText = wx.StaticText(self,-1,"Rss Feed:",wx.Point(0,0),wx.Size(55,20))  
        self.rssText.SetBackgroundColour((216,233,240))
        self.rssText.SetForegroundColour(wx.BLACK)
        self.rssText.SetFont(wx.Font(FS_RSS_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.rssText.SetMinSize((55,20))

        # torrent text
        #self.torrentText = wx.StaticText(self,-1,"Torrent:",wx.Point(0,0),wx.Size(55,20))  
        #self.torrentText.SetBackgroundColour((216,233,240))
        #self.torrentText.SetForegroundColour(wx.BLACK)
        #self.torrentText.SetFont(wx.Font(FS_RSS_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        #self.torrentText.SetMinSize((55,20))


        # rss ctrl
        self.rssCtrl = wx.TextCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER|wx.NO_BORDER)
        self.rssCtrl.SetFont(wx.Font(FS_RSS, wx.MODERN, wx.NORMAL, wx.NORMAL, 0, "Verdana"))
        self.rssCtrl.Bind(wx.EVT_KEY_DOWN, self.addRSS)
        self.rssCtrl.SetBackgroundColour((206,223,230))
        self.rssCtrl.Refresh()
        #self.rssCtrl.SetValue("http://www.legaltorrents.com/feeds/cat/netlabel-music.rss")
        self.rssCtrl.SetMinSize((self.x-205,23))

        self.tf = TorrentFeedThread.getInstance()
        try:
            self.rssCtrl.SetValue(self.tf.mainURL)
            self.rssFeed = self.rssCtrl.GetValue().strip()
        except:
            pass


        #self.tf.addURL(self.rssCtrl.GetValue().strip()) ## callback=self.nonUIThreadAddTorrent



        # torrent ctrl
        #self.torrentCtrl = wx.TextCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER|wx.NO_BORDER)
        #self.torrentCtrl.SetFont(wx.Font(FS_RSS, wx.MODERN, wx.NORMAL, wx.NORMAL, 0, "Verdana"))
        #self.torrentCtrl.SetBackgroundColour((206,223,230))
        #self.torrentCtrl.SetMinSize((self.x-205,23))



        # add Button
        self.addButton = SwitchButton(self, -1, name = "addRSS")
        self.addButton.createBackgroundImage()  
        self.addButton.setToggled(True)
        self.addButton.Bind(wx.EVT_LEFT_UP, self.addRSS)      


        self.rssFeedbackText = wx.StaticText(self,-1,"Updated",wx.Point(0,0),wx.Size(55,20))  
        self.rssFeedbackText.SetBackgroundColour((216,233,240))
        self.rssFeedbackText.SetForegroundColour((0,110,149))
        self.rssFeedbackText.SetFont(wx.Font(FS_RSSFEEDBACK_TEXT,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))
        self.rssFeedbackText.SetMinSize((55,20))
        self.rssFeedbackText.Hide()


        #self.torrentFeedbackText = wx.StaticText(self,-1,"Added",wx.Point(0,0),wx.Size(55,20))  
        #self.torrentFeedbackText.SetBackgroundColour((216,233,240))
        #self.torrentFeedbackText.SetForegroundColour((0,110,149))
        #self.torrentFeedbackText.SetFont(wx.Font(FS_RSSFEEDBACK_TEXT,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))
        #self.torrentFeedbackText.SetMinSize((55,20))
        #self.torrentFeedbackText.Hide()




        # add Torrent button
        self.add_torrent = tribler_topButton(self, -1, name = "torrent_add")
        self.add_torrent.createBackgroundImage()
        self.add_torrent.Bind(wx.EVT_LEFT_UP, self.addTorrentClicked)
        self.add_torrent.Hide()



        # subscription button
        self.SubscriptionButton = SwitchButton(self, -1, name = "SubscriptionButton")
        self.SubscriptionButton.createBackgroundImage()
        self.SubscriptionButton.Bind(wx.EVT_LEFT_UP, self.SubscriptionClicked)

        # scroll left
        self.scrollLeft = tribler_topButton(self, -1, name = "scrollLeft_old")
        self.scrollLeft.createBackgroundImage()  
        self.scrollLeft.Bind(wx.EVT_LEFT_UP, self.scrollLeftClicked)      
 
        # scroll right
        self.scrollRight = tribler_topButton(self, -1, name = "scrollRight_old")
        self.scrollRight.createBackgroundImage()        
        self.scrollRight.Bind(wx.EVT_LEFT_UP, self.scrollRightClicked)      


        # contents text
        self.foundText = wx.StaticText(self,-1,"Found",wx.Point(0,0),wx.Size(100,18))  
        self.foundText.SetBackgroundColour((216,233,240))
        self.foundText.SetForegroundColour(wx.BLACK)
        self.foundText.SetFont(wx.Font(FS_CONTAIN_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.foundText.SetMinSize((100,18))


        # subscription limit text
        self.SubscriptionLimitText = wx.StaticText(self,-1,"Sorry, you have reached the maximum amout of subscriptions. Please unsubscribe to some channels.",wx.Point(0,0),wx.Size(330,40), style = wx.ALIGN_CENTRE)  
        self.SubscriptionLimitText.SetBackgroundColour((216,233,240))
        self.SubscriptionLimitText.SetForegroundColour((255,0,0))
        self.SubscriptionLimitText.SetFont(wx.Font(FS_MAX_SUBSCRIPTION_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.SubscriptionLimitText.SetMinSize((330,40))
        self.SubscriptionLimitText.Hide()
  

        # add Spam button
        self.spam = tribler_topButton(self, -1, name = "spam")
        self.spam.SetPosition((196,70))
        self.spam.createBackgroundImage()
        self.spam.Bind(wx.EVT_LEFT_UP, self.spamClicked)
        self.spam.Hide()

        self.hSizer0.Add((20,0), 0, 0, 0)
        self.hSizer0.Add(self.channelTitle, 0, 0, 0)
        self.hSizer0.Add((5,0), 0, 0, 0)
        self.hSizer0.Add(self.SubscriptionText, 0, 0, 0)
        self.hSizer0.Add((5,0), 0, 0, 0)
        self.hSizer0.Add(self.SubscriptionButton, 0, 0, 0)


        self.hSizer1.Add((20,0), 0, 0, 0)
        self.hSizer1.Add(self.foundText, 0, 0, 0)
        self.hSizer1.Add((5,0), 0, 0, 0)
        self.hSizer1.Add(self.SubscriptionLimitText, 0, 0, 0)


        self.hSizer2.Add((20,20), 0, 0, 0)
        self.hSizer2.Add(self.rssText, 0, wx.TOP, 3)
        self.hSizer2.Add((5,0), 0, 0, 0)
        self.hSizer2.Add(self.rssCtrl, 0, 0, 0)
        if sys.platform != 'darwin':
            self.hSizer2.Add((10,0), 0, 0, 0)
        else:
            self.hSizer2.Add((5,0), 0, 0, 0)
        self.hSizer2.Add(self.addButton, 0, 0, 0)
        self.hSizer2.Add((5,0), 0, 0, 0)
        self.hSizer2.Add(self.rssFeedbackText, 0, wx.TOP, 5)

        if sys.platform == 'darwin':
            self.hSizer3.Add((346,0), 0, 0, 0)
        else:
            self.hSizer3.Add((351,0), 0, 0, 0)
        self.hSizer3.Add(self.add_torrent, 0, 0, 0)


        #self.hSizer3.Add((20,20), 0, 0, 0)
        #self.hSizer3.Add(self.torrentText, 0, wx.TOP, 3)
        #self.hSizer3.Add((5,0), 0, 0, 0)
        #self.hSizer3.Add(self.torrentCtrl, 0, 0, 0)
        #if sys.platform != 'darwin':
        #    self.hSizer3.Add((10,0), 0, 0, 0)
        #else:
        #    self.hSizer3.Add((5,0), 0, 0, 0)
        #self.hSizer3.Add(self.add_torrent, 0, 0, 0)
        #self.hSizer3.Add((5,0), 0, 0, 0)
        #self.hSizer3.Add(self.torrentFeedbackText, 0, wx.TOP, 5)


        #self.hSizer4.Add((196,0), 0, 0, 0)
        #self.hSizer4.Add(self.spam, 0, 0, 0)

            
        self.vSizerLeft.Add((0,100), 0, 0, 0)
        self.vSizerLeft.Add(self.scrollLeft, 0, 0, 0)

        self.vSizerRight.Add((0,100), 0, 0, 0)
        self.vSizerRight.Add(self.scrollRight, 0, 0, 0)

        self.hSizerChannels.Add((20,0), 0, 0, 0)
        self.hSizerChannels.Add(self.vSizerLeft, 0, 0, 0)
        self.hSizerChannels.Add((10,0), 0, 0, 0)
        self.hSizerChannels.Add(self.vSizerContents, 0, 0, 0)
        self.hSizerChannels.Add((10,0), 0, 0, 0)
        self.hSizerChannels.Add(self.vSizerRight, 0, 0, 0)


        self.vSizer.Add((0,15), 0, 0, 0)
        self.vSizer.Add(self.hSizer0, 0, 0, 0)     
        self.vSizer.Add((0,2), 0, 0, 0)
        self.vSizer.Add(self.hSizer1, 0, wx.TOP, -15)
        if sys.platform == 'darwin':
            self.vSizer.Add((0,4), 0, 0, 0)
        else:
            self.vSizer.Add((0,2), 0, 0, 0)
        self.vSizer.Add(self.hSizer2, 0, 0, 0)     
        self.vSizer.Add((0,3), 0, 0, 0)
        self.vSizer.Add(self.hSizer3, 0, 0, 0)     
        self.vSizer.Add((0,3), 0, 0, 0)
        self.vSizer.Add(self.hSizer4, 0, 0, 0)     
        self.vSizer.Add((0,40), 0, 0, 0)
        self.vSizer.Add(self.hSizerChannels, 0, 0, 0)     


        self.initialized = True

        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.vSizer.Layout()
        self.Layout()

    def guiservthread_refresh_torrents(self):
        records = self.channelcast.getNewRecords()
        print >> sys.stderr , "RECORD : " , records
        self.guiserver.add_task(self.guiservthread_refresh_torrents,5.0)


    def setType(self, Type):
        self.type = Type



    def hideElements(self, force = False):
        if self.initialized == True or force==True:
            self.channelTitle.Hide()
            self.SubscriptionButton.Hide()
            self.foundText.Hide()
            self.scrollLeft.Hide()
            self.scrollRight.Hide()
            self.SubscriptionText.Hide()
            self.foundText.Hide()
            self.rssText.Hide()
            self.rssCtrl.Hide()
            self.addButton.Hide()
            self.rssFeedbackText.Hide()
            self.add_torrent.Hide()
            self.spam.Hide()

    def reinitialize(self, force = False):
        try:
            self.hideElements(force)
            self.clearAll()
            self.isempty = True
        except:
            pass

    def clearAll(self):
        for i in range(self.totalItems):
            if type(self.torrents[i]) is not dict:
                self.torrents[i].title.SetLabel('')
                self.torrents[i].Hide()
        self.vSizerContents.Clear()
        self.vSizerContents.Layout()
        self.vSizer.Layout()
        self.Layout()
    


    
    def isEmpty(self):
        try:
            return self.isempty
        except:
            return True

    def roundCorners(self):
        wx.EVT_PAINT(self, self.OnPaint)


    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self.tl, 0, 0)
        dc.DrawBitmap(self.tr, 456, 0)
        dc.DrawBitmap(self.bl, 0, 490)
        dc.DrawBitmap(self.br, 456, 490)


    def addRSS(self, event):
        if event.GetEventObject().GetName() == 'text':        
            keycode = event.GetKeyCode()
        else:
            keycode = None

        if self.rssCtrl.GetValue().strip() != '' and (keycode == wx.WXK_RETURN or event.GetEventObject().GetName() == 'addRSS') and self.rssFeed != self.rssCtrl.GetValue().strip() and self.addButton.isToggled():
            self.torrentfeed.deleteURL(self.rssFeed) 
            self.setRSSFeed(self.rssCtrl.GetValue().strip())
            self.torrentfeed.addURL(self.rssFeed, callback=self.nonUIThreadAddTorrent) 
            self.addButton.setToggled(False)
            self.updateRSS()
        else:
            event.Skip()
            if event.GetEventObject().GetName() != 'addRSS':
                self.addButton.setToggled(True)



    def setRSSFeed(self, rssfeed):
        self.rssFeed = rssfeed

    def getRSSFeed(self):
        return self.rssFeed



    def setSubscribed(self, subscribed):
        self.subscribed = subscribed


    def showElements(self, subscribed):
        self.channelTitle.Show()
        self.SubscriptionButton.Show()
        self.SubscriptionText.Show()
        self.foundText.Show()
        self.rssText.Hide()
        self.rssCtrl.Hide()
        self.addButton.Hide()
        self.rssFeedbackText.Hide()
        self.add_torrent.Hide()
        self.spam.Hide()
        if len(self.torrentList) != 1:
            self.foundText.SetLabel("Found %s files" % len(self.torrentList))
        else:
            self.foundText.SetLabel("Found %s file" % len(self.torrentList))
            
        
        if self.parent.isMyChannel(): # My Channel
            self.add_torrent.Show()
            self.SubscriptionButton.Hide()
            self.SubscriptionText.Hide()
            self.rssText.Show()
            self.rssCtrl.Show()
            if self.rssFeed is not None:
                self.rssCtrl.SetValue(self.rssFeed)
            self.addButton.Show()

        else:
            if subscribed:
                self.SubscriptionText.SetLabel("Unsubscribe")
                self.SubscriptionButton.setToggled(False)
            else:
                self.SubscriptionText.SetLabel("Subscribe")
                self.SubscriptionButton.setToggled(True)
        self.scrollLeft.Show()
        self.scrollRight.Show()
        self.isempty = False



    def checkDuplicates(self, event): # for testing
        for el in range(len(self.torrentList)):
            for el2 in range(len(self.torrentList)):
                if el!=el2:
                    i1 =self.torrentList[el]['infohash']
                    i2 =self.torrentList[el2]['infohash']
                    if i1==i2:
                        print >> sys.stderr, el, el2
        print >> sys.stderr , "DONE"
                    
                     



    def spamClicked(self, event):
        dialog = wx.MessageDialog(None, "Are sure you want to report %s as spam ?\nThis will remove all the torrents and possibly unsubscribe you from the channel. " % self.channelTitle.GetLabel(), "Report spam", wx.OK|wx.CANCEL|wx.ICON_WARNING)
        result = dialog.ShowModal()
        dialog.Destroy()
        if result == wx.ID_OK:
            self.reinitialize() 
            self.vcdb.spam(self.publisher_id)
            self.channelcast_db.deleteTorrentsFromPublisherId(self.publisher_id)
            if self.guiUtility.frame.top_bg.indexPopularChannels != -1:
                wx.CallAfter(self.guiUtility.standardOverview.getGrid(2).clearAllData)
                wx.CallAfter(self.guiUtility.standardOverview.getGrid(2).gridManager.refresh)
            else:
                wx.CallAfter(self.guiUtility.standardOverview.getGrid().clearAllData)
                wx.CallAfter(self.guiUtility.standardOverview.getGrid().gridManager.refresh)


    def addTorrentClicked(self, event):
        dlg = wx.FileDialog(self,"Choose torrent file", style = wx.DEFAULT_DIALOG_STYLE)
        path = self.defaultDLConfig.get_dest_dir()
        dlg.SetPath(path)
        if dlg.ShowModal() == wx.ID_OK and os.path.isfile(dlg.GetPath()):
            infohash = self.tf.addFile(dlg.GetPath())
            if infohash is not None:
                try:
                    torrent = self.torrent_db.getTorrent(infohash)

                    if DEBUG:
                        print >> sys.stderr , torrent
                    self.addTorrent(torrent, True)
                except:
                    print >> sys.stderr , "Could not add torrent"
                    pass
            else:
                print >> sys.stderr , "No infohash. Could not add torrent"

            

    def nonUIThreadAddTorrent(self, rss_url, infohash, torrent_data):
        if DEBUG:
            print >> sys.stderr , "NONUITHREAD"
        if self.isMyChannel() and torrent_data is not None:
            try:
                torrent = self.torrent_db.getTorrent(infohash)
                if DEBUG:
                    print >> sys.stderr , torrent
                wx.CallAfter(self.addTorrent, torrent, True)
                # wx.CallAfter(self.rssCtrl.SetFocus)
            except:
                pass


    def getNumItemsCurrentPage(self):
        if self.totalItems == 0:
            return 0
        else:
            if self.currentPage != self.lastPage:
                return self.torrentsPerPage
            else:
                numItems = self.totalItems % self.torrentsPerPage
                if numItems == 0:
                    numItems = self.torrentsPerPage
                return numItems
                
            
    def isMyChannel(self):
        return self.mychannel


    def haveTorrent(self, infohash):
        for el in self.torrentList:
            if infohash==el['infohash']:
                return True
        return False    
                



    def addTorrent(self, torrent, isMine = False):
        if DEBUG:
            print >> sys.stderr , "ADDTORRENT"


        if not haveTorrent(torrent['infohash']):

            print >> sys.stderr , "new torrent" , torrent
            self.erasevSizerContents()

            self.torrentList.append(torrent)
            self.totalItems = len(self.torrentList)
            self.setLastPage()
            self.parent.setTorrentList(self.torrentList)
            self.showElements(self.subscribed)

            item=channelsDetailsItem(self, -1)
            item.reemove.Hide()
            item.SetIndex(self.totalItems - 1)
            item.setTitle(self.torrentList[-1]['name'])
            item.setTorrent(self.torrentList[-1])
            item.setMine(isMine)
            item.deselect()
            item.Hide()
            self.torrents.append(item)

            self.displayChannelContents()

        elif DEBUG:
            print >> sys.stderr , "Already have torrent : " , torrent



    def removeTorrent(self, index):
#        if self.currentPage == self.lastPage:
#            numItems = self.totalItems % self.torrentsPerPage
#            for i in range (numItems):
#                self.torrents[self.currentPage*self.torrentsPerPage+i].Hide()
#        del self.torrentList[index]
#        self.parent.setTorrentList(self.torrentList)
#        self.parent.setMyTitle()
#        if self.currentPage == self.lastPage and (self.totalItems -1) % self.torrentsPerPage == 0 and self.currentPage > 0:
#            self.currentPage = self.currentPage - 1
#        self.reloadChannel(self.torrentList)

        self.erasevSizerContents()

        if DEBUG:
            print >> sys.stderr , "INDEX DELETED" , index

        # change self.torrentList
        del self.torrentList[index]
        self.parent.setTorrentList(self.torrentList)
        self.parent.setMyTitle()

        # change self.torrents
        del self.torrents[index]

        # update indexes
        for i in range(index, self.totalItems-1):
            if type (self.torrents[i]) is not dict:
                self.torrents[i].SetIndex(i)

        self.totalItems = self.totalItems - 1

        self.setLastPage()
        if self.currentPage > self.lastPage:
            self.currentPage = self.currentPage - 1


        self.showElements(self.subscribed)
        self.displayChannelContents()


    def loadChannel(self, parent, torrentList, publisher_id, publisher_name, subscribed):
        self.currentPage = 0
        self.parent = parent
        self.mychannel = self.parent.mychannel
        self.torrents = torrentList[:] # make a shallow copy because we plan to
                              # modify this list

        self.torrentList = torrentList
        self.totalItems = len(self.torrentList)
        self.setLastPage()
        self.setSubscribed(subscribed)
        self.setPublisherId(publisher_id)
        self.showElements(subscribed)
        self.erasevSizerContents()
        self.setTitle(publisher_name)
        #self.addItems()
        if not self.parent.isMyChannel():
            self.spam.Show()
        self.displayChannelContents()
        self.roundCorners()
        self.Refresh()


    def reloadChannel(self, torrentList): # reloads the list of torrents after a torrent has been added or deleted
        self.torrentList = torrentList
        self.totalItems = len(self.torrentList)
        self.showElements(self.subscribed)
        self.erasevSizerContents()
        self.Refresh()
        self.setLastPage()
        self.addItems()
        self.displayChannelContents()


    def addItems(self):
        isMine = self.parent.isMyChannel()
        self.torrents = []
        for i in range(self.totalItems):
            if DEBUG:
                print >> sys.stderr , "item :" , i
            item=channelsDetailsItem(self, -1)
            item.reemove.Hide()
            item.SetIndex(i)
            self.torrents.append(item)
            self.torrents[i].setTitle(self.torrentList[i]['name'])
            self.torrents[i].setTorrent(self.torrentList[i])
            self.torrents[i].setMine(isMine)
            self.torrents[i].deselect()
            self.torrents[i].Hide()



    def displayChannelContents(self):
        isMine = self.parent.isMyChannel()
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.torrentsPerPage
            if numItems == 0 and self.totalItems != 0:
                numItems = self.torrentsPerPage
        else:
            numItems = self.torrentsPerPage    

        #print >> sys.stderr , "numitems" , numItems



        for index in range(self.currentPage*self.torrentsPerPage, self.currentPage*self.torrentsPerPage+numItems):
            if type(self.torrents[index]) is dict:
                item = channelsDetailsItem(self, -1)
                item.reemove.Hide()
                item.SetIndex(index)
                self.torrents[index] = item
                self.torrents[index].setTitle(self.torrentList[index]['name'])
                self.torrents[index].setTorrent(self.torrentList[index])
                self.torrents[index].setMine(isMine)
           
            self.vSizerContents.Add(self.torrents[index], 0, 0, 0)
            self.torrents[index].Show()



#        for i in range(numItems):
#            if DEBUG:
#                print >> sys.stderr , "showing item :" , i

#            self.vSizerContents.Add(self.torrents[self.currentPage*self.torrentsPerPage+i], 0, 0, 0)
#            self.torrents[self.currentPage*self.torrentsPerPage+i].Show()
        self.vSizerContents.Layout()
        self.refreshScrollButtons()
        self.Layout()
        self.Refresh()




    def erasevSizerContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.torrentsPerPage
            if numItems == 0 and self.totalItems != 0:
                numItems = self.torrentsPerPage
        else:
            numItems = self.torrentsPerPage    
        for index in range(self.currentPage*self.torrentsPerPage, self.currentPage*self.torrentsPerPage+numItems):
            if type(self.torrents[index]) is not dict:
                self.torrents[index].Hide()
        self.vSizerContents.Clear()
        self.vSizerContents.Layout()
        self.vSizer.Layout()
        self.Layout()




    def setTitle(self, title):
        if self.parent.isMyChannel():
            self.channelTitle.SetLabel(title)
        else:
            self.channelTitle.SetLabel(title  + "'s channel")
        self.Refresh()


    def setLastPage(self, lastPage=None):
        if lastPage is None:
            if self.totalItems % self.torrentsPerPage == 0:
                self.lastPage = self.totalItems / self.torrentsPerPage - 1
                if self.lastPage == -1:
                    self.lastPage = 0
            else:
                self.lastPage = (self.totalItems - self.totalItems % self.torrentsPerPage) / self.torrentsPerPage

        else:
            self.lastPage=lastPage


    def setPublisherId(self, publisher_id):
        if publisher_id is not None:
            self.publisher_id = publisher_id

    def refreshScrollButtons(self):
        self.scrollLeft.setSelected(self.currentPage==0)
        self.scrollRight.setSelected(self.currentPage==self.lastPage)


    def scrollLeftClicked(self, event):
        if self.currentPage > 0:
            self.erasevSizerContents()
            self.currentPage = self.currentPage - 1
            self.displayChannelContents()

    def scrollRightClicked(self, event):
        if self.currentPage < self.lastPage:
            self.erasevSizerContents()
            self.currentPage = self.currentPage + 1
            self.displayChannelContents()




    def refreshItems(self):
        for i in range(self.totalItems):
            if self.torrents[i].selected:
                self.torrents[i].select()
            else:
                self.torrents[i].deselect()

    def deselectAllExceptSelected(self, index): ## for mac os x
        for i in range(self.totalItems):
            if i <> index and type(self.torrents[i]) is not dict:
                self.torrents[i].deselect()
        


    def deselectAll(self):
        for i in range(self.totalItems):
            if type(self.torrents[i]) is not dict:
                self.torrents[i].deselect()
        

    def SubscriptionClicked(self, event):
        if self.SubscriptionButton.isToggled(): # subscribe
      
            if self.guiUtility.nb_subscriptions < 10: # hard coded for now, max subscriptions = 10

                self.vcdb.subscribe(self.publisher_id)
                self.SubscriptionText.SetLabel("Unsubscribe")
                self.SubscriptionButton.setToggled(False)

                self.guiUtility.frame.top_bg.needs_refresh = True

#                if self.guiUtility.frame.top_bg.indexPopularChannels != -1:
#                    self.guiUtility.standardOverview.getGrid(2).getPanelFromIndex(self.parent.index).num_votes+=1    
#                else:
#                    self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).num_votes+=1
#                    print >> sys.stderr , self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).num_votes


            else: # maximum number of subscriptions reached
                self.updateSubscriptionLimitText()




        else: # unsubscribe
            self.vcdb.unsubscribe(self.publisher_id)
            self.SubscriptionText.SetLabel("Subscribe")
            self.SubscriptionButton.setToggled(True)

            self.guiUtility.frame.top_bg.needs_refresh = True


#            if self.guiUtility.frame.top_bg.indexPopularChannels != -1:
#                self.guiUtility.standardOverview.getGrid(2).getPanelFromIndex(self.parent.index).num_votes-=1    
#            else:
#                self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).num_votes-=1
#                print >> sys.stderr , self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).num_votes



        if self.guiUtility.frame.top_bg.indexPopularChannels != -1:
            self.guiUtility.standardOverview.getGrid(2).getPanelFromIndex(self.parent.index).setSubscribed()       
            self.guiUtility.standardOverview.getGrid(2).getPanelFromIndex(self.parent.index).resetTitle()      
        else:
            self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).setSubscribed()       
            self.guiUtility.standardOverview.getGrid().getPanelFromIndex(self.parent.index).resetTitle()       

#        if self.guiUtility.frame.top_bg.needs_refresh:
#            self.guiUtility.frame.top_bg.indexPopularChannels = -1
#            self.guiUtility.frame.top_bg.indexMyChannel = -1


    def updateSubscriptionLimitText(self):
        self.guiserver = GUITaskQueue.getInstance()
        self.guiserver.add_task(lambda:wx.CallAfter(self.showSubscriptionLimitText), 0.0)

    def showSubscriptionLimitText(self):
        self.SubscriptionLimitText.Show(True)
        sizer = self.SubscriptionLimitText.GetContainingSizer()
        sizer.Layout()
        self.guiserver.add_task(lambda:wx.CallAfter(self.hideSubscriptionLimitText), 3.0)

    def hideSubscriptionLimitText(self):
        self.SubscriptionLimitText.Show(False)



    def updateRSS(self):
        self.guiserver = GUITaskQueue.getInstance()
        self.guiserver.add_task(lambda:wx.CallAfter(self.showRSS), 0.0)

    def showRSS(self):
        self.rssFeedbackText.Show(True)
        sizer = self.rssFeedbackText.GetContainingSizer()
        sizer.Layout()
        self.guiserver.add_task(lambda:wx.CallAfter(self.hideRSS), 3.0)

    def hideRSS(self):
        self.rssFeedbackText.Show(False)


    def guiservthread_updateincomingtorrents(self):
        self.checkincomingtorrents()
        self.guiserver.add_task(self.guiservthread_updateincomingtorrents,2.0)


    def checkincomingtorrents(self):
        if self.publisher_id is not None:
            hits = self.channelcast.hits[:]
            non_added_hits=[]
            if DEBUG:
                print >> sys.stderr , "NEW CHANNELCAST RECORDS : ", hits
            try:
                if len(hits) > 0: # new torrents
                    for hit in hits:
                        if self.publisher_id != hit[0]:
                            non_added_hits.append(hit)
                            continue
                        torrent = self.torrent_db.getTorrent(str2bin(hit[2]))
                        if torrent is not None:
                            b = self.publisher_id == bin2str(self.guiUtility.utility.session.get_permid())
                            wx.CallAfter(self.addTorrent, torrent, b)
                        else:
                            non_added_hits.append(hit)
                    self.channelcast.hits = non_added_hits[:]
            except:
                pass

            



