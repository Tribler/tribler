# Written by Richard Gwin

import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack

from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.Utilities.unicode import *
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
import cStringIO
import string

from copy import deepcopy
import cStringIO
import mimetypes
import tempfile

from font import *
from Tribler.Core.simpledefs import *

from Tribler.Main.vwxGUI.FilesItemDetailsSummary import FilesItemDetailsSummary


from Tribler.__init__ import LIBRARYNAME


DEBUG = False

# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 10
    FS_FILETITLE_SEL = 12 # size of title in expanded torrent
    FS_FILESIZE = 10
    FS_SEEDERS = 10
    FS_LEECHERS = 10
    TITLELENGTH = 80
    TITLEHEIGHT = 18
    TITLEHEIGHTEXP = 18

elif sys.platform == 'linux2':
    FS_FILETITLE = 8
    FS_FILETITLE_SEL = 10 
    FS_FILESIZE = 8
    FS_SEEDERS = 8
    FS_LEECHERS = 8
    TITLELENGTH = 164
    TITLEHEIGHT = 12
    TITLEHEIGHTEXP = 18
else:
    FS_FILETITLE = 8
    FS_FILETITLE_SEL = 10 
    FS_FILESIZE = 8
    FS_SEEDERS = 8
    FS_LEECHERS = 8
    TITLELENGTH = 80
    TITLEHEIGHT = 18
    TITLEHEIGHTEXP = 18


