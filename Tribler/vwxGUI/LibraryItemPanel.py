import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.vwxGUI.GuiUtility import GUIUtility
#from Tribler.vwxGUI.TriblerProgressbar import TriblerProgressbar
from Tribler.vwxGUI.filesItemPanel import ThumbnailViewer
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Video.Progress import ProgressBar
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
        self.guiserver = parent.guiserver
        self.triblerGrey = wx.Colour(128,128,128)
        self.data = None
        self.datacopy = None
        self.titleLength = 23 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()

    def addComponents(self):
        self.Show(False)
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add thumb
        self.thumb = ThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((66,37))
        #self.thumb = bgPanel(self, name="defaultThumb")
        #self.thumb.setBackground(wx.BLACK)
        #self.thumb.SetSize((66,37))
        self.hSizer.Add(self.thumb, 0, wx.ALL, 0)
        
        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(160,12))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(8,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((180,12))
        
        # Up/Down text speed
        self.speedUp2   = wx.StaticText(self,-1,"up: 10 KB/s",wx.Point(274,3),wx.Size(70,15),wx.ST_NO_AUTORESIZE)                        
        self.speedUp2.SetForegroundColour(self.triblerGrey)
        self.speedDown2 = wx.StaticText(self,-1,"down: 12 KB/s",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        self.speedDown2.SetForegroundColour(self.triblerGrey)        
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
        #self.pb = TriblerProgressbar(self,-1,wx.Point(359,0),wx.Size(80,15))
        self.pb = ProgressBar(self,pos=wx.Point(359,0),size=wx.Size(100,15))
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
        self.fileProgress = wx.StaticText(self,-1,"?/?",wx.Point(274,3),wx.Size(70,15),wx.ST_NO_AUTORESIZE)
        self.fileProgress.SetForegroundColour(self.triblerGrey)
        self.pbMessage = wx.BoxSizer(wx.VERTICAL)
        self.pbMessage.Add(self.pbSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.pbMessage.Add(self.fileProgress,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.hSizer.Add(self.pbMessage, 0, wx.LEFT|wx.EXPAND, 2)         
                
        # V Line                
#        self.vLine = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
#        self.hSizer.Add(self.vLine, 0, wx.LEFT|wx.TOP, 6)

        # Add checkBox -Private & -Archive
#        self.cbPrivate = wx.CheckBox(self,-1,"",wx.Point(258,3),wx.Size(13,13))
#        self.cbPrivateLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(35,15),wx.ST_NO_AUTORESIZE)
#        self.cbPrivateLabel.SetLabel("archive")
#        self.cbPrivateSizer = wx.BoxSizer(wx.HORIZONTAL)
#        self.cbPrivateSizer.Add(self.cbPrivate, 0, wx.LEFT|wx.EXPAND, 1)     
#        self.cbPrivateSizer.Add(self.cbPrivateLabel, 0, wx.LEFT|wx.EXPAND, 3)     
#
#        self.cbArchive = wx.CheckBox(self,-1,"",wx.Point(258,18),wx.Size(13,13))
#        self.cbArchiveLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(35,15),wx.ST_NO_AUTORESIZE)
#        self.cbArchiveLabel.SetLabel("private")
#        self.cbArchiveSizer = wx.BoxSizer(wx.HORIZONTAL)
#        self.cbArchiveSizer.Add(self.cbArchive, 0, wx.LEFT|wx.EXPAND, 1)     
#        self.cbArchiveSizer.Add(self.cbArchiveLabel, 0, wx.LEFT|wx.EXPAND, 2)     
#        
#        self.cbSizer = wx.BoxSizer(wx.VERTICAL)
#        self.cbSizer.Add(self.cbPrivateSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
#        self.cbSizer.Add(self.cbArchiveSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
#        self.hSizer.Add(self.cbSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)                
        
        # V Line                        
#        self.vLine2 = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
#        self.hSizer.Add(self.vLine2, 0, wx.LEFT|wx.TOP, 6)

        # Play Fast
        self.playFast = tribler_topButton(self, name="playFast")
        self.playFast.setBackground(wx.BLACK)
        self.playFast.SetSize((84,37))
        self.playFast.Hide()
        self.hSizer.Add(self.playFast, 0, wx.TOP, 2) 

        # Play
        self.playerPlay = tribler_topButton(self, name="playerPlay")
        self.playerPlay.setBackground(wx.BLACK)
        self.playerPlay.SetSize((84,37))
        self.playerPlay.Hide()
        self.hSizer.Add(self.playerPlay, 0, wx.TOP, 2) 
        
        # Add Refresh        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                  
    def refreshData(self):
        self.setData(self.data)
        
    def setData(self, torrent):
        # set bitmap, rating, title
        
        if threading.currentThread().getName() != "MainThread":
            print >>sys.stderr,"lip: setData called by nonMainThread!",threading.currentThread().getName()
            print_stack()


        self.data = torrent
        
        if torrent is None:
            torrent = {}
            self.Hide()
        else:
            self.Show()
            
        
        if torrent.get('abctorrent'):
            #print '%s is an active torrent' % torrent['content_name']
            abctorrent = torrent['abctorrent']
            abctorrent.setLibraryPanel(self)
            #self.pb.setEnabled(True)
            if not self.fileProgress.IsShown():
                self.fileProgress.Show()
            self.speedUp2.Show()
            self.speedDown2.Show()
            
            dls = abctorrent.getColumnText(COL_DLSPEED)
            self.speedDown2.SetLabel(self.utility.lang.get('down')+': '+dls) 
            uls = abctorrent.getColumnText(COL_ULSPEED)
            self.speedUp2.SetLabel(self.utility.lang.get('up')+': '+uls)
            progresstxt = abctorrent.getColumnText(COL_PROGRESS)[:-1]
            progress = float(progresstxt)
            #self.pb.setPercentage(progress)
            #eta = abctorrent.getColumnText(COL_ETA)
            #self.pb.setETA(eta)
            
            #print >>sys.stderr,"lip: Progress is",progress,torrent['content_name']
            
            switchable = False
            playable = False
            havedigest = None
            statustxt = abctorrent.status.getStatusText()
            
            initstates = [self.utility.lang.get('checkingdata'), 
                           self.utility.lang.get('allocatingspace'), 
                           self.utility.lang.get('movingdata'),
                           self.utility.lang.get('waiting')]
            
            if not (statustxt in initstates):
                if abctorrent.get_on_demand_download():
                    progressinf = abctorrent.get_progressinf()
                    havedigest = abctorrent.status.getHaveDigest()
                    havedigest2 = progressinf.get_bufferinfo()
                    playable = havedigest2.get_playable()
                    switchable = False
                else:
                    havedigest = abctorrent.status.getHaveDigest()
                    playable = (progress == 100.0)
                    if not playable:
                        switchable = True
                    
            if havedigest is not None:
                self.pb.set_blocks(havedigest.get_blocks())
                self.pb.Refresh()
            elif progress == 100.0:
                self.pb.reset(colour=2) # Show as complete
                self.pb.Refresh()
            elif progress > 0:
                self.pb.reset(colour=1) # Show as having some
                self.pb.Refresh()
            else:
                self.pb.reset(colour=0) # Show has having none
                self.pb.Refresh()
                
            if playable:
                self.playerPlay.Show()
                
            if switchable:
                self.playFast.Show()
            else:                
                self.playFast.Hide()
                
                
            dlsize = abctorrent.getColumnText(COL_DLANDTOTALSIZE)
            self.fileProgress.SetLabel(dlsize)
        else:
            #self.pb.setEnabled(False)
            self.pb.reset()
            self.pb.Refresh()
            self.speedUp2.Hide()
            self.speedDown2.Hide()
            self.playFast.Hide()
            self.fileProgress.Hide()
            
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
        self.thumb.setTorrent(torrent)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
    def select(self):
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(self.selectedColour)
        self.SetBackgroundColour(self.selectedColour)
        self.Refresh()
        
        
    def deselect(self):
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(self.unselectedColour)
        self.SetBackgroundColour(self.unselectedColour)
        self.Refresh()
        
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'lib: deleting'
                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        if self.data.get('abctorrent'):
            obj = event.GetEventObject()
            name = obj.GetName()
            abctorrent = self.data.get('abctorrent')
            if name == 'delete':
                abctorrent.actions.stop()
                
            elif name == 'pause':
                if abctorrent.status.value == STATUS_PAUSE:
                    abctorrent.actions.pauseResume()
                    obj.switchBack()
                else:
                    abctorrent.actions.pause()
                    playBitmap = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'play.png'))
                    obj.switchTo(playBitmap)
            elif name == 'playFast':
                self.switch_to_vod(abctorrent)
            elif name == 'playerPlay':
                self.play(abctorrent)
          
        print >>sys.stderr,"lip: mouseaction: name",event.GetEventObject().GetName()
            
        self.SetFocus()
        if self.data:
            self.guiUtility.selectTorrent(self.data)
        event.Skip()
                
    def getIdentifier(self):
        if self.data:
            return self.data.get('infohash')
        else:
            return None
        
    def switch_to_vod(self,ABCTorrentTemp):
        videoplayer = VideoPlayer.getInstance()
        videoplayer.play(ABCTorrentTemp)
                        
    def play(self,ABCTorrentTemp):
        videoplayer = VideoPlayer.getInstance()
        if ABCTorrentTemp.get_on_demand_download():
            videoplayer.vod_start_playing(ABCTorrentTemp)
        else:
            videoplayer.play(ABCTorrentTemp)

        