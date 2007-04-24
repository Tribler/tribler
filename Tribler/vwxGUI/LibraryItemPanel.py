import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.vwxGUI.TriblerProgressbar import TriblerProgressbar
from Tribler.unicode import *
from tribler_topButton import *
from copy import deepcopy
from bgPanel import *
from Utility.constants import * 
import cStringIO

DEBUG=True

class LibraryItemPanel(wx.Panel):
    def __init__(self, parent):

        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 37 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.selectedColour = wx.Colour(245,208,120)
        self.unselectedColour = wx.WHITE
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add thumb        
        self.thumbnail = bgPanel(self, name="defaultThumb")
        self.thumbnail.setBackground(wx.BLACK)
        self.thumbnail.SetSize((66,37))
        self.hSizer.Add(self.thumbnail, 0, wx.ALL, 0)        
        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(160,12))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(8,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((180,12))
        
        # Up/Down text speed
        self.speedUp2   = wx.StaticText(self,-1,"up: 10 KB/s",wx.Point(274,3),wx.Size(70,15),wx.ST_NO_AUTORESIZE)                        
        self.speedUp2.SetForegroundColour(wx.Colour(128,128,128))
        self.speedDown2 = wx.StaticText(self,-1,"down: 12 KB/s",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        self.speedDown2.SetForegroundColour(wx.Colour(128,128,128))        
        self.speedSizer = wx.BoxSizer(wx.HORIZONTAL)
#        self.speedSizer.Add(self.speedUp,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,4)                
        self.speedSizer.Add(self.speedUp2,0,wx.TOP|wx.FIXED_MINSIZE,4)
#        self.speedSizer.Add(self.speedDown, 0, wx.LEFT|wx.TOP|wx.FIXED_MINSIZE, 4)                       
        self.speedSizer.Add(self.speedDown2, 0, wx.LEFT|wx.TOP|wx.FIXED_MINSIZE, 4)        
        self.vSizerTitle = wx.BoxSizer(wx.VERTICAL)
        self.vSizerTitle.Add (self.title, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
        self.vSizerTitle.Add (self.speedSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)                           
        self.hSizer.Add(self.vSizerTitle, 0, wx.ALL|wx.EXPAND, 3)     
        
        # Add Gauge/progressbar
        self.pb = TriblerProgressbar(self,-1,wx.Point(359,0),wx.Size(80,15))
        #self.pb = wx.Panel(self)
        self.pause = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(17,17),name='pause' )
        self.delete = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(17,17),name='delete')        
        # >> Drawn in progressbar
        #self.pbLabel = wx.StaticText(self,-1,"12% |ETA:10min30",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        #self.pbSizer.Add(self.pbLabel,0,wx.TOP|wx.FIXED_MINSIZE,3)        
        # <<
        self.pbSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pbSizer.Add(self.pb,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        self.pbSizer.Add(self.pause,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        self.pbSizer.Add(self.delete,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,2)        

        # Add message        
        self.message = wx.StaticText(self,-1,"message",wx.Point(274,3),wx.Size(70,15),wx.ST_NO_AUTORESIZE)        
        self.pbMessage = wx.BoxSizer(wx.VERTICAL)
        self.pbMessage.Add(self.pbSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.pbMessage.Add(self.message,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.hSizer.Add(self.pbMessage, 0, wx.LEFT|wx.EXPAND, 2)         
                
        # V Line                
#        self.vLine = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
#        self.hSizer.Add(self.vLine, 0, wx.LEFT|wx.TOP, 6)

        # Add checkBox -Private & -Archive
        self.cbPrivate = wx.CheckBox(self,-1,"",wx.Point(258,3),wx.Size(13,13))
        self.cbPrivateLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(35,15),wx.ST_NO_AUTORESIZE)
        self.cbPrivateLabel.SetLabel("archive")
        self.cbPrivateSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cbPrivateSizer.Add(self.cbPrivate, 0, wx.LEFT|wx.EXPAND, 1)     
        self.cbPrivateSizer.Add(self.cbPrivateLabel, 0, wx.LEFT|wx.EXPAND, 3)     

        self.cbArchive = wx.CheckBox(self,-1,"",wx.Point(258,18),wx.Size(13,13))
        self.cbArchiveLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(35,15),wx.ST_NO_AUTORESIZE)
        self.cbArchiveLabel.SetLabel("private")
        self.cbArchiveSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cbArchiveSizer.Add(self.cbArchive, 0, wx.LEFT|wx.EXPAND, 1)     
        self.cbArchiveSizer.Add(self.cbArchiveLabel, 0, wx.LEFT|wx.EXPAND, 2)     
        
        self.cbSizer = wx.BoxSizer(wx.VERTICAL)
        self.cbSizer.Add(self.cbPrivateSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.cbSizer.Add(self.cbArchiveSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.hSizer.Add(self.cbSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)                
        
        # V Line                        
#        self.vLine2 = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
#        self.hSizer.Add(self.vLine2, 0, wx.LEFT|wx.TOP, 6)

        # Play Fast
        self.playFast = bgPanel(self, name="playFast")
        self.playFast.setBackground(wx.BLACK)
        self.playFast.SetSize((84,37))
        self.hSizer.Add(self.playFast, 0, wx.TOP, 2) 
        
        # Add Refresh        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, torrent):
        # set bitmap, rating, title
        
        self.data = torrent
        
        if torrent == None:
            torrent = {}
            self.Hide()
        else:
            self.Show()
            
        
        if torrent.get('abctorrent'):
            print '%s is an active torrent' % torrent['content_name']
            abctorrent = torrent['abctorrent']
            progress = abctorrent.getColumnText(COL_PROGRESS)
            self.pb.setPercentage(float(progress[:-1]))
            #self.pb.setPercentage(50.0)
            eta = abctorrent.getColumnText(COL_ETA)
            self.pb.setETA(eta)
            
            
        if torrent.get('content_name'):
            title = torrent['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(torrent['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
        #self.thumb.setTorrent(torrent)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self):
        self.selected = True
        old = self.title.GetBackgroundColour()
        if old != self.selectedColour:
            self.title.SetBackgroundColour(self.selectedColour)
            self.Refresh()
        
        
    def deselect(self):
        self.selected = False
        old = self.title.GetBackgroundColour()
        if old != self.unselectedColour:
            self.title.SetBackgroundColour(self.unselectedColour)
            self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: deleting'
                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        
        self.SetFocus()
        if self.data:
            self.guiUtility.selectTorrent(self.data)
                
                
DEFAULT_THUMB = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'defaultThumb.png'))

