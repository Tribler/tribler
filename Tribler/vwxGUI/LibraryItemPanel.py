import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Dialogs.dlhelperframe import DownloadHelperFrame
from Tribler.vwxGUI.GuiUtility import GUIUtility
#from Tribler.vwxGUI.TriblerProgressbar import TriblerProgressbar
from Tribler.vwxGUI.filesItemPanel import ThumbnailViewer
#from Dialogs.abcdetailframe import ABCDetailFrame
from Tribler.Video.__init__ import stat
from Tribler.Video.VideoPlayer import VideoPlayer,find_video_on_disk

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
        self.torrentDetailsFrame = None
        self.addComponents()
        self.SetMinSize((-1, 37+6))
        self.Show()
        self.Refresh()
        self.Layout()

    def addComponents(self):
        self.Show(False)
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add Spacer
        self.hSizer.Add([8,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        
        
        # Add thumb
        self.thumb = ThumbnailViewer(self, 'libraryMode')
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((66,37))
        #self.thumb = bgPanel(self, name="defaultThumb")
        #self.thumb.setBackground(wx.BLACK)
        #self.thumb.SetSize((66,37))
        self.hSizer.Add(self.thumb, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 3)
        
        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(160,12))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(8,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((180,14))
        
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
        self.hSizer.Add(self.vSizerTitle, 0, wx.LEFT|wx.RIGHT|wx.TOP|wx.EXPAND, 3)     
        
        # Add Gauge/progressbar
        #self.pb = TriblerProgressbar(self,-1,wx.Point(359,0),wx.Size(80,15))
        self.pb = ProgressBar(self,pos=wx.Point(359,0),size=wx.Size(100,16))
        #self.pb = wx.Panel(self)
        self.pause = SwitchButton(self, -1, wx.Point(542,3), wx.Size(16,16),name='pause' )
                
        # >> Drawn in progressbar
        #self.pbLabel = wx.StaticText(self,-1,"12% |ETA:10min30",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        #self.pbSizer.Add(self.pbLabel,0,wx.TOP|wx.FIXED_MINSIZE,3)        
        # <<
        self.pbSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pbSizer.Add(self.pb,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)        
        self.pbSizer.Add(self.pause,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,2)        
                

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
        
        self.addLine()
        #vLine = wx.StaticLine(self,-1,wx.Point(362,37),wx.Size(2,32),wx.LI_VERTICAL)
        #self.hSizer.Add(vLine, 0, wx.LEFT, 6)
        
        self.hSizer.Add(self.pbMessage, 0, wx.LEFT|wx.EXPAND, 2)         
        
        # V Line                
        self.addLine()

       
        # Play Fast
        self.playFast = SwitchButton(self, name="playFast")
        self.playFast.setBackground(wx.WHITE)
        self.playFast.SetSize((81,16))
        self.playFast.setEnabled(False)
        self.boost = SwitchButton(self, name="boost")
        self.boost.setBackground(wx.WHITE)
        self.boost.SetSize((81,16))
        self.boost.setEnabled(False)
        buttonSizer = wx.BoxSizer(wx.VERTICAL)
        buttonSizer.Add(self.playFast, 1, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 2)
        buttonSizer.Add(self.boost, 1, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 2)
        
        self.hSizer.Add(buttonSizer, 1, wx.TOP, 0) 

        self.addLine()
        
        # Status message
        self.statusField = wx.StaticText(self, -1, '')
        self.statusField.SetMinSize((37,-1))
        self.hSizer.Add(self.statusField, 1, wx.TOP|wx.EXPAND, 4)
        
        # Play
        self.playerPlay = SwitchButton(self, name="libraryPlay")
        self.playerPlay.setBackground(wx.WHITE)
        self.playerPlay.SetSize((37,37))
        self.playerPlay.setEnabled(False)
        self.hSizer.Add(self.playerPlay, 0, wx.TOP|wx.BOTTOM, 3) 
        
        # Delete button
        self.delete = tribler_topButton(self, -1, wx.DefaultPosition, wx.Size(16,16),name='deleteLibraryitem')
        self.delete.setBackground(wx.WHITE)
        
        self.hSizer.Add(self.delete,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE|wx.ALIGN_TOP,3)       
        
        self.hSizer.Add([8,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)         
    
        # Add Refresh        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in [self]+self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                  
    def refreshData(self):
        self.setData(self.data)
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,32),wx.LI_VERTICAL)
        self.hSizer.Add(vLine, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
        
    def setData(self, torrent):
        # set bitmap, rating, title
        
        if threading.currentThread().getName() != "MainThread":
            print >>sys.stderr,"lip: setData called by nonMainThread!",threading.currentThread().getName()
            print_stack()

        self.vodMode = False
        self.data = torrent
        
        if torrent is None:
            for child in self.GetChildren():
                child.Hide()
            torrent = {}
        else:
            for child in self.GetChildren():
                child.Show()
            

        
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
            if eta == 'ETA: ' or eta.find('unknown') != -1 or progress == 100.0:
                eta = ''
            self.eta.SetLabel(eta)
            
            self.statusField.SetLabel(abctorrent.getColumnText(COL_BTSTATUS))
            switchable = False
            self.playable = False
            havedigest = None
            showBoost = False
            showPlayFast = False            
            showPlayButton = False
            statustxt = abctorrent.status.getStatusText()
            active = abctorrent.status.isActive(pause = False)
            
            initstates = [self.utility.lang.get('checkingdata'), 
                           self.utility.lang.get('allocatingspace'), 
                           self.utility.lang.get('movingdata'),
                           self.utility.lang.get('waiting')]
            
            if not (statustxt in initstates):
                showBoost = active and (progress < 100.0)
                if showBoost and len(find_video_on_disk(abctorrent,stat(abctorrent))) > 0:
                    showPlayFast = True
                
                if abctorrent.get_on_demand_download():
                    self.vodMode = True
                    progressinf = abctorrent.get_progressinf()
                    havedigest = abctorrent.status.getHaveDigest()
                    havedigest2 = progressinf.get_bufferinfo()
                    self.playable = havedigest2.get_playable()
                    switchable = False
                    showPlayButton = True
                else:
                    havedigest = abctorrent.status.getHaveDigest()
                    self.playable = (progress == 100.0)
                    if not self.playable:
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
                
            
            self.playerPlay.setEnabled(showPlayButton or self.playable)
            self.playerPlay.setToggled(self.playable)
            
            self.playFast.setEnabled(showPlayFast)
            self.playFast.setToggled(not switchable)

            self.boost.setEnabled(showBoost)
            self.boost.setToggled(self.is_boosted())
            
            self.pause.setToggled(not active)
                        
                
        elif torrent: # inactive torrent
            
            #self.pb.setEnabled(False)
            self.speedUp2.Hide()
            self.speedDown2.Hide()
            
            # Only show playbutton
            self.playFast.setEnabled(False)
            self.boost.setEnabled(False)
            self.pause.setEnabled(True)
            self.pause.setToggled(True)
            self.statusField.SetLabel(self.utility.lang.get('stop'))
            self.eta.SetLabel('')
            
            if torrent.get('progress'):
                self.percentage.SetLabel('%0.2f%%' % torrent['progress'])
                self.pb.setNormalPercentage(torrent['progress'])
            else:
                self.percentage.SetLabel('?')
                self.pb.reset()
            
            self.pb.Show()
            self.pb.Refresh()
            
        if torrent.get('content_name'):
            title = torrent['content_name'][:self.titleLength]
            self.title.Show()
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(torrent['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Hide()
            
        
            
        self.thumb.setTorrent(torrent)
               
        self.Layout()
        self.Refresh()
        self.GetContainingSizer().Layout()
        #self.parent.Refresh()
        
    def select(self):
        colour = self.guiUtility.selectedColour
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(colour)
        self.playFast.setBackground(colour)
        self.boost.setBackground(colour)
        self.playerPlay.setBackground(colour)
        self.SetBackgroundColour(colour)
        self.playerPlay.setBackground(colour)
        self.Refresh()
        
        
    def deselect(self, number = 0):
        if number % 2 == 0:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
        self.SetBackgroundColour(colour)
        self.playFast.setBackground(colour)
        self.boost.setBackground(colour)
        self.playerPlay.setBackground(colour)
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
        event.Skip()
        
        if not self.data:
            return
        
        obj = event.GetEventObject()
        name = obj.GetName()
        
        self.SetFocus()
        if self.data:
            self.guiUtility.selectTorrent(self.data)
            
        # buttons that are switched off, should not generate events
        try:
            if not obj.isEnabled():
                #print 'Button %s was not enabled' % name
                return
        except:
            pass
            
        if self.data.get('abctorrent'):
                
            abctorrent = self.data.get('abctorrent')
            if name == 'deleteLibraryitem':
                removeFiles = False
                self.utility.actionhandler.procREMOVE([abctorrent], removefiles = removeFiles)
                            
            elif name == 'pause':
                if abctorrent.status.value in [STATUS_PAUSE, STATUS_STOP, STATUS_QUEUE ]:
                    self.utility.actionhandler.procRESUME([abctorrent])
                    obj.setToggled(False)
                else:
                    self.utility.actionhandler.procSTOP([abctorrent])
                    obj.setToggled(True)
                    
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
                if self.playable:
                    self.play(abctorrent)
        else: # no abctorrent
            if name == 'pause':
                 #playbutton
                 dest_dir = self.data.get('destdir')
                 if  dest_dir != None:
                     # Start torrent again
                     print 'starting torrent %s with data in dir %s' % (repr(self.data['content_name']), dest_dir)
                     self.guiUtility.standardDetails.download(self.data, dest = dest_dir)
                 
                 else:
                     print 'LibraryItemPanel: Could not make abctorrent active, no destdir in dictionary: %s' % repr(self.data.get('content_name'))
                
                
        if name == 'deleteLibraryitem':
            # delete works for active and inactive torrents
            self.guiUtility.standardOverview.removeTorrentFromLibrary(self.data)
                
        print >>sys.stderr,"lip: mouseaction: name",event.GetEventObject().GetName()
            
        
       
       
    def doubleClicked(self, event):
        # open torrent details frame
        abctorrent = self.data.get('abctorrent')
        if abctorrent:
            abctorrent.dialogs.advancedDetails()
            
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
            print 'abcTorrentShutdown with right infohash'
            
            abctorrent = self.data.get('abctorrent')
            progresstxt = abctorrent.getColumnText(COL_PROGRESS)
            progress = float(progresstxt[:-1])
            # store the progress of this torrent
            newdata = {'progress':progress, 'destdir':abctorrent.files.dest}
            self.data.update(newdata)
            
            print 'Save destination?: %s' % self.data['destdir']
            # only save new data (progression and destdir, no other data or torrent
            self.utility.torrent_db.updateTorrent(infohash, item = newdata)
            # Now delete the abctorrent object reference
            del self.data['abctorrent']
    
