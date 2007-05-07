import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Dialogs.dlhelperframe import DownloadHelperFrame
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
        self.vodMode = False
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
        self.speedUp2   = wx.StaticText(self,-1,"up: 0 KB/s",wx.Point(274,3),wx.Size(70,15),wx.ST_NO_AUTORESIZE)                        
        self.speedUp2.SetForegroundColour(self.triblerGrey)
        self.speedDown2 = wx.StaticText(self,-1,"down: 0 KB/s",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
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
        self.pb = ProgressBar(self,pos=wx.Point(359,0),size=wx.Size(100,16))
        #self.pb = wx.Panel(self)
        self.pause = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(16,16),name='pause' )
        self.stop = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(16,16),name='stop' )
        
        # >> Drawn in progressbar
        #self.pbLabel = wx.StaticText(self,-1,"12% |ETA:10min30",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        #self.pbSizer.Add(self.pbLabel,0,wx.TOP|wx.FIXED_MINSIZE,3)        
        # <<
        self.pbSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pbSizer.Add(self.pb,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        self.pbSizer.Add(self.pause,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        self.pbSizer.Add(self.stop,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        

        # Text under progressbar
        self.percentage = wx.StaticText(self,-1,"?%")
        self.percentage.SetForegroundColour(self.triblerGrey)
        self.eta = wx.StaticText(self,-1,"?")
        self.eta.SetForegroundColour(self.triblerGrey)
        
        self.fileProgressSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fileProgressSizer.Add(self.percentage, 1, wx.EXPAND, 0)
        self.fileProgressSizer.Add(self.eta, 0, wx.EXPAND|wx.ALIGN_RIGHT, 0)
        
        self.pbMessage = wx.BoxSizer(wx.VERTICAL)
        self.pbMessage.Add(self.pbSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.pbMessage.Add(self.fileProgressSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        
        vLine = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
        self.hSizer.Add(vLine, 0, wx.LEFT|wx.TOP, 6)
        
        self.hSizer.Add(self.pbMessage, 0, wx.LEFT|wx.EXPAND, 2)         
        
        # V Line                
        self.addLine()

       
        # Play Fast
        self.playFast = SwitchButton(self, name="playFast")
        self.playFast.setBackground(wx.WHITE)
        self.playFast.SetSize((82,18))
        self.playFast.setEnabled(False)
        self.boost = SwitchButton(self, name="boost")
        self.boost.setBackground(wx.WHITE)
        self.boost.SetSize((82,18))
        self.boost.setEnabled(False)
        buttonSizer = wx.BoxSizer(wx.VERTICAL)
        buttonSizer.Add(self.playFast, 1, wx.ALL, 2)
        buttonSizer.Add(self.boost, 1, wx.ALL, 2)
        
        self.hSizer.Add(buttonSizer, 1, wx.ALIGN_CENTER|wx.TOP, 2) 

        self.addLine()
        
        # Status message
        self.statusField = wx.StaticText(self, -1, '')
        self.statusField.SetMinSize((50,-1))
        self.hSizer.Add(self.statusField, 1, wx.ALL|wx.EXPAND, 5)
        
        # Play
        self.playerPlay = SwitchButton(self, name="libraryPlay")
        self.playerPlay.setBackground(wx.WHITE)
        self.playerPlay.SetSize((38,38))
        self.playerPlay.setEnabled(False)
        self.hSizer.Add(self.playerPlay, 0, wx.ALL, 2) 
        
        # Delete button
        self.delete = tribler_topButton(self, -1, wx.DefaultPosition, wx.Size(16,16),name='delete')
        self.delete.setBackground(wx.WHITE)
        
        self.hSizer.Add(self.delete,0,wx.FIXED_MINSIZE|wx.ALIGN_TOP,2)        
    
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
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,32),wx.LI_VERTICAL)
        self.hSizer.Add(vLine, 0, wx.LEFT|wx.TOP, 6)
        
    def setData(self, torrent):
        # set bitmap, rating, title
        
        if threading.currentThread().getName() != "MainThread":
            print >>sys.stderr,"lip: setData called by nonMainThread!",threading.currentThread().getName()
            print_stack()

        self.vodMode = False
        self.data = torrent
        
        if torrent is None:
            torrent = {}

        
        if torrent.get('abctorrent'):
            #print '%s is an active torrent' % torrent['content_name']
            abctorrent = torrent['abctorrent']
            abctorrent.setLibraryPanel(self)
            #self.pb.setEnabled(True)
            self.pb.Show()
            self.speedUp2.Show()
            self.speedDown2.Show()
            
            dls = abctorrent.getColumnText(COL_DLSPEED)
            self.speedDown2.SetLabel(self.utility.lang.get('down')+': '+dls) 
            uls = abctorrent.getColumnText(COL_ULSPEED)
            self.speedUp2.SetLabel(self.utility.lang.get('up')+': '+uls)
            progresstxt = abctorrent.getColumnText(COL_PROGRESS)
            progress = float(progresstxt[:-1])
            self.percentage.SetLabel(progresstxt)
            eta = 'ETA: '+abctorrent.getColumnText(COL_ETA)
            if not eta == 'ETA: ' or eta.find('unknown') != -1 or progress == 100.0:
                eta = ''
            self.eta.SetLabel(eta)
            
            self.statusField.SetLabel(abctorrent.getColumnText(COL_BTSTATUS))
            switchable = False
            playable = False
            havedigest = None
            showBoostAndPlayFast = False
            showPlayButton = False
            statustxt = abctorrent.status.getStatusText()
            
            initstates = [self.utility.lang.get('checkingdata'), 
                           self.utility.lang.get('allocatingspace'), 
                           self.utility.lang.get('movingdata'),
                           self.utility.lang.get('waiting')]
            
            if not (statustxt in initstates):
                showBoostAndPlayFast = (progress < 100.0)
                
                if abctorrent.get_on_demand_download():
                    self.vodMode = True
                    progressinf = abctorrent.get_progressinf()
                    havedigest = abctorrent.status.getHaveDigest()
                    havedigest2 = progressinf.get_bufferinfo()
                    playable = havedigest2.get_playable()
                    switchable = False
                    showPlayButton = True
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
                
            
            self.playerPlay.setEnabled(showPlayButton or playable)
            self.playerPlay.setToggled(playable)
            self.playFast.setToggled(not switchable)
            self.boost.setEnabled(showBoostAndPlayFast)
            self.boost.setToggled(self.is_boosted())
            self.playFast.setEnabled(showBoostAndPlayFast)
            
        else:
            #self.pb.setEnabled(False)
            self.pb.reset()
            self.pb.Refresh()
            self.speedUp2.Hide()
            self.speedDown2.Hide()
            self.playFast.setEnabled(False)
            self.boost.setEnabled(False)
            self.pb.Hide()
            
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
        self.GetContainingSizer().Layout()
        #self.parent.Refresh()
        
    def select(self):
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(self.selectedColour)
        self.playFast.setBackground(self.selectedColour)
        self.boost.setBackground(self.selectedColour)
        self.playerPlay.setBackground(self.selectedColour)
        self.SetBackgroundColour(self.selectedColour)
        self.playerPlay.setBackground(self.selectedColour)
        self.Refresh()
        
        
    def deselect(self):
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(self.unselectedColour)
        self.SetBackgroundColour(self.unselectedColour)
        self.playFast.setBackground(self.unselectedColour)
        self.boost.setBackground(self.unselectedColour)
        self.playerPlay.setBackground(self.unselectedColour)
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
                    playBitmap = wx.Bitmap(os.path.join(self.utility.getPath(),'Tribler', 'vwxGUI', 'images', 'play.png'))
                    obj.switchTo(playBitmap)
            elif name == 'playFast':
                if not self.vodMode:
                    self.vodMode = True
                    self.switch_to_vod(abctorrent)
                else:
                    self.switch_to_standard_dlmode(abctorrent)
                    self.vodMode = False
                self.playFast.setToggled(self.vodMode)
                
            elif name == 'boost':
                self.show_boost(abctorrent)
                    
            elif name == 'libraryPlay':
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
      
    def show_boost(self, ABCTorrentTemp):
        if ABCTorrentTemp is not None:
            #print >>sys.stderr,"GUIUtil: buttonClicked: dlbooster: Torrent is",ABCTorrentTemp.files.dest
            engine = ABCTorrentTemp.connection.engine
            if engine is not None and engine.getDownloadhelpCoordinator() is not None:
                self.dlhelperframe = DownloadHelperFrame(self,self.utility,engine)
                self.dlhelperframe.Show()
                
    
    def play(self,ABCTorrentTemp):
        videoplayer = VideoPlayer.getInstance()
        if ABCTorrentTemp.get_on_demand_download():
            videoplayer.vod_start_playing(ABCTorrentTemp)
        else:
            videoplayer.play(ABCTorrentTemp)
    
    def switch_to_standard_dlmode(self,ABCTorrentTemp): 
        videoplayer = VideoPlayer.getInstance() 
        videoplayer.vod_back_to_standard_dlmode(ABCTorrentTemp) 
        
    def is_boosted(self): 
        if self.data is None: 
            return False 
                  
        ABCTorrentTemp = self.data.get('abctorrent') 
        if ABCTorrentTemp is None: 
            return False 
                  
        engine = ABCTorrentTemp.connection.engine 
        if engine is None: 
            return False 
                  
        coordinator = engine.getDownloadhelpCoordinator() 
        if coordinator is None: 
            return False 
                  
        helpingFriends = coordinator.get_asked_helpers_copy() 
                  
        return len(helpingFriends) > 0
             
    def abcTorrentShutdown(self, infohash):
        """
        The abctorrent related to this panel was shutdown
        """
        if self.data.get('infohash') == infohash and self.data.get('abctorrent'):
            del self.data['abctorrent']
            
    
