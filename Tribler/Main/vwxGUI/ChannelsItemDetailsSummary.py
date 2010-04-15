import wx, os

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Utilities.unicode import bin2unicode

from Tribler.Category.Category import Category
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton, TestButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.ColumnHeader import ColumnHeaderBar
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.GridState import GridState
from Tribler.Main.vwxGUI.SearchGridManager import SEARCHMODE_NONE, SEARCHMODE_SEARCHING, SEARCHMODE_STOPPED

from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL

from font import *


# font sizes
if sys.platform == 'darwin':
    FS_SUBSCRIBE = 7
    FS_TORRENT = 7
elif sys.platform == 'linux2':
    FS_SUBSCRIBE = 7
    FS_TORRENT = 7
else:
    FS_SUBSCRIBE = 7
    FS_TORRENT = 7




class ChannelsItemDetailsSummary(bgPanel):
    
    def __init__(self, parent, torrentList, subscribed):
        wx.Panel.__init__(self, parent, -1)

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility   
        self.mcdb = self.utility.session.open_dbhandler(NTFY_MODERATIONCAST)
        self.vcdb = self.utility.session.open_dbhandler(NTFY_VOTECAST)

        self.session = self.utility.session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)


        self.torrentList = torrentList



        self.currentPage=0
        self.lastPage=0
        self.totalItems=0
        self.torrentsPerPage=3
        self.torrentSpacing=(0,5) # space between torrents
        self.torrentLength=50
        self.torrentColour=(255,51,0)
        self.torrentColourSel=(0,105,156)
 
        # list of torrents
        self.torrents=[] 

        # subscription state
        self.subscribed = subscribed


        self.addComponents()
        self.refreshScrollButtons()

        self.loadChannel()

        self.tile = True
        self.backgroundColour = wx.Colour(102,102,102)
        self.searchBitmap('blue_long.png')
        self.createBackgroundImage()


        self.gridmgr = parent.parent.getGridManager()

        self.Refresh(True)
        self.Update()

        
        
    def addComponents(self):
        self.triblerStyles = TriblerStyles.getInstance()


       # hSizer0
        self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)               

        # subscription button
        self.subscribe = SwitchButton(self, -1, name = "subscribe")
        self.subscribe.Bind(wx.EVT_LEFT_UP, self.subscribeClicked)
        self.subscribe.setToggled(not self.subscribed)
        self.subscribeText = wx.StaticText(self,-1,"Subscribe",wx.Point(0,0),wx.Size(200,18))
        self.subscribeText.SetFont(wx.Font(FS_SUBSCRIBE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        if self.subscribed:
            self.subscribeText.SetForegroundColour((150,150,150)) # grey colour 


       # vSizer0
        self.vSizer0 = wx.BoxSizer(wx.VERTICAL)               
        self.vSizer0.Add((0,15), 0, 0, 0)
        self.vSizer0.Add(self.subscribe, 0, 0, 0)
        self.vSizer0.Add((0,3), 0, 0, 0)
        self.vSizer0.Add(self.subscribeText, 0, wx.LEFT, -8)


        # vSizerLeft
        self.vSizerLeft = wx.BoxSizer(wx.VERTICAL)
       
        # vSizerRight
        self.vSizerRight = wx.BoxSizer(wx.VERTICAL)

        # vSizerContents
        self.vSizerContents = wx.BoxSizer(wx.VERTICAL) ## list of items within a particular channel
        self.vSizerContents.SetMinSize((300,30))



        # scroll left
        self.scrollLeft = tribler_topButton(self, -1, name = "scrollLeft")
        self.scrollLeft.createBackgroundImage()  
        self.scrollLeft.Bind(wx.EVT_LEFT_UP, self.scrollLeftClicked)      
 
        # scroll right
        self.scrollRight = tribler_topButton(self, -1, name = "scrollRight")
        self.scrollRight.createBackgroundImage()        
        self.scrollRight.Bind(wx.EVT_LEFT_UP, self.scrollRightClicked)      

            
        self.vSizerLeft.Add((0,5), 0, 0, 0)
        self.vSizerLeft.Add(self.scrollLeft, 0, 0, 0)

        self.vSizerRight.Add((0,5), 0, 0, 0)
        self.vSizerRight.Add(self.scrollRight, 0, 0, 0)



        self.hSizer0.Add((20,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizer0, 0, 0, 0)
        self.hSizer0.Add((20,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizerLeft, 0, 0, 0)
        self.hSizer0.Add((10,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizerContents, 0, wx.TOP, 10)
        self.hSizer0.Add((10,0), 0, 0, 0)
        self.hSizer0.Add(self.vSizerRight, 0, 0, 0)



        self.SetSizer(self.hSizer0)
        self.SetAutoLayout(1);  
        self.Layout()





    def loadChannel(self):
        self.totalItems = len(self.torrentList)
        self.setLastPage()
        self.addItems()
        self.erasevSizerContents()
        self.displayChannelContents()
        self.Refresh()


    def addItems(self):
        for i in range(self.totalItems):
            item = wx.StaticText(self, -1, self.torrentList[i]['name'][:self.torrentLength], wx.Point(0,0), wx.Size(300,18))
                        

            self.torrents.append(item)
            self.torrents[i].SetFont(wx.Font(FS_TORRENT,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.torrents[i].SetToolTipString(self.torrentList[i]['name'][:self.torrentLength])
            self.torrents[i].SetForegroundColour(self.torrentColour)
            self.torrents[i].Hide()



    def subscribeClicked(self, event):
        if self.subscribe.isToggled():
            sefl.votecast_db.addSubscription(self.GetParent().data['permid'])
            self.guiserver = GUITaskQueue.getInstance()
            self.guiserver.add_task(lambda:wx.CallAfter(self.guiUtility.frame.show_saved, self.guiUtility.frame.top_bg.newChannel), 0.2)
         
        




    def displayChannelContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.torrentsPerPage
            if numItems == 0:
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
        self.hSizer0.Layout()
        self.Layout()



    def setLastPage(self, lastPage=None):
        if lastPage is None:
            if self.totalItems % self.torrentsPerPage == 0:
                self.lastPage = self.totalItems / self.torrentsPerPage - 1
            else:
                self.lastPage = (self.totalItems - self.totalItems % self.torrentsPerPage) / self.torrentsPerPage
        else:
            self.lastPage=lastPage

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


