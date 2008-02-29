import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from Tribler.Core.Utilities.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.Dialogs.dlhelperframe import DownloadHelperFrame
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.filesItemPanel import ThumbnailViewer, libraryModeThumbSize
from Tribler.Video.VideoPlayer import VideoPlayer
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Video.Progress import ProgressBar
from Tribler.Core.Overlay.MetadataHandler import MetadataHandler
from Tribler.Core.Utilities.unicode import *
from tribler_topButton import *
from copy import deepcopy
from bgPanel import *
from font import *
from Tribler.Main.Utility.constants import * 
from Tribler.Main.Utility import *



import cStringIO

DEBUG = False

[ID_MENU_1418,ID_MENU_1419,ID_MENU_1420] = 1418,1419,1420

# font sizes

#if sys.platform == 'darwin':
#    FS_FRIENDTITLE = 11
#    FS_STATUS = 10
#    FS_SIMILARITY = 10
#    FS_HEARTRANK = 10
#    FS_ONLINE = 10
#else:
#    FS_FRIENDTITLE = 11
#    FS_STATUS = 9
#    FS_SIMILARITY = 10
#    FS_HEARTRANK = 7
#    FS_ONLINE = 8

if sys.platform == 'darwin':
    FS_TITLE = 10
    FS_PERC = 9
    FS_SPEED = 9
else:
    FS_TITLE = 8
    FS_PERC = 7
    FS_SPEED = 7
    
statusLibrary  = {"downloading"     : "LibStatus_downloading.png",
                  "stopped"         : "LibStatus_stopped.png",
                  "boosting"        : "LibStatus_boosting.png",
                  "completed"       : "LibStatus_completed.png",
                  "seeding"         : "LibSatus_seeding.png"}


class LibraryItemPanel(wx.Panel):
    def __init__(self, parent, keyTypedFun = None):

        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.guiserver = parent.guiserver
        self.triblerGrey = wx.Colour(128,128,128)
        
        #self.statusTorrent = TorrentStatus(self)
        
        self.listItem = True # library always in listmode
        self.data = None
        self.status = None
        self.rightMouse = None
        self.datacopy = None
        self.titleLength = 16 # num characters
        self.vodMode = False
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.torrentDetailsFrame = None
        self.metadatahandler = MetadataHandler.getInstance()
        self.addComponents()
    
        #self.Bind(wx.EVT_RIGHT_DOWN, self.rightMouseButton)             
        

        self.SetMinSize((-1, 22))
        self.selected = False
        self.Show()
        self.Refresh()
        self.Layout()

    def addComponents(self):
        self.Show(False)
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add Spacer
        self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        
        
        
        # Add thumb
        self.thumb = ThumbnailViewer(self, 'libraryMode')
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize(libraryModeThumbSize)
        self.hSizer.Add(self.thumb, 0, wx.ALL, 2)
        
        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(120,14))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((120,14))
        self.hSizer.Add(self.title,1,wx.TOP,3)
        
    
