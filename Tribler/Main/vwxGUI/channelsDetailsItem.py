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
from Tribler.Main.vwxGUI.tribler_topButton import *

from Tribler.Core.simpledefs import *


from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.channelsDetailsPanel import channelsDetailsPanel
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin




# font sizes
if sys.platform == 'darwin':
    FS_TITLE = 10
    FS_TITLE_SEL = 11 # size of title in expanded torrent
elif sys.platform == 'linux2':
    FS_TITLE = 9
    FS_TITLE_SEL = 10
else:
    FS_TITLE = 9
    FS_TITLE_SEL = 10 




class channelsDetailsItem(wx.Panel):
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
        self.backgroundColourSel = wx.Colour(195,219,231)
        self.backgroundColour = wx.Colour(216,233,240)


        self.channelcast_db = self.utility.session.open_dbhandler(NTFY_CHANNELCAST)


        self.SetBackgroundColour(self.backgroundColour)
        self.expandedValue = 377
        self.SetMinSize((self.expandedValue,18))
        self.SetSize((self.expandedValue,18))
        self.torrentColour=(255,51,0)
        self.torrentColourSel=(0,105,156)
        self.expandedSize=(self.expandedValue,100)
        self.panelSize=(self.expandedValue,self.expandedSize[1]-18)
        self.index = 0 # used for torrent deletion
        self.selected=False
        self.subpanel=None
        self.torrent = None
        self.addComponents()
        self.Refresh()



    def addComponents(self):


        # main sizer
        self.vSizer = wx.BoxSizer(wx.VERTICAL)

        # hSizer
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
 
        

        # torrent title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(self.expandedValue,18))
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))        
        self.title.SetForegroundColour(self.torrentColour)
        self.title.SetMinSize((self.expandedValue-31,18))
       
        # save button
        #self.save = tribler_topButton(self, -1, name = "downloadFromChannel")
        #self.save.setBackground(self.backgroundColourSel)
        #self.save.Bind(wx.EVT_LEFT_UP, self.saveClicked)
        #self.save.Hide()

        # remove button
        self.remove = tribler_topButton(self, -1, name = "reemove")
        self.remove.setBackground(self.backgroundColourSel)
        self.remove.Bind(wx.EVT_LEFT_UP, self.removeClicked)
        self.remove.Hide()


        self.hSizer.Add(self.title, 0, wx.LEFT, 5)
        self.hSizer.Add(self.remove, 0, wx.TOP, 7)

        self.vSizer.Add(self.hSizer, 0, 0, 0)

        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh()

        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

        if sys.platform != 'linux2':
            self.title.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)


        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)



    def setTitle(self, title):
        self.title.SetLabel(title)
        self.Refresh()


    def setTorrent(self, torrent):
        self.torrent = torrent

    def setMine(self,b):
        self.mine = b

    def isMine(self):
        if self.mine is not None:
            return self.mine
        else:
            return False


    def mouseAction(self, event):
        event.Skip()

        tc = self.torrentColourSel
        bc = self.backgroundColourSel

        if event.Entering():
            tc = self.torrentColourSel
            bc = self.backgroundColourSel
        elif event.Leaving() and not self.selected:
            tc = self.torrentColour
            bc = self.backgroundColour

        self.title.SetForegroundColour(tc)
        self.SetBackgroundColour(bc)
        wx.CallAfter(self.Refresh)


        if event.LeftUp():
            if sys.platform == 'darwin':
                self.GetParent().deselectAllExceptSelected(self.index)
                wx.Yield()
            else:
                self.GetParent().deselectAll()
            self.select()


            self.GetParent().parent.select()
            self.GetParent().parent.parent.showSelectedChannel()
        self.refresh()                                    

    def SetIndex(self, index):    
        self.index = index

    def IncrementIndex(self): # used by channelsDetails
        self.index+=1

    def saveClicked(self, event):
        self.guiUtility.frame.standardDetails.download(self.torrent)

    def removeClicked(self, event):
        self.deselect()
        self.channelcast_db.deleteOwnTorrent(self.torrent['infohash'])
        cd = self.GetParent()
        cd.removeTorrent(self.index)




    def select(self): # select an item in the list
        self.SetMinSize(self.expandedSize)
        if not self.subpanel or sys.platform != 'darwin':
            self.subpanel = channelsDetailsPanel(self,-1)
            self.subpanel.SetMinSize(self.panelSize)
            self.subpanel.SetSize(self.panelSize)
            self.subpanel.SetBackgroundColour(self.backgroundColourSel)
            self.SetBackgroundColour(self.backgroundColourSel)
            self.guiUtility.selectTorrent(self.torrent)

            self.vSizer.Add(self.subpanel, 1, 0, 0)
            self.title.SetForegroundColour(self.torrentColourSel)
            self.title.SetFont(wx.Font(FS_TITLE_SEL,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))        
            if sys.platform == 'win32':
                wx.CallAfter(self.vSizer.Layout)
            else:
                self.vSizer.Layout()
            if self.isMine():
                self.remove.Show()
            else:
                self.remove.Hide()

            

        self.selected = True



    def deselect(self): # deselect an item
        self.SetMinSize((self.expandedValue,18))

        if sys.platform == 'darwin':
            if self.subpanel:
                self.subpanel.Hide()
                self.subpanel.DestroyChildren()
                self.subpanel.Destroy()
                self.subpanel = None
        else:
            if self.subpanel:
                self.subpanel.Destroy()
        
        self.title.SetForegroundColour(self.torrentColour)
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))        
        self.SetBackgroundColour(self.backgroundColour)
        self.selected = False

        self.remove.Hide()
        self.Refresh()




    def refresh(self):
        self.GetParent().vSizerContents.Layout()