class ItemPanel(wx.Panel): #torrent item
    """
    This Panel shows one content item inside the GridPanel
    """
    def __init__(self, parent, name='regular'):
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.session = self.utility.session
        self.parent = parent
        self.data = None
        self.datacopy = {}
        self.titleLength = TITLELENGTH # num characters
        self.selected = False
        self.summary = None
        self.titleMaxLength=None

        if self.parent.GetName() == 'filesGrid':
            self.listItem = (self.parent.viewmode == 'list')
            self.guiserver = parent.guiserver
        else:
            self.listItem = True
            self.guiserver = GUITaskQueue.getInstance()


        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.vcdb = self.session.open_dbhandler(NTFY_VOTECAST)
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)

        self.w1 = 415
        self.w2 = 99
        self.w3 = 80
        self.w4 = 67

        self.h1 = TITLEHEIGHT

        if sys.platform == 'linux2':
            self.titleMaxLength=405
        elif sys.platform == 'darwin':
            self.titleMaxLength=395
        else:
            self.titleMaxLength=400

        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()

        self.type = 'torrent' # channel or torrent

        # subscription state
        self.subscribed = False
        
        self.name = name

    def addComponents(self):
        
        self.Show(False)
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
       
        self.SetBackgroundColour(self.unselectedColour)
       
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        
        
        self.SetMinSize((660,22))

        self.vSizerOverall = wx.BoxSizer(wx.VERTICAL)

        # line
        imgpath = os.path.join(self.utility.getPath(),LIBRARYNAME ,"Main","vwxGUI","images","5.0","line3.png")
        self.line_file = wx.Image(imgpath, wx.BITMAP_TYPE_ANY)            
        self.hLine = wx.StaticBitmap(self, -1, wx.BitmapFromImage(self.line_file))


        self.vSizerOverall.Add(self.hLine, 0, 0, 0)

        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            
            

        self.hSizer.Add([10,5],0,wx.FIXED_MINSIZE,0)
        self.vSizerOverall.Add(self.hSizer, 0, wx.EXPAND, 0)

        # Add title
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(300,self.h1))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetForegroundColour(wx.BLACK)
        self.title.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((300,self.h1))
        self.title.SetSize((300,self.h1))

        self.hSizer.Add(self.title, 0,wx.TOP|wx.BOTTOM, 3)  
  
        self.hSizer.Add([5,0],0 ,0 ,0)



        self.fileSize = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(self.w2-5,18), wx.ALIGN_LEFT | wx.ST_NO_AUTORESIZE)        
        self.fileSize.SetBackgroundColour(wx.WHITE)
        self.fileSize.SetForegroundColour(wx.BLACK) 
        self.fileSize.SetFont(wx.Font(FS_FILESIZE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.fileSize.SetMinSize((self.w2-5,18))

        self.hSizer.Add(self.fileSize, 0,wx.TOP|wx.BOTTOM, 2)  

        self.hSizer.Add([5,0],0 ,0 ,0)


        # seeders
        self.seeders = wx.StaticText(self, -1, "", wx.Point(0,0), wx.Size(self.w3-5,18))
        self.seeders.SetBackgroundColour(wx.WHITE)
        self.seeders.SetForegroundColour(wx.BLACK) 
        self.seeders.SetFont(wx.Font(FS_SEEDERS,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.seeders.SetMinSize((self.w3-5,18))


        # leechers
        self.leechers = wx.StaticText(self, -1, "", wx.Point(0,0), wx.Size(self.w4-5,18))
        self.leechers.SetBackgroundColour(wx.WHITE)
        self.leechers.SetForegroundColour(wx.BLACK) 
        self.leechers.SetFont(wx.Font(FS_LEECHERS,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.leechers.SetMinSize((self.w4-5,18))

        self.hSizer.Add(self.seeders, 0,wx.TOP|wx.BOTTOM, 2)  

        self.hSizer.Add([5,0],0 ,0 ,0)

        self.hSizer.Add(self.leechers, 0,wx.TOP|wx.BOTTOM, 2)  


        self.hSizerSummary = wx.BoxSizer(wx.HORIZONTAL) ##
        self.vSizerOverall.Add(self.hSizerSummary, 0, wx.FIXED_MINSIZE|wx.EXPAND, 0) ##           
 
        if sys.platform != 'linux2':
            self.title.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            self.fileSize.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            self.seeders.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
            self.leechers.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)


           
        self.SetSizer(self.vSizerOverall);
            
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        # 2.8.4.2 return value of GetChildren changed
        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            
    def getColumns(self):
        return [{'sort':'name', 'reverse':True, 'title':'Name', 'width':self.w1,'tip':self.utility.lang.get('C_filename')},
                {'sort':'length', 'title':'Size', 'width':self.w2, 'tip':self.utility.lang.get('C_filesize')},
                {'sort':'length', 'title':'Seeders', 'width':self.w3, 'tip':self.utility.lang.get('C_uploaders')},
                {'sort':'length', 'title':'Leechers', 'width':self.w4, 'tip':self.utility.lang.get('C_downloaders')},
                ]


    def _setTitle(self, title):
        self.title.SetToolTipString(title)
        i=0
        try:
            while self.title.GetTextExtent(title[:i])[0] < self.titleMaxLength and i <= len(title):
                i=i+1
            self.title.SetLabel(title[:(i-1)])
        except:
            self.title.SetLabel(title)
        self.Refresh()       

    def setTitle(self, title):
        """
        Simple wrapper around _setTitle to handle unicode bugs
        """
        self.storedTitle = title
        try:
            self._setTitle(title)
        except UnicodeDecodeError:
            self._setTitle(`title`)


                 
    def setData(self, data):
        
        self.data = data
        
        if not data:
            data = {}

        try:
            if self.selected:
                if DEBUG :
                    print >> sys.stderr , "Torrent already selected. Not refreshing individual item."
                return
        except:
            pass


        if data.get('name'):
            titlefull = data['name']
            title = data['name'][:self.titleLength]
            if sys.platform == 'win32':
                title = string.replace(title,'&','&&')
            self.title.Enable(True)
            self.title.Show()
            self.setTitle(title)
            self.title.SetToolTipString(titlefull)
               


            if self.listItem:
                self.fileSize.Enable(True)
                if data.get('web2'):
                    self.fileSize.SetLabel('%s s' % data['length'])
                else:
                    self.fileSize.SetLabel(self.utility.size_format(data['length']))

                if data['num_seeders'] < 0:
                    self.seeders.SetForegroundColour((200, 200, 200))
                    self.seeders.SetLabel("?")                
                else:
                    self.seeders.SetForegroundColour(wx.BLACK)
                    self.seeders.SetLabel("%s " % data['num_seeders'])                

                if data['num_leechers'] < 0:
                    self.leechers.SetForegroundColour((200, 200, 200))
                    self.leechers.SetLabel("?")                
                else:
                    self.leechers.SetForegroundColour(wx.BLACK)
                    self.leechers.SetLabel("%s " % data['num_leechers'])                
                self.hLine.Show()

                
                
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            self.title.Hide()
            self.seeders.SetLabel('')                
            self.leechers.SetLabel('')                
            if self.listItem:
                self.fileSize.SetLabel('')
 

        self.Layout()

    def select(self, rowIndex, colIndex, pageIndex=-1, panelsPerRow=-1, rowsPerPage=-1):
        # if pageIndex is given, we assume panelsPerRow and rowsPerPage are given as well,
        # and set click_position, a 0-indexed value indicating the rank of the panel
        if pageIndex>-1:
             panelsPerPage = panelsPerRow * rowsPerPage
             self.data["click_position"] = pageIndex * panelsPerPage + rowIndex * panelsPerRow + colIndex
        self.selected = True

        if self.data and self.data.get('myDownloadHistory'):
            colour = self.guiUtility.selectedColour
        elif self.data and self.data.get('query_torrent_was_requested',False):
            colour = self.guiUtility.selectedColourPending
        else:
            colour = self.guiUtility.selectedColour

        self.title.SetBackgroundColour(colour)
        self.title.SetFont(wx.Font(FS_FILETITLE_SEL,FONTFAMILY,FONTWEIGHT,wx.BOLD,False,FONTFACE))
        self.title.SetMinSize((self.w1-5, TITLEHEIGHTEXP))
        self.title.SetSize((self.w1-5, TITLEHEIGHTEXP))
        
        
        self.SetBackgroundColour(colour)
        self.fileSize.SetBackgroundColour(colour)
        self.toggleItemDetailsSummary(True)
        if self.type == 'torrent':
            self.guiUtility.standardOverview.selectedTorrent = self.data['infohash']
        else: # channel
            self.guiUtility.standardOverview.selectedChannel = self.data['infohash']
        self.Refresh()
        self.guiUtility.standardOverview.SetFocus()
        
    def deselect(self, rowIndex, colIndex):

        self.selected = False
        self.hLine.Show()
        self.vSizerOverall.Layout()
        downloading = self.data and self.data.get('myDownloadHistory')
        if rowIndex % 2 == 0 or not self.listItem:
            if downloading:
                colour = self.guiUtility.unselectedColour
            else:
                colour = self.guiUtility.unselectedColour
        else:
            if downloading:
                colour = self.guiUtility.unselectedColour2
            else:
                colour = self.guiUtility.unselectedColour2
        
            
        self.title.SetBackgroundColour(colour)
        self.title.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((self.w1-5, TITLEHEIGHT))
        self.title.SetSize((self.w1-5, TITLEHEIGHT))

        self.SetBackgroundColour(colour)
        self.fileSize.SetBackgroundColour(colour)
        self.seeders.SetBackgroundColour(colour)
        self.leechers.SetBackgroundColour(colour)
       
        self.toggleItemDetailsSummary(False)
        self.Refresh()
        
            
            
    def setIndex(self, index):
        self.index=index

       
    def mouseAction(self, event):   

        event.Skip()
        colour = wx.Colour(216,233,240)

        if self.data is None:
            colour = self.guiUtility.unselectedColour

        elif event.Entering() and self.data is not None:
            colour = self.guiUtility.selectedColour
    
        elif event.Leaving() and self.selected == False:
            colour = self.guiUtility.unselectedColour


        self.title.SetBackgroundColour(colour)
        self.fileSize.SetBackgroundColour(colour)
        self.seeders.SetBackgroundColour(colour)
        self.leechers.SetBackgroundColour(colour)
        self.SetBackgroundColour(colour)
        wx.CallAfter(self.Refresh)


        if self.data and (event.LeftUp() or event.RightDown()):
            self.guiUtility.standardOverview.getGrid().gridManager.torrentIndex = self.index
            self.guiUtility.selectTorrent(self.data)

        
    def getIdentifier(self):
        return self.data['infohash']


    def toggleItemDetailsSummary(self, visible):
        if visible and not self.summary:            
            if not self.data.get('web2'):                
                self.guiUtility.moderatedinfohash = self.data['infohash']
                self.summary = FilesItemDetailsSummary(self, torrentHash = self.data['infohash'], torrent = self.data)
            else:
                self.summary = FilesItemDetailsSummary(self, torrentHash = None, torrent = self.data, web2data = self.data)
            self.hSizerSummary.Add(self.summary, 1, wx.ALL|wx.EXPAND, 0)
            if sys.platform == 'win32':
                self.SetMinSize((-1,97))
            elif sys.platform == 'darwin':
                self.SetMinSize((-1,101))
            else:
                self.SetMinSize((-1,100))                
        elif visible and self.summary:
            pass
   
        elif self.summary and not visible:
            self.summary.Hide()
            wx.CallAfter(self.summary.DestroyChildren)
            wx.CallAfter(self.summary.Destroy)
            self.summary = None
            self.SetMinSize((-1,22))               

       
