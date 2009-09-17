# Written by Richard Gwin 

import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from copy import deepcopy
from wx.lib.stattext import GenStaticText as StaticText

from Tribler.Core.API import *
from Tribler.Core.Utilities.unicode import *
from Tribler.Core.Utilities.utilities import *
# LAYERVIOLATION
from Tribler.Core.Overlay.MetadataHandler import get_filename

from Tribler.Core.simpledefs import *

from Tribler.Main.Utility.constants import * 
from Tribler.Main.Utility import *
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.Progress import ProgressBar
from Tribler.Video.utils import videoextdefaults
from bgPanel import *
from font import *
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles

from Tribler.Main.Utility.constants import * 
from Tribler.Main.Utility import *
from Tribler.__init__ import LIBRARYNAME

DEBUG = False

# font sizes


if sys.platform == 'darwin':
    FS_MY_CHANNEL_TITLE = 13
    FONTFAMILY_MY_CHANNEL=wx.SWISS
    FS_TITLE = 10
    FS_PERC = 9
    FS_SPEED = 9
else:
    FS_MY_CHANNEL_TITLE = 11
    FONTFAMILY_MY_CHANNEL=wx.SWISS
    FS_TITLE = 8
    FS_PERC = 7
    FS_SPEED = 7
    

class SubscriptionsItemPanel(wx.Panel):
    def __init__(self, parent, keyTypedFun = None, name='regular'):

        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
           
        self.guiserver = parent.guiserver
        
        self.data = None
        self.titleLength = 40 # num characters
        self.selected = False
        self.name = name

        self.subscribed = False # whether subscibed to particular channel
        self.publisher_id = None
        self.publisher_name = None
        self.num_votes = None # how many subscriptions to this channel

        self.mychannel = False # whether this panel is my own channel

        self.backgroundColour = wx.WHITE
        self.selectedColour = (216,233,240)
        self.channelTitleSelectedColour = wx.BLACK
        self.channelTitleUnselectedColour = wx.BLACK
       
        self.channelsDetails = self.guiUtility.frame.channelsDetails

        self.session = self.utility.session
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.vcdb = self.session.open_dbhandler(NTFY_VOTECAST)
        
        self.torrentList = [] # list of torrents within the channel

        self.index=-1
 
        self.addComponents()
            
        self.gui_server = GUITaskQueue.getInstance()

        self.selected = False
        self.Show()
        self.Refresh()
        self.Layout()
       
    def addComponents(self):
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)        
        self.Show(False)
        self.SetMinSize((660,22))
        self.vSizerOverall = wx.BoxSizer(wx.VERTICAL)
        imgpath = os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","line4.png")
        self.line_file = wx.Image(imgpath, wx.BITMAP_TYPE_ANY)            
        self.hLine = wx.StaticBitmap(self, -1, wx.BitmapFromImage(self.line_file))
        if sys.platform == 'win32':
            self.vSizerOverall.Add(self.hLine, 0, 0, 0)
        else:
            self.vSizerOverall.Add(self.hLine, 0, wx.EXPAND, 0)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vSizerOverall.Add(self.hSizer, 0 , wx.EXPAND, 0)
        self.SetBackgroundColour(wx.WHITE)
       
        # Add Spacer
        self.hSizer.Add([10,0],0,wx.FIXED_MINSIZE,0)        

        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(240,16))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((240,16))

        #self.vSizerTitle = wx.BoxSizer(wx.VERTICAL)
        #self.vSizerTitle.Add((


        self.hSizer.Add(self.title, 0, wx.TOP,3)

        # Add subscription button
        ##self.SubscriptionButton = SwitchButton(self, -1, name = "SubscriptionButton")
        ##self.SubscriptionButton.Bind(wx.EVT_LEFT_UP, self.SubscriptionClicked)
        ##self.hSizer.Add(self.SubscriptionButton, 0, wx.TOP, 1)


        ##self.hSizer.Add((10,0), 0, 0, 0)

         
        # Add Refresh        
        self.SetSizer(self.vSizerOverall);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        wl = [self]
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)             
            
    def getColumns(self):
        return [{'sort':'name', 'reverse':True, 'title':'My Subscriptions', 'width':242,'tip':self.utility.lang.get('C_filename'), 'order':'down'}
                ]     
                  
    def refreshData(self):
        self.setData(self.data)
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,0),wx.LI_VERTICAL)
        self.vSizer1.Add(vLine, 0, wx.LEFT|wx.RIGHT, 3)
       
    def setData(self, data):
        if threading.currentThread().getName() != "MainThread":
            print >>sys.stderr,"cip: setData called by nonMainThread!",threading.currentThread().getName()
            print_stack()


        if self.data is None:
            oldinfohash = None
        else:
            oldinfohash = self.data[0]
     
        self.data = data
        
        if data is None:
            self.title.SetLabel("")
            self.title.Hide()
            ##self.SubscriptionButton.Hide()
            self.hLine.Show()
            self.Refresh()
            return 
        else:
            for child in self.GetChildren():
                child.Show()
        
          

        if data == "mychannel":
            self.mychannel = True
            self.selectedColour = wx.Colour(216,233,240)
            self.backgroundColour = wx.Colour(255,255,255)
            self.SetBackgroundColour(self.backgroundColour)
            self.channelTitleSelectedColour = wx.BLACK


            self.publisher_id = self.utility.session.get_permid()
            self.num_votes = self.channelcast_db.getSubscribersCount(self.utility.session.get_permid())

            # get torrent list
            torrentList = self.channelcast_db.getTorrentsFromPublisherId(self.publisher_id)
            self.torrentList = torrentList

            # convert torrentList to proper format (dictionnary)
            torrent_list = []
            for item in self.torrentList:
                torrent = dict(zip(self.torrent_db.value_name_for_channel, item))
                torrent_list.append(torrent)
            self.torrentList = torrent_list
            if self.num_votes == 0:
                self.publisher_name = "My Channel (No subscribers)"
            elif self.num_votes == 1:
                self.publisher_name = "My Channel (1 subscriber)" 
            else:
                self.publisher_name = "My Channel (%s subscribers)" % self.num_votes 

            self.setMyTitle()

            self.SetMinSize((660,32))

        else:
            self.mychannel = False
            if data and oldinfohash != self.data[0]:
                title = data[1][:self.titleLength]
                self.title.Show()
                self.title.SetLabel(title)
                self.title.Wrap(self.title.GetSize()[0])
                self.title.SetToolTipString(data[1])

         
            self.publisher_id, self.publisher_name, self.num_votes = data

            # determine whether subscribed
            self.setSubscribed()

            # get torrent list
            torrentList = self.channelcast_db.getTorrentsFromPublisherId(self.publisher_id)
            self.torrentList = torrentList



            # convert torrentList to proper format (dictionnary)
            torrent_list = []
            for item in self.torrentList:
                torrent = dict(zip(self.torrent_db.value_name_for_channel, item))
                torrent_list.append(torrent)
            self.torrentList = torrent_list



               
        self.Layout()
        self.Refresh()
        self.GetContainingSizer().Layout()
        self.parent.Refresh()
        

    def setSubscribed(self):
        if self.vcdb.hasSubscription(self.publisher_id, bin2str(self.utility.session.get_permid())):
            self.subscribed = True
        else:
            self.subscribed = False
        

    def setTorrentList(self, torrentList):
        self.torrentList = torrentList


    def setMyTitle(self):
        title = "My channel (%s)" % len(self.torrentList)
        self.title.SetLabel(title)
        self.title.Show()
        self.title.SetFont(wx.Font(FS_MY_CHANNEL_TITLE,FONTFAMILY_MY_CHANNEL,FONTWEIGHT,wx.NORMAL, False,FONTFACE))
        self.title.Wrap(self.title.GetSize()[0])
        self.title.SetToolTipString(title)



    def select(self, i=None, j=None):
        self.selected = True        
        if self.isMyChannel():
            self.title.SetFont(wx.Font(FS_MY_CHANNEL_TITLE,FONTFAMILY_MY_CHANNEL,FONTWEIGHT,wx.BOLD, False,FONTFACE))
        else:
            self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))
        colour = self.selectedColour
        channelColour = self.channelTitleSelectedColour
        self.title.SetBackgroundColour(colour)
        self.title.SetForegroundColour(channelColour)
        self.SetBackgroundColour(colour)
        self.Refresh()

        
    def deselect(self, i=None, j=None):
        self.selected = False
        if self.isMyChannel():
            self.title.SetFont(wx.Font(FS_MY_CHANNEL_TITLE,FONTFAMILY_MY_CHANNEL,FONTWEIGHT,wx.NORMAL, False,FONTFACE))
        else:
            self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        colour = self.backgroundColour
        channelColour = self.channelTitleUnselectedColour
        self.title.SetBackgroundColour(colour)
        self.title.SetForegroundColour(channelColour)
        self.SetBackgroundColour(colour)
        self.Refresh()
       

    def SubscriptionClicked(self, event):
        if self.SubscriptionButton.isToggled():
            vote = {'mod_id' : self.publisher_id ,'voter_id' : self.utility.session.get_permid() , 'vote' : 2, 'time_stamp' : 0}
            self.vcdb.addVote(vote)
            self.SzbscriptionText.SetLabel("Remove \nSubscription")
            self.SubscriptionButton.setToggled(False)
        else:
            self.hideElements()
            self.erasevSizerContents()
            self.vcdb.deleteVote(self.publisher_id,self.utility.session.get_permid())

            self.parent.setData(None)
            self.parent.Refresh()
            self.parent.parent.gridManager.refresh()

        self.parent.setSubscribed() # reloads subscription state of the parent
        

    def isSubscribed(self):
        return self.subscribed


    def isMyChannel(self):
        return False


    def mouseAction(self, event):

        event.Skip()
        colour = self.selectedColour
        channelColour = self.channelTitleSelectedColour

        if self.data is None:
            colour = self.backgroundColour
            channelColour = self.channelTitleUnselectedColour
        else:
            if event.Entering() and self.data is not None:
                colour = self.selectedColour
                channelColour = self.channelTitleSelectedColour
            elif event.Leaving() and self.selected == False:
                colour = self.backgroundColour
                channelColour = self.channelTitleUnselectedColour
            self.title.SetBackgroundColour(colour)
            self.title.SetForegroundColour(channelColour)
            self.SetBackgroundColour(colour)


        if not self.data:
            return



        
        if event.LeftUp():
            self.parent.deselectAllChannels()
            self.guiUtility.standardOverview.data['channelsMode']['grid'].deselectAll()
            self.guiUtility.standardOverview.data['channelsMode']['grid2'].deselectAll()
            self.guiUtility.standardOverview.data['channelsMode']['grid3'].deselectAll()
            self.select()
            self.guiUtility.frame.top_bg.indexMyChannel=-1
            self.guiUtility.frame.top_bg.indexPopularChannels=-1
            self.guiUtility.frame.top_bg.indexSubscribedChannels=self.index
            self.channelsDetails.loadChannel(self, self.torrentList, self.publisher_id, self.publisher_name, True)


        wx.CallAfter(self.Refresh)

        self.SetFocus()

    def setIndex(self, index):
        self.index=index

            
            
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.BLUE))
        
        dc.Clear()
        
        if self.title:
