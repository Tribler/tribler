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

from Tribler.Core.CacheDB.sqlitecachedb import bin2str

from font import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Main.vwxGUI.tribler_topButton import *

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.channelsDetailsItem import channelsDetailsItem

from Tribler.Subscriptions.rss_client import TorrentFeedThread

from Tribler.__init__ import LIBRARYNAME

DETAILS_MODES = ['filesMode',  'libraryMode', 'channelsMode']

DEBUG = False


# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 14
    FS_ITEM = 12
    FS_REMOVE_TEXT = 12
    FS_RSS = 10
    FS_RSS_TEXT = 11
    FS_RSSFEEDBACK_TEXT = 11
    FS_CONTAIN_TEXT = 10
    FS_UPDATE_TEXT = 10
    FS_FILETITLE_SEL = 14 # size of title in expanded torrent
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
else:
    FS_FILETITLE = 11
    FS_ITEM = 6
    FS_REMOVE_TEXT = 6
    FS_RSS = 10
    FS_RSS_TEXT = 7
    FS_RSSFEEDBACK_TEXT = 7
    FS_CONTAIN_TEXT = 8
    FS_UPDATE_TEXT = 4
    FS_FILETITLE_SEL = 10 





class channelsDetails(bgPanel):
    def __init__(self, *args,**kwds):
        ##bgPanel.__init__(self,*args,**kwds)
        ##self.Hide()
        self.initialized = False
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
        self.torrentSpacing=(0,5) # space between torrents
        self.torrentLength=320
        self.torrentColour=(255,51,0)
        self.torrentColourSel=(0,105,156)

        self.parent = None

 
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


        self.origin = None 



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

    def addComponents(self):

        # main Sizer
        self.vSizer = wx.BoxSizer(wx.VERTICAL)

        # hSizer0
        self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer1
        self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizer2
        self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        # hSizerChannels
        self.hSizerChannels = wx.BoxSizer(wx.HORIZONTAL)


        # vSizer2
        self.vSizer2 = wx.BoxSizer(wx.VERTICAL)

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

        # rss ctrl
        self.rssCtrl = wx.TextCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER|wx.NO_BORDER)
        self.rssCtrl.SetFont(wx.Font(FS_RSS, wx.MODERN, wx.NORMAL, wx.NORMAL, 0, "Verdana"))
        self.rssCtrl.Bind(wx.EVT_KEY_DOWN, self.addRSS)
        self.rssCtrl.SetBackgroundColour((206,223,230))
        #self.rssCtrl.SetValue("http://www.legaltorrents.com/feeds/cat/netlabel-music.rss")
        self.rssCtrl.SetMinSize((self.x-205,23))

        self.tf = TorrentFeedThread.getInstance()
        try:
	    self.rssCtrl.SetValue(self.tf.mainURL)
        except:
            pass

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


        # add Torrent button
        ##self.add_torrent = tribler_topButton(self, -1, name = "addTorrent")
        ##self.add_torrent.createBackgroundImage()
        ##self.add_torrent.Bind(wx.EVT_LEFT_UP, self.addTorrentClicked)
        ##self.add_torrent.Hide()

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
        self.foundText = wx.StaticText(self,-1,"Found",wx.Point(0,0),wx.Size(150,18))  
        self.foundText.SetBackgroundColour((216,233,240))
        self.foundText.SetForegroundColour(wx.BLACK)
        self.foundText.SetFont(wx.Font(FS_CONTAIN_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.foundText.SetMinSize((150,18))


        # update subscription text
        #self.updateSubscriptionText = wx.StaticText(self,-1,"Last Updated 3 days ago",wx.Point(0,0),wx.Size(150,18))  
        #self.updateSubscriptionText.SetBackgroundColour((216,233,240))
        #self.updateSubscriptionText.SetForegroundColour(wx.BLACK)
        #self.updateSubscriptionText.SetFont(wx.Font(FS_UPDATE_TEXT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        #self.updateSubscriptionText.SetMinSize((150,18))
   


        self.hSizer0.Add((20,0), 0, 0, 0)
        self.hSizer0.Add(self.channelTitle, 0, 0, 0)
        self.hSizer0.Add((5,0), 0, 0, 0)
        self.hSizer0.Add(self.SubscriptionText, 0, 0, 0)
        self.hSizer0.Add((5,0), 0, 0, 0)
        self.hSizer0.Add(self.SubscriptionButton, 0, 0, 0)

        self.vSizer2.Add(self.foundText, 0, 0, 0)
        self.vSizer2.Add((0,5), 0, 0, 0)
        ##self.vSizer2.Add(self.add_torrent, 0, 0, 0)

        self.hSizer1.Add((20,0), 0, 0, 0)
        self.hSizer1.Add(self.vSizer2, 0, 0, 0)

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
        self.vSizer.Add((0,2), 0, 0, 0)
        self.vSizer.Add(self.hSizer2, 0, 0, 0)     
        self.vSizer.Add((0,50), 0, 0, 0)
        self.vSizer.Add(self.hSizerChannels, 0, 0, 0)     


        self.initialized = True

        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.Layout()


    def setType(self, Type):
        self.type = Type



    def hideElements(self, force = False):
        if self.initialized == True or force==True:
            self.channelTitle.Hide()
            self.SubscriptionButton.Hide()
            ##self.updateSubscriptionText.Hide()
            self.foundText.Hide()
            self.scrollLeft.Hide()
            self.scrollRight.Hide()
            self.SubscriptionText.Hide()
            self.foundText.Hide()
            self.rssText.Hide()
            self.rssCtrl.Hide()
            self.addButton.Hide()
            self.rssFeedbackText.Hide()

    def reinitialize(self, force = False):
        self.hideElements(force)
        self.clearAll()
        self.isempty = True


    def clearAll(self):
        for i in range(self.totalItems):
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
            self.setRSSFeed(self.rssCtrl.GetValue().strip())
            self.torrentfeed.deleteURL(self.rssFeed) 
            self.torrentfeed.addURL(self.rssCtrl.GetValue().strip()) 
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
        self.rssText.Hide()
        self.rssCtrl.Hide()
        self.addButton.Hide()
        self.rssFeedbackText.Hide()

        self.foundText.Show()
        if len(self.torrentList) != 1:
            self.foundText.SetLabel("Found %s files" % len(self.torrentList))
        else:
            self.foundText.SetLabel("Found %s file" % len(self.torrentList))
            
        
        if self.parent.isMyChannel(): # My Channel
            self.SubscriptionButton.Hide()
            self.SubscriptionText.Hide()
            self.rssText.Show()
            self.rssCtrl.Show()
            if self.rssFeed is not None:
                self.rssCtrl.SetValue(self.rssFeed)
            self.addButton.Show()

        elif subscribed:
            self.SubscriptionText.SetLabel("Unsubscribe")
            self.SubscriptionButton.setToggled(False)
        else:
            self.SubscriptionText.SetLabel("Subscribe")
            self.SubscriptionButton.setToggled(True)
        self.scrollLeft.Show()
        self.scrollRight.Show()
        self.isempty = False






    def addTorrent(self, torrent):
        self.torrentList.append(torrent)
        self.parent.setTorrentList(self.torrentList)
        self.parent.setMyTitle()
        self.reloadChannel(self.torrentList)


    def removeTorrent(self, index):
        del self.torrentList[index]
        self.parent.setTorrentList(self.torrentList)
        self.parent.setMyTitle()
        self.reloadChannel(self.torrentList)



    def loadChannel(self, parent, torrentList, publisher_id, publisher_name, subscribed):
        self.parent = parent
        self.torrentList = torrentList
        ##self.add_torrent.Show(self.parent.isMyChannel())
        self.setSubscribed(subscribed)
        self.setPublisherId(publisher_id)
        self.showElements(subscribed)
        self.erasevSizerContents()
        self.Refresh()
        self.setTitle(publisher_name)
        self.totalItems = len(self.torrentList)
        self.setLastPage()
        self.addItems()
        self.displayChannelContents()
        self.roundCorners()
        self.Refresh()


    def reloadChannel(self, torrentList): # reloads the list of torrents after a torrent has been added or deleted
        self.torrentList = torrentList
        self.showElements(self.subscribed)
        self.erasevSizerContents()
        self.Refresh()
        self.totalItems = len(self.torrentList)
        self.setLastPage()
        self.addItems()
        self.displayChannelContents()


    def addItems(self):
        isMine = self.parent.isMyChannel()
        self.torrents = []
        for i in range(self.totalItems):
            item=channelsDetailsItem(self, -1)
            item.SetIndex(i)
            self.torrents.append(item)
            self.torrents[i].setTitle(self.torrentList[i]['name'])
            self.torrents[i].setTorrent(self.torrentList[i])
            self.torrents[i].setMine(isMine)
            self.torrents[i].deselect()
            self.torrents[i].Hide()



    def displayChannelContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.torrentsPerPage
            if numItems == 0 and self.totalItems != 0:
                numItems = self.torrentsPerPage
        else:
            numItems = self.torrentsPerPage    



        for i in range(numItems):
            self.vSizerContents.Add(self.torrents[self.currentPage*self.torrentsPerPage+i], 0, 0, 0)
            self.torrents[self.currentPage*self.torrentsPerPage+i].Show()
            # self.vSizerContents.Add(self.torrentSpacing, 0, 0, 0)
        self.vSizerContents.Layout()
        self.refreshScrollButtons()
        self.Layout()
        self.Refresh()




    def erasevSizerContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.torrentsPerPage
        else:
            numItems = self.torrentsPerPage    
        for i in range(numItems):
            self.torrents[self.currentPage*self.torrentsPerPage+i].Hide()
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
            if i <> index:
                self.torrents[i].deselect()
        


    def deselectAll(self):
        for i in range(self.totalItems):
            self.torrents[i].deselect()
        

    def SubscriptionClicked(self, event):
        if self.SubscriptionButton.isToggled():
            self.vcdb.subscribe(self.publisher_id)
            self.SubscriptionText.SetLabel("Unsubscribe")
            self.SubscriptionButton.setToggled(False)
            self.parent.num_votes+=1

        else:
            self.vcdb.unsubscribe(self.publisher_id)

            self.guiUtility.frame.top_bg.indexMyChannel=-1
            self.guiUtility.frame.top_bg.indexPopularChannels=-1
            self.guiUtility.frame.top_bg.indexSubscribedChannels=-1

            self.SubscriptionText.SetLabel("Subscribe")
            self.SubscriptionButton.setToggled(True)
            self.parent.num_votes-=1

        self.parent.setSubscribed() # reloads subscription state of the parent
        self.parent.resetTitle()


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