##        self.vSizerTitle = wx.BoxSizer(wx.VERTICAL)
##        self.vSizerTitle.Add (self.title, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
##        self.vSizerTitle.Add (self.speedSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)                           
##        self.hSizer.Add(self.vSizerTitle, 0, wx.LEFT|wx.RIGHT|wx.TOP|wx.EXPAND, 3)     
        
        
        # V Line
        self.addLine()
        # Add Gauge/progressbar
        #self.pb = TriblerProgressbar(self,-1,wx.Point(359,0),wx.Size(80,15))
        self.pb = ProgressBar(self,pos=wx.Point(359,0),size=wx.Size(100,5))
        
        # >> Drawn in progressbar
        #self.pbLabel = wx.StaticText(self,-1,"12% |ETA:10min30",wx.Point(274,3),wx.Size(80,15),wx.ST_NO_AUTORESIZE)                                
        #self.pbSizer.Add(self.pbLabel,0,wx.TOP|wx.FIXED_MINSIZE,3)        
        # <<        

        # Text under progressbar
        self.percentage = wx.StaticText(self,-1,"?%")
        self.percentage.SetForegroundColour(self.triblerGrey)
        self.percentage.SetFont(wx.Font(FS_PERC,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.eta = wx.StaticText(self,-1,"?")
        self.eta.SetForegroundColour(self.triblerGrey)
        self.eta.SetFont(wx.Font(FS_PERC,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))                
        self.fileProgressSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fileProgressSizer.Add(self.percentage, 1, wx.EXPAND, 0)
        self.fileProgressSizer.Add(self.eta, 0, wx.EXPAND|wx.ALIGN_RIGHT, 0)
        
        self.pbMessage = wx.BoxSizer(wx.VERTICAL)
        self.pbMessage.Add(self.pb,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.pbMessage.Add(self.fileProgressSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.hSizer.Add(self.pbMessage, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 2)         
        
        # pause/stop button
        self.pause = SwitchButton(self, -1, wx.Point(542,3), wx.Size(16,16),name='pause' )
        self.hSizer.Add(self.pause,0,wx.TOP|wx.FIXED_MINSIZE,2)        
        
        # V Line
        self.addLine()
        
        # Up/Down text speed
#        self.downSpeed = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='downSpeed')
#        self.downSpeed.setBackground(wx.WHITE)
#        self.downSpeed.SetToolTipString(self.utility.lang.get('down'))
        self.speedDown2 = wx.StaticText(self,-1,"down: 0 KB/s",wx.Point(274,3),wx.Size(70,12),wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)                                
        self.speedDown2.SetForegroundColour(self.triblerGrey)        
        self.speedDown2.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.speedDown2.SetMinSize((70,12))        
#        self.upSpeed = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='upSpeed')
#        self.upSpeed.setBackground(wx.WHITE)
#        self.upSpeed.SetToolTipString(self.utility.lang.get('up'))
        self.speedUp2   = wx.StaticText(self,-1,"up: 0 KB/s",wx.Point(274,3),wx.Size(70,12),wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)                        
        self.speedUp2.SetForegroundColour(self.triblerGrey)
        self.speedUp2.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.speedUp2.SetMinSize((70,12))

#        self.hSizer.Add(self.downSpeed, 0, wx.TOP, 2)
#        self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)                 
        self.hSizer.Add(self.speedDown2, 0, wx.TOP|wx.EXPAND, 4)
        # V Line
        self.addLine()
        
#        self.hSizer.Add(self.upSpeed, 0, wx.LEFT|wx.TOP, 2)                  
#        self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)                 
        self.hSizer.Add(self.speedUp2, 0, wx.TOP|wx.EXPAND, 4)         
        
        # V Line                
        self.addLine()
                
        # Status Icon
##        self.statusIcon = ImagePanel(self, -1, name="LibStatus_boosting")        
##        self.statusIcon.searchBitmap(name = statusLibrary["stopped"])
##
##        self.hSizer.Add(self.statusIcon, 0, wx.TOP|wx.RIGHT|wx.EXPAND, 2)
        
        # Status message
        self.statusField = wx.StaticText(self, -1,'', wx.Point(),wx.Size())
        self.statusField.SetForegroundColour(self.triblerGrey)        
        self.statusField.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.statusField.SetMinSize((60,12))
#        self.statusField.SetMinSize((125,12))
        self.hSizer.Add(self.statusField, 1, wx.TOP, 4)
        
        # V Line
        self.addLine()
        
        # Boost button
        self.boost = SwitchButton(self, name="boost")
        self.boost.setBackground(wx.WHITE)
        self.boost.SetSize((50,16))
        self.boost.setEnabled(False)
        self.hSizer.Add(self.boost, 0, wx.TOP|wx.ALIGN_RIGHT, 2)
        self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
       
        # Play Fast
        self.playFast = SwitchButton(self, name="playFast")
        self.playFast.setBackground(wx.WHITE)
        self.playFast.SetSize((39,16))
        self.playFast.setEnabled(False)
        self.hSizer.Add(self.playFast, 0, wx.TOP|wx.ALIGN_RIGHT, 2)
        self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)   

        # Play
        self.playerPlay = SwitchButton(self, name="libraryPlay")
        self.playerPlay.setBackground(wx.WHITE)
        self.playerPlay.SetSize((16,16))
        self.playerPlay.setEnabled(False)
        self.hSizer.Add(self.playerPlay, 0, wx.TOP|wx.ALIGN_RIGHT, 2)          
        self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0) 
#       
        # TODO: TB >delete button should be removed when delete function in rightMouseButton menu works 
        # Delete button
        #self.delete = tribler_topButton(self, -1, wx.DefaultPosition, wx.Size(16,16),name='deleteLibraryitem')
        #self.delete.setBackground(wx.WHITE)
        #self.hSizer.Add(self.delete,0,wx.TOP|wx.FIXED_MINSIZE|wx.ALIGN_TOP,7)
        #self.hSizer.Add([8,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)         
    
        # Add Refresh        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        # 2.8.4.2 return value of GetChildren changed
        wl = [self]
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            #window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)                         
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)             
            
    def getColumns(self):
        return [{'sort':'', 'title':'', 'width':35, 'tip':''},
                {'sort':'content_name', 'reverse':True, 'title':'name', 'weight':1,'tip':self.utility.lang.get('C_filename'), 'order':'down'},
                {'sort':'progress', 'title':'progress', 'width':120, 'tip':self.utility.lang.get('C_progress')},
                {'sort':'??','dummy':True, 'pic':'downSpeedColumn','title':'down', 'width':70, 'tip':self.utility.lang.get('C_downspeed')},
                {'sort':'??', 'dummy':True, 'pic':'upSpeedColumn','title':'up','width':70, 'tip':self.utility.lang.get('C_upspeed')},                
                {'sort':'latest', 'dummy':True, 'title':'status', 'weight':1, 'tip':self.utility.lang.get('C_message')},
                {'sort':'??', 'title':'info', 'dummy':True, 'width':111, 'tip':self.utility.lang.get('C_info')}
                ]     
                  
    def refreshData(self):
        self.setData(self.data)
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,22),wx.LI_VERTICAL)
        self.hSizer.Add(vLine, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 3)
        
    def setData(self, torrent):
        # set bitmap, rating, title
        
        #print_stack()
        
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
            

        
        if torrent.get('abctorrent2'):    # Jie: temporary disable it by set it as 'abctorrent2'
            #print '%s is an active torrent' % torrent['content_name']
            abctorrent = torrent['abctorrent']
            #abctorrent.setLibraryPanel(self)
            
            # Check if torrent just finished for resort
            #abctorrent.status.checkJustFinished()
            
            #self.pb.setEnabled(True)
            self.pb.Show()