#            print 'tb > self.title.GetLabel() = %s' % self.title.GetLabel()
            dc.SetFont(wx.Font(14,FONTFAMILY,FONTWEIGHT, wx.BOLD, False,FONTFACE))
            dc.SetTextForeground('#007303')
#            dc.DrawText(self.title.GetLabel(), 0, 0)
            dc.DrawText('online', 38, 64)
            self.title.Hide()


    def guiservthread_loadMetadata(self, torrent,torrent_filename):
        """ Called by separate non-GUI thread """
        
        isVideo = False 
        try:
            if os.path.isfile(torrent_filename):
                if DEBUG:
                    print >>sys.stderr,"lip: Reading",torrent_filename,"to see if contains video"
                tdef = TorrentDef.load(torrent_filename)
                isVideo = bool(tdef.get_files(exts=videoextdefaults))
        except:
            print_exc()
            
        if torrent['infohash'] == self.data['infohash']:
            self.containsvideo = isVideo
            wx.CallAfter(self.metadata_loaded,torrent,None)

             
    def metadata_loaded(self,torrent,metadata):
        """ Called by GUI thread """
        try:
            if torrent['infohash'] == self.data['infohash']:
                self.library_play.setEnabled(self.containsvideo)
        except wx.PyDeadObjectError:
            pass
