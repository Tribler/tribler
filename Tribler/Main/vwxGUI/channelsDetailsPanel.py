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

from Tribler.Core.Overlay.MetadataHandler import get_filename


from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Main.vwxGUI.tribler_topButton import *

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.bgPanel import *


from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.utils import videoextdefaults

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import *

from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename


# font sizes
if sys.platform == 'darwin':
    FS_SAVE_TITLE = 8
    FS_REMOVE_TITLE = 9
    FS_TITLE = 10
    FS_TITLE_SEL = 11 # size of title in expanded torrent
elif sys.platform == 'linux2':
    FS_SAVE_TITLE = 7
    FS_REMOVE_TITLE = 8
    FS_TITLE = 9
    FS_TITLE_SEL = 10
else:
    FS_SAVE_TITLE = 6
    FS_REMOVE_TITLE = 7
    FS_TITLE = 8
    FS_TITLE_SEL = 9 




class channelsDetailsPanel(bgPanel):
    def __init__(self, *args,**kwds):
        ##bgPanel.__init__(self,*args,**kwds)
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
        self.backgroundColour = wx.Colour(195,219,231)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        
        self.xpos = self.ypos = 0
        #self.tile = True
        #self.bitmap = None
        self.currentPage=0
        self.lastPage=0
        self.totalItems=11
        self.itemsPerPage=3
        self.torrentSpacing=(0,5) # space between torrents
        self.torrentLength=300
        self.torrentColour=(255,51,0)
        self.torrentColourSel=(0,105,156)
        self.files=[]

        self.fileList = None

        self.channelcast_db = self.utility.session.open_dbhandler(NTFY_CHANNELCAST)

        
        #wx.CallAfter(self.createBackgroundImage,"subpanel.png")



        self.gridmgr = self.guiUtility.standardGrid.gridManager


        self.addComponents()


        self.tile = True
        self.backgroundColour = wx.Colour(195,219,231)
        self.searchBitmap('subpanel.png')
        self.createBackgroundImage()




        ##self.refreshScrollButtons()
        self.Refresh()
        self.SetBackgroundColour(self.backgroundColour)
        self.Show()

        self.Refresh(True)
        self.Update()




    def addComponents(self):

        # main Sizer
        self.vSizer = wx.BoxSizer(wx.VERTICAL)

        # hSizer0
        self.hSizer0 = wx.BoxSizer(wx.HORIZONTAL)


        # hSizer1
        self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)

        # hSizerFiles
        self.hSizerFiles = wx.BoxSizer(wx.HORIZONTAL)


        # vSizerLeft
        self.vSizerLeft = wx.BoxSizer(wx.VERTICAL)
       
        # vSizerRight
        self.vSizerRight = wx.BoxSizer(wx.VERTICAL)

        # vSizerContents
        self.vSizerContents = wx.BoxSizer(wx.VERTICAL) ## list of items within a particular torrent
        self.vSizerContents.SetMinSize((260,10))


        # vSizerSave
        self.vSizerSave = wx.BoxSizer(wx.VERTICAL)

        # remove text
        self.removeText =wx.StaticText(self,-1,"Remove",wx.Point(0,0),wx.Size(50,10))        
        self.removeText.SetBackgroundColour(self.backgroundColour)
        self.removeText.SetForegroundColour(wx.BLACK)
        self.removeText.SetFont(wx.Font(FS_SAVE_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.removeText.SetMinSize((50,10))
        self.removeText.Hide()

        # scroll left
        self.scrollLeft = tribler_topButton(self, -1, name = "ScrollLeft")
        self.scrollLeft.createBackgroundImage()  
        self.scrollLeft.Bind(wx.EVT_LEFT_UP, self.scrollLeftClicked)      
 
        # scroll right
        self.scrollRight = tribler_topButton(self, -1, name = "ScrollRight")
        self.scrollRight.createBackgroundImage()        
        self.scrollRight.Bind(wx.EVT_LEFT_UP, self.scrollRightClicked)      


        # play
        #self.play = SwitchButton(self, -1, name = "playbig")
        #self.play.createBackgroundImage()        
        #self.play.setToggled(True)
        #self.play.Bind(wx.EVT_LEFT_UP, self.playClicked)      


        def is_playable_callback(torrent, playable):
            if playable[0]:
                self.fileList=playable[1]
                self.loadChannel(self.fileList)


                

        playable = self.guiUtility.standardDetails.torrent_is_playable(torrent = self.GetParent().torrent, callback=is_playable_callback)
        if playable[0]:
            #self.play_big.setToggled(True)
            self.fileList=playable[1]
            self.loadChannel(self.fileList)



        # save
        self.save = tribler_topButton(self, -1, name = "download")
        self.save.createBackgroundImage()        
        self.save.Bind(wx.EVT_LEFT_UP, self.saveClicked)      


        # save text
        self.saveText =wx.StaticText(self,-1,"Save",wx.Point(0,0),wx.Size(40,10))        
        self.saveText.SetBackgroundColour(self.backgroundColour)
        self.saveText.SetForegroundColour(wx.BLACK)
        self.saveText.SetFont(wx.Font(FS_SAVE_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.saveText.SetMinSize((40,10))


        self.hSizer0.Add((280,0), 0, 0, 0)
        self.hSizer0.Add(self.removeText, 0, 0, 0)

        #self.hSizer1.Add((10,0), 0, 0, 0)
        #self.hSizer1.Add(self.play, 0, wx.TOP, -10)
        #self.hSizer1.Add((5,0), 0, 0, 0)
        #self.hSizer1.Add(self.save, 0, wx.TOP, -10)


            
        self.vSizerLeft.Add((0,3), 0, 0, 0)
        self.vSizerLeft.Add(self.scrollLeft, 0, 0, 0)

        self.vSizerRight.Add((0,3), 0, 0, 0)
        self.vSizerRight.Add(self.scrollRight, 0, 0, 0)

        self.hSizerFiles.Add((5,0), 0, 0, 0)
        self.hSizerFiles.Add(self.vSizerLeft, 0, 0, 0)
        self.hSizerFiles.Add((10,0), 0, 0, 0)
        self.hSizerFiles.Add(self.vSizerContents, 0, 0, 0)
        self.hSizerFiles.Add((10,0), 0, 0, 0)
        self.hSizerFiles.Add(self.vSizerRight, 0, 0, 0)

        self.vSizerSave.Add((0,10), 0, 0, 0)
        self.vSizerSave.Add(self.save, 0, 0, 0)
        self.vSizerSave.Add((0,5), 0, 0, 0)
        self.vSizerSave.Add(self.saveText, 0, wx.LEFT, -5)

        self.hSizerFiles.Add((38,0), 0, 0, 0)
        self.hSizerFiles.Add(self.vSizerSave, 0, 0, 0)

        #self.loadChannel()

        self.vSizer.Add((0,5), 0, 0, 0)
        self.vSizer.Add(self.hSizer0, 0, 0, 0)     

        #self.vSizer.Add((0,0), 0, 0, 0)
        #self.vSizer.Add(self.hSizer1, 0, 0, 0)     

        self.vSizer.Add((0,0), 0, 0, 0)
        self.vSizer.Add(self.hSizerFiles, 0, 0, 0)     


        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.Layout()




    

    def loadChannel(self, files=None):
        self.totalItems = len(files)
        if self.GetParent().isMine():
            self.removeText.SetLabel("Remove")
        else:
            self.removeText.SetLabel("")
        self.setLastPage()
        self.addItems(files)
        self.displayChannelContents()


    def addItems(self, files=None):
        for i in range(self.totalItems):
            item = fileItem(self)
            if files == None:
                item.setTitle("")
            else:
                item.setTitle(files[i])
            self.files.append(item)
            self.files[i].Hide()




    def displayChannelContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.itemsPerPage
            if numItems == 0:
                numItems = self.itemsPerPage
        else:
            numItems = self.itemsPerPage    

        for i in range(numItems):
            self.vSizerContents.Add(self.files[self.currentPage*self.itemsPerPage+i], 0, 0, 0)
            self.files[self.currentPage*self.itemsPerPage+i].Show()
            # self.vSizerContents.Add(self.torrentSpacing, 0, 0, 0)
        self.vSizerContents.Layout()
        self.refreshScrollButtons()
        self.Layout()
        self.Refresh()



    def erasevSizerContents(self):
        if self.currentPage == self.lastPage:
            numItems = self.totalItems % self.itemsPerPage
        else:
            numItems = self.itemsPerPage    
        for i in range(numItems):
            self.files[self.currentPage*self.itemsPerPage+i].Hide()
        self.vSizerContents.Clear()
        self.vSizerContents.Layout()
        self.vSizer.Layout()
        self.Layout()


    def playClicked(self, event):
        if self.play.isToggled():

            ds = self.GetParent().torrent.get('ds')

            videoplayer = self._get_videoplayer(exclude=ds) 
            videoplayer.stop_playback() # stop current playback
            videoplayer.show_loading()

            ##self.play_big.setToggled()
            ##self.guiUtility.buttonClicked(event)
            if ds is None:
                self.guiUtility.standardDetails.download(vodmode=True)
            else:
                self.play(ds)

            self.guiUtility.standardDetails.setVideodata(self.guiUtility.standardDetails.getData())
            self._get_videoplayer(exclude=ds).videoframe.get_videopanel().SetLoadingText(self.guiUtility.standardDetails.getVideodata()['name'])
            if sys.platform == 'darwin':
                self._get_videoplayer(exclude=ds).videoframe.show_videoframe()
                self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Refresh()
                self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Layout()

    def play(self,ds):


        self._get_videoplayer(exclude=ds).play(ds)


    def _get_videoplayer(self, exclude=None):
        """
        Returns the VideoPlayer instance and ensures that it knows if
        there are other downloads running.
        """
        other_downloads = False
        for ds in self.gridmgr.get_dslist():
            if ds is not exclude and ds.get_status() not in (DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR):
                other_downloads = True
                break
        
        videoplayer = VideoPlayer.getInstance()
        videoplayer.set_other_downloads(other_downloads)
        return videoplayer



    def saveClicked(self, event):
        self.guiUtility.frame.standardDetails.download(self.GetParent().torrent)






    def setLastPage(self, lastPage=None):
        if lastPage is None:
            if self.totalItems % self.itemsPerPage == 0:
                self.lastPage = self.totalItems / self.itemsPerPage - 1
            else:
                self.lastPage = (self.totalItems - self.totalItems % self.itemsPerPage) / self.itemsPerPage
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

    def removeClicked(self, event):
        self.channelcast_db.deleteOwnTorrent(self.GetParent().torrent['infohash'])
        cd = self.GetParent().GetParent()
        cd.removeTorrent(self.GetParent().index)

    def refreshItems(self):
        for i in range(self.totalItems):
            if self.files[i].selected:
                self.files[i].select()
            else:
                self.files[i].deselect()


    def deselectAll(self):
        for i in range(self.totalItems):
            self.files[i].deselect()
        

class fileItem(bgPanel):
    def __init__(self, *args,**kwds):
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
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility        

        self.gridmgr = self.GetParent().gridmgr


        self.fileColour=(255,51,0)
        self.fileColourSel=(0,105,156)

        if sys.platform == 'win32':
            self.minsize=(250,18)
        else:
            self.minsize=(200,18)


        self.SetMinSize(self.minsize)
        self.selected=False
        self.addComponents()


        self.tile = True
        self.backgroundColour = wx.Colour(195,219,231)
        self.searchBitmap('subpanel.png')
        self.createBackgroundImage()


        self.SetBackgroundColour((195, 219, 231))
        self.Refresh()


    def addComponents(self):
        # hSizer
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)

        # file title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),self.minsize)
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))        
        self.title.SetForegroundColour(self.fileColour)
        self.title.SetMinSize(self.minsize)

        # play button
        if sys.platform != 'win32':
            self.play = tribler_topButton(self, -1, name='channels_play')
        else:
            self.play = tribler_topButton(self, -1, name='channels_play_win')

        self.play.Bind(wx.EVT_LEFT_UP, self.play_clicked)
        self.play.Hide()

        self.hSizer.Add(self.play, 0, 0, 0)
        self.hSizer.Add((10,0), 0, 0, 0)
        self.hSizer.Add(self.title, 0, 0, 0)

        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh()

        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)

        if sys.platform != 'linux2':
            self.title.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

    def setTitle(self, title):
        self.title.SetLabel(title[:200])
        self.Refresh()       

    def mouseAction(self, event):
        if event.LeftUp():
            self.play_clicked()

        if event.Entering():
            self.title.SetForegroundColour(self.fileColourSel)
            self.play.Show()
            self.hSizer.Layout()
        elif event.Leaving():
            self.title.SetForegroundColour(self.fileColour)
            self.play.Hide()
            self.hSizer.Layout()


        self.Refresh()


    def play_clicked(self):
        ds = self.GetParent().GetParent().torrent.get('ds')
        selectedinfilename = self.title.GetLabel()

        if ds is not None:
            self._get_videoplayer(exclude=ds).play(ds, selectedinfilename)

        else:
            torrent = self.GetParent().GetParent().torrent
            if 'torrent_file_name' not in torrent:
                torrent['torrent_file_name'] = get_filename(torrent['infohash']) 
            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
            tdef = TorrentDef.load(torrent_filename)

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()

            self._get_videoplayer().start_and_play(tdef, dscfg, selectedinfilename)


        videoplayer = self._get_videoplayer(exclude=ds) 
        videoplayer.stop_playback() # stop current playback
        videoplayer.show_loading()


        self.guiUtility.standardDetails.setVideodata(self.guiUtility.standardDetails.getData())
        self._get_videoplayer(exclude=ds).videoframe.get_videopanel().SetLoadingText(self.guiUtility.standardDetails.getVideodata()['name'])
        if sys.platform == 'darwin':
            self._get_videoplayer(exclude=ds).videoframe.show_videoframe()
            self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Refresh()
            self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Layout()


    def _get_videoplayer(self, exclude=None):
        """
        Returns the VideoPlayer instance and ensures that it knows if
        there are other downloads running.
        """
        other_downloads = False
        for ds in self.gridmgr.get_dslist():
            if ds is not exclude and ds.get_status() not in (DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR):
                other_downloads = True
                break
        
        videoplayer = VideoPlayer.getInstance()
        videoplayer.set_other_downloads(other_downloads)
        return videoplayer