#            self.downSpeed.Show()
            self.speedDown2.Show()
#            self.upSpeed.Show()
            self.speedUp2.Show()
            
            dls = abctorrent.getColumnText(COL_DLSPEED)
            self.speedDown2.SetLabel(dls) 
#            self.speedDown2.SetLabel(self.utility.lang.get('down')+': '+dls) 
            uls = abctorrent.getColumnText(COL_ULSPEED)
            self.speedUp2.SetLabel(uls)
#            self.speedUp2.SetLabel(self.utility.lang.get('up')+': '+uls)
            #progresstxt = abctorrent.getColumnText(COL_PROGRESS)
            #progress = round(float(progresstxt[:-1]),0)

            self.percentage.SetLabel(progresstxt)
            #eta = ''+abctorrent.getColumnText(COL_ETA)
            if eta == '' or eta.find('unknown') != -1 or progress == 100.0:
                eta = ''
            self.eta.SetLabel(eta)
            self.eta.SetToolTipString(self.utility.lang.get('eta')+eta)
            
            #self.statusField.SetLabel(abctorrent.getColumnText(COL_BTSTATUS))
            self.statusField.SetToolTipString(self.statusField.GetLabel())
            
            #status = abctorrent.status.getStatus()
#            print "--tb-------------------------------"
#            print status
            # status is mapped with >Utility/constants.py
            #if status == STATUS_QUEUE :  
                #print 'queue'
            #    pass
##            elif status == STATUS_STOP or status == STATUS_PAUSE :  
##                self.statusIcon.searchBitmap(name = statusLibrary["stopped"])
##            elif status == STATUS_ACTIVE:  
##                self.statusIcon.searchBitmap(name = statusLibrary["downloading"])
##            elif status == STATUS_HASHCHECK:  
##                print 'hash check'
##            elif status == STATUS_SUPERSEED :  
##                self.statusIcon.searchBitmap(name = statusLibrary["seeding"])
##            elif status == STATUS_FINISHED :  
##                self.statusIcon.searchBitmap(name = statusLibrary["completed"])
                
##statusLibrary  = {"downloading"     : "LibStatus_boosting.png",
##                  "stopped"         : "LibStatus_stopped.png",
##                  "boosting"        : "LibStatus_boosting.png",
##                  "completed"       : "LibStatus_completed.png",
##                  "seeding"         : "LibSatus_seeding.png"}

                            
            switchable = False
            self.playable = False
            havedigest = None
            showBoost = False
            showPlayFast = False            
            showPlayButton = False
            #statustxt = abctorrent.status.getStatusText()

            active = True # fixme: abctorrent.status.isActive(pause = False)
            
            if abctorrent.caller_data is not None:
                active = False
            
            initstates = [self.utility.lang.get('checkingdata'), 
                           self.utility.lang.get('allocatingspace'), 
                           self.utility.lang.get('movingdata'),
                           self.utility.lang.get('waiting')]
            
            if not (statustxt in initstates):
                showBoost = active and (progress < 100.0)
                if showBoost and abctorrent.is_vodable():
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
                    isVideo = abctorrent.is_vodable()
                    self.playable = (progress == 100.0) and isVideo
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
            self.playerPlay.setToggled(self.playable, tooltip = {"disabled" : self.utility.lang.get('playerDisabled'), "enabled" : self.utility.lang.get('playerEnabled')})
            
            self.playFast.setEnabled(showPlayFast)
            self.playFast.setToggled(not switchable, tooltip = {"disabled" : self.utility.lang.get('playFastDisabled'), "enabled" : self.utility.lang.get('playFastEnabled')})

            self.boost.setEnabled(showBoost)
            self.boost.setToggled(self.is_boosted(), tooltip = {"disabled" : self.utility.lang.get('boostDisabled'), "enabled" : self.utility.lang.get('boostEnabled')})
            
            self.pause.setToggled(not active)
                        
                
        elif torrent: # inactive torrent
            
            #self.pb.setEnabled(False)
            #self.downSpeed2.Hide()
            self.speedDown2.SetLabel('')
            #self.upSpeed.Hide()            
            self.speedUp2.SetLabel('')
            
            # Only show playbutton
            self.playFast.setEnabled(False)
            self.boost.setEnabled(False)
            self.pause.setEnabled(True)
            self.pause.setToggled(True)
            if torrent.get('progress') == 100.0:
                self.playerPlay.setEnabled(True)
                self.playerPlay.setToggled(True, tooltip = {"disabled" : self.utility.lang.get('playerDisabled'), "enabled" : self.utility.lang.get('playerEnabled')})
                self.statusField.SetLabel(self.utility.lang.get('completed'))
            else:
                self.playerPlay.setEnabled(False)
                self.statusField.SetLabel(self.utility.lang.get('stop'))
            self.statusField.SetToolTipString(self.statusField.GetLabel())
            self.eta.SetLabel('')
            
            if torrent.get('progress') != None:                
                self.percentage.SetLabel('%0.1f%%' % torrent['progress'])
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
        
    def select(self, rowIndex, colIndex):
        self.selected = True
        colour = self.guiUtility.selectedColour
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(colour)
#        self.downSpeed.setBackground(colour)
#        self.upSpeed.setBackground(colour)
        self.playFast.setBackground(colour)
        self.boost.setBackground(colour)
##        self.statusIcon.setBackground(colour)
        self.playerPlay.setBackground(colour)
        self.SetBackgroundColour(colour)
        self.Refresh()

        
        
    def deselect(self, rowIndex, colIndex):
        self.selected = False
        if rowIndex % 2 == 0:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
#        self.downSpeed.setBackground(colour)
#        self.upSpeed.setBackground(colour)
        self.SetBackgroundColour(colour)
        self.playFast.setBackground(colour)
        self.boost.setBackground(colour)
##        self.statusIcon.setBackground(colour)
        self.playerPlay.setBackground(colour)
        self.Refresh()
        
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'lib: deleting'
                    # Arno; 2007-05-11: TODO: use right method here, deleteTorrent does nothing at the 
                    # moment, see below for right method
                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        if DEBUG:
            print >>sys.stderr,"lip: mouseaction: name",event.GetEventObject().GetName()

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
            
        if self.data.get('abctorrent2'):    # Jie: temporary disable it. It should set back to abctorrent.
                
            abctorrent = self.data.get('abctorrent')
            if name == 'deleteLibraryitem':
                removeFiles = False
                self.utility.actionhandler.procREMOVE([abctorrent], removefiles = removeFiles)
                            
            elif name == 'pause':
                # ARNOCOMMENT: need to get/store/cache current status of Download somehow
                if abctorrent.status.value in [STATUS_PAUSE, STATUS_STOP, STATUS_QUEUE ]:
                    abctorrent.restart()
                    obj.setToggled(False)
                else:
                    abctorrent.stop()
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
                 if  dest_dir is not None:
                     # Start torrent again
                     if DEBUG:
                         print >>sys.stderr,'lip: starting torrent %s with data in dir %s' % (repr(self.data['content_name']), dest_dir)
                     self.guiUtility.standardDetails.download(self.data, dest = dest_dir, force = True)
                 
                 elif DEBUG:
                     print >>sys.stderr,'lip: Could not make abctorrent active, no destdir in dictionary: %s' % repr(self.data.get('content_name'))
            elif name == 'libraryPlay':
                # Todo: make non-abctorrent files playable.
                dest_dir = self.data.get('destdir')
                if  dest_dir is not None:
                    # Start torrent again
                    if DEBUG:
                        print >>sys.stderr,'lip: starting torrent %s with data in dir %s' % (repr(self.data['content_name']), dest_dir)
                    self.guiUtility.standardDetails.download(self.data, dest = dest_dir, force = True)
                    
                elif DEBUG:
                    print >>sys.stderr,'lip: Could not make abctorrent active, no destdir in dictionary: %s' % repr(self.data.get('content_name'))
                
        if name == 'deleteLibraryitem':
            # delete works for active and inactive torrents
            self.guiUtility.standardOverview.removeTorrentFromLibrary(self.data)
            
        if event.RightDown():
            self.rightMouseButton(event)
   
   
    def rightMouseButton(self, event):     
        # Open right-click menu (windows menu key)
        # >>makePopup(self, menu, event = None, label = "", extralabel = "", bindto = None):

        menu = self.guiUtility.OnRightMouseAction(event)
        if menu is not None:
            self.PopupMenu(menu, (-1,-1))        
        
        #--tb--
#        rightMouse = wx.Menu()        
#
#        self.utility.makePopup(rightMouse, self.onOpenFileDest, 'ropenfiledest')
#        self.utility.makePopup(rightMouse, self.onOpenDest, 'ropendest')
#        rightMouse.AppendSeparator()        
#        self.utility.makePopup(rightMouse, self.onModerate, 'rModerate')              
#        self.utility.makePopup(rightMouse, self.onRecommend, 'rRecommend')        
#        #if secret:
#        self.utility.makePopup(rightMouse, self.onDownloadOpen, 'rDownloadOpenly')
#        #else:
#        self.utility.makePopup(rightMouse, self.onDownloadSecret, 'rDownloadSecretly')
#        rightMouse.AppendSeparator()
#        self.utility.makePopup(rightMouse, None, 'rLibraryOptions')
#        self.utility.makePopup(rightMouse, None, 'rRemoveFromList')
#        self.utility.makePopup(rightMouse, None, 'rRemoveFromListAndHD')  
        

##        #Add the priority submenu if this is a multi-file torrent
##        if not self.torrent.files.isFile():
##            prioritymenu = self.makePriorityMenu()
##            if prioritymenu is not None:
##                menu.AppendMenu(-1, self.utility.lang.get('rpriosetting'), prioritymenu)
##
##         Popup the menu.  If an item is selected then its handler
##         will be called before PopupMenu returns.
##        if event is None:
##             use the position of the first selected item (key event)
##            position = self.GetItemPosition(s[0])
##        else:
##             use the cursor position (mouse event)
##            position = event.GetPoint()

        #position = event.GetPoint()
#        self.PopupMenu(rightMouse, (-1,-1))


    
       
#    def doubleClicked(self, event):
#        # open torrent details frame
#        abctorrent = self.data.get('abctorrent')
#        if abctorrent:
#            abctorrent.dialogs.advancedDetails()
#            
#        event.Skip()
        
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
            raise RuntimeException("arno: core: engine class no longer exists")
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
            if DEBUG:
                print >>sys.stderr,'lip: abcTorrentShutdown with right infohash'
            
            abctorrent = self.data.get('abctorrent')
            progresstxt = abctorrent.getColumnText(COL_PROGRESS)
            progress = float(progresstxt[:-1])
            # store the progress of this torrent
            newdata = {'progress':progress, 'destdir':abctorrent.files.dest}
            self.data.update(newdata)
            
            if DEBUG:
                print >>sys.stderr,'lip: Save destination?: %s and progress: %f' % (`self.data['destdir']`, self.data['progress'])
            # only save new data (progression and destdir, no other data or torrent
            self.utility.torrent_db.updateTorrent(infohash, **newdata)
            # Now delete the abctorrent object reference
            del self.data['abctorrent']

    
    def abctorrentFinished(self, infohash):
        """
        The download just finished. Call standardOverview to resort.
        """
        
        if self.data.get('infohash') == infohash:
            standardOverview = self.guiUtility.standardOverview
            if standardOverview.mode == 'libraryMode':
                standardOverview.filterChanged(None)
                #print 'filterChanged()called'

