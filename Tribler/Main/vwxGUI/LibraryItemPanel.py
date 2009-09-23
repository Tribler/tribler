# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information

import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from copy import deepcopy
from wx.lib.stattext import GenStaticText as StaticText

from Tribler.Core.API import *
from Tribler.Core.Utilities.unicode import *
from Tribler.Core.Utilities.utilities import *
# LAYERVIOLATION
from Tribler.Core.Overlay.MetadataHandler import get_filename

from Tribler.Main.Utility.constants import * 
from Tribler.Main.Utility import *
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.filesItemPanel import ThumbnailViewer, libraryModeThumbSize
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
    FS_PAUSE = 10
elif sys.platform == 'win32':
    FS_TITLE = 8
    FS_PERC = 6
    FS_SPEED = 7
    FS_PAUSE = 7
else:
    FS_TITLE = 8
    FS_PERC = 7
    FS_SPEED = 7
    FS_PAUSE = 7
    
    
statusLibrary  = {"downloading"     : "LibStatus_downloading.png",
                  "stopped"         : "LibStatus_stopped.png",
                  "boosting"        : "LibStatus_boosting.png",
                  "completed"       : "LibStatus_completed.png",
                  "seeding"         : "LibSatus_seeding.png"}


class LibraryItemPanel(wx.Panel):
    def __init__(self, parent, keyTypedFun = None, name='regular'):

        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        if self.parent.GetName() == 'libraryGrid':
            self.listItem = (self.parent.viewmode == 'list')
#            self.guiserver = parent.guiserver
        else:
            self.listItem = True
#            self.guiserver = GUIServer.getInstance()
        
            
        self.guiserver = parent.guiserver
        self.triblerGrey = wx.Colour(128,128,128)
        
        #self.statusTorrent = TorrentStatus(self)
        self.ThumbnailViewer = ThumbnailViewer
#        self.listItem = True # library always in listmode
        self.data = None
        self.status = None
        self.rightMouse = None
        self.titleLength = 40 # num characters
        self.selected = False
        self.warningMode = False
        self.summary = None
        self.oldCategoryLabel = None
        self.name = name
        self.torrentDetailsFrame = None
        self.first = True
        self.containsvideo = None # None means unknown, True=yes, False=no ;o)
        
        self.addComponents()
            
        #self.Bind(wx.EVT_RIGHT_DOWN, self.rightMouseButton)             
        
#        self.Bind(wx.EVT_PAINT, self.OnPaint)
        #self.Bind(wx.EVT_RIGHT_DOWN, self.rightMouseButton)   
        self.cache_progress = {}
        self.gui_server = GUITaskQueue.getInstance()

#        self.SetMinSize((-1, 130))
        self.selected = False
        self.Show()
        self.Refresh()
        self.Layout()
        
        

        self.triblerStyles = TriblerStyles.getInstance()
    def addComponents(self):


        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)        
        self.Show(False)

        self.SetMinSize((660,22))

        self.vSizerOverall = wx.BoxSizer(wx.VERTICAL)
       

        imgpath = os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","5.0","line3.png")
        self.line_file = wx.Image(imgpath, wx.BITMAP_TYPE_ANY)            

        self.hLine = wx.StaticBitmap(self, -1, wx.BitmapFromImage(self.line_file))



        #self.hLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(220,2),wx.LI_HORIZONTAL)
        #self.hLine.SetBackgroundColour((255,0,0))
        self.vSizerOverall.Add(self.hLine, 0, wx.FIXED_MINSIZE|wx.EXPAND, 0) ##           


        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.vSizerOverall.Add(self.hSizer, 0 , wx.EXPAND, 0)

        self.SetBackgroundColour(wx.WHITE)

        
        # Add Spacer
        self.hSizer.Add([5,0],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        
        
        
        # Add thumb
        #self.thumb = ThumbnailViewer(self, 'libraryMode')
        #self.thumb.setBackground(wx.BLACK)
        #self.thumb.SetSize(libraryModeThumbSize)
        #self.thumb.Hide()
        #self.hSizer.Add(self.thumb, 0, wx.ALL, 2)
        

        # add play button
        self.library_play = tribler_topButton(self, name="library_play") ## before libraryPlay
        self.library_play.setBackground(wx.WHITE)
        self.library_play.SetMinSize((17,17))
        self.library_play.SetSize((17,17))
        self.hSizer.Add(self.library_play, 0, wx.TOP|wx.ALIGN_RIGHT, 2) 
        self.library_play.Hide()  
 


        self.hSizer.Add([5,0],0,wx.FIXED_MINSIZE,0)        


        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(250,14))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(FS_TITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((250,14))
        self.hSizer.Add(self.title,0,wx.TOP,3)
        
        self.hSizer.Add([20,0],0,wx.FIXED_MINSIZE,0)        



 
        # estimated time left
        if sys.platform == 'win32':
            self.eta = wx.StaticText(self,-1,"                ") 
        else:
            self.eta = wx.StaticText(self,-1,"    ")
        self.eta.SetForegroundColour((150,150,150))
        if sys.platform == 'win32':
            self.eta.SetMinSize((120,14))
        else:
            self.eta.SetMinSize((50,14))
        self.eta.SetFont(wx.Font(FS_PERC,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))                
        #self.hSizer.Add(self.eta, 0, wx.FIXED_MINSIZE, 0)
 

        self.pause_resume = wx.StaticText(self,-1,"Pause",wx.Point(0,0),wx.Size(50,14))
        self.pause_resume.SetForegroundColour((255,51,0)) 
        self.pause_resume.SetFont(wx.Font(FS_PAUSE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.pause_resume.Bind(wx.EVT_LEFT_UP, self.pause_resume_clicked)

        self.hSizer.Add(self.pause_resume, 0, wx.TOP,3)



        # remove from library button
        self.remove = tribler_topButton(self, name="remove")
        self.remove.setBackground(wx.WHITE)
        self.remove.SetMinSize((17,17))
        self.remove.SetSize((17,17))
        self.hSizer.Add(self.remove, 0, wx.TOP|wx.ALIGN_RIGHT, 2) 

        if sys.platform == 'win32':
            self.hSizer.Add([40,0],0,wx.FIXED_MINSIZE,0)        
        elif sys.platform == 'linux2':
            self.hSizer.Add([55,0],0,wx.FIXED_MINSIZE,0)
        else:
            self.hSizer.Add([60,0],0,wx.FIXED_MINSIZE,0)


        if sys.platform == 'win32':
            size = 55
        elif sys.platform == 'linux2':
            size = 45
        else:
            size = 45
        self.speedDown2 = wx.StaticText(self,-1,"0.0 KB/s",wx.Point(274,3),wx.Size(size,12), wx.ST_NO_AUTORESIZE)                                
        self.speedDown2.SetForegroundColour(wx.BLACK) 
        self.speedDown2.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.speedDown2.SetMinSize((size,12))        


        self.speedUp2   = wx.StaticText(self,-1,"0.0 KB/s",wx.Point(274,3),wx.Size(size,12), wx.ST_NO_AUTORESIZE)                        
        self.speedUp2.SetForegroundColour(wx.BLACK) 
        self.speedUp2.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.speedUp2.SetMinSize((size,12))


        self.hSizer.Add(self.speedDown2, 0, wx.TOP|wx.EXPAND, 4)
        self.hSizer.Add([18,0],0,0,0)
        self.hSizer.Add(self.speedUp2, 0, wx.TOP|wx.EXPAND, 4)   

        if sys.platform == 'linux2':
            self.hSizer.Add([25,0],0,wx.FIXED_MINSIZE,0)
        elif sys.platform == 'darwin':   
            self.hSizer.Add([21,0],0,wx.FIXED_MINSIZE,0)
        else:
            self.hSizer.Add([30,0],0,wx.FIXED_MINSIZE,0)
        self.pb = ProgressBar(self,pos=wx.Point(450,0),size=wx.Size(60,5))
        self.pb.SetMinSize((100,5))        

        self.pbSizer = wx.BoxSizer(wx.VERTICAL)
        if sys.platform == 'win32':
            self.pbSizer.Add([0,3],0,wx.FIXED_MINSIZE,0)        
        else:
            self.pbSizer.Add([0,1], 0, wx.FIXED_MINSIZE, 0)
        self.pbSizer.Add(self.pb,0,wx.FIXED_MINSIZE,0)        
        self.pbSizer.Add([0,1],0,wx.FIXED_MINSIZE,0)  
        self.pbSizer.Add(self.eta,0,wx.FIXED_MINSIZE,0)  
      
                

        # Percentage
        self.percentage = wx.StaticText(self,-1,"?%",wx.Point(800,0),wx.Size(40,14))
        self.percentage.SetForegroundColour(self.triblerGrey)
        self.percentage.SetFont(wx.Font(FS_PERC,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
       

        self.hSizer.Add(self.pbSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 0) 
        self.hSizer.Add([9,0],0,wx.FIXED_MINSIZE,0)        
        self.hSizer.Add(self.percentage, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 0)         
        
        # pause/stop button
        #self.pause = SwitchButton(self, -1, wx.Point(542,3), wx.Size(16,16),name='pause' )
        #self.hSizer.Add(self.pause,0,wx.TOP|wx.FIXED_MINSIZE,2)        
        
        # V Line
        ## self.addLine()

        self.hSizer.Add([14,0],0,wx.FIXED_MINSIZE,0)        
      

        
        # V Line                
        ## self.addLine()
                
        # Status Icon
##        self.statusIcon = ImagePanel(self, -1, name="LibStatus_boosting")        
##        self.statusIcon.searchBitmap(name = statusLibrary["stopped"])
##
##        self.hSizer.Add(self.statusIcon, 0, wx.TOP|wx.RIGHT|wx.EXPAND, 2)
        
        # Status message
        ##self.statusField = wx.StaticText(self, -1,'', wx.Point(),wx.Size())
        ##self.statusField.SetForegroundColour(self.triblerGrey)        
        ##self.statusField.SetFont(wx.Font(FS_SPEED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        ##self.statusField.SetMinSize((60,12))
#        self.statusField.SetMinSize((125,12))
        ##self.hSizer.Add(self.statusField, 0, wx.TOP, 4)

        ##self.hSizer.Add([20,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0) 
        
        # V Line
        ## self.addLine()

        # Boost button
        ##self.boost = SwitchButton(self, name="boost")
        ##self.boost.setBackground(wx.WHITE)
        ##self.boost.SetSize((50,16))
        ##self.boost.setEnabled(False)
        ##self.hSizer.Add(self.boost, 0, wx.TOP|wx.ALIGN_RIGHT, 2)
        ##self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)

        # Play Fast
        ##self.playFast = SwitchButton(self, name="playFast")
        ##self.playFast.setBackground(wx.WHITE)
        ##self.playFast.SetSize((39,16))
        ##self.playFast.setEnabled(False)
        ##self.hSizer.Add(self.playFast, 0, wx.TOP|wx.ALIGN_RIGHT, 2)
        ##self.hSizer.Add([2,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)   

        # Play
        ##self.playsmall = SwitchButton(self, name="playsmall") ## before libraryPlay
        ##self.playsmall.setBackground(wx.WHITE)
        ##self.playsmall.SetSize((16,16))
        ##self.playsmall.setEnabled(True)
        ##self.hSizer.Add(self.playsmall, 1, wx.TOP|wx.ALIGN_RIGHT, 2)          

        ##self.hSizerSummary = wx.BoxSizer(wx.HORIZONTAL) ##
        ##self.vSizerOverall.Add(self.hSizerSummary, 1, wx.FIXED_MINSIZE|wx.EXPAND, 0) ##           

        
       
            
        # Add Refresh        
        self.SetSizer(self.vSizerOverall);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
#        print 'tb > self.bgPanel size = %s' % self.titleBG.GetSize(), self.titleBG.GetPosition()
        
        # 2.8.4.2 return value of GetChildren changed
        wl = [self]
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            #window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            # Arno, 2009-03-05: this binding persists, so even when results page
            # is shown after libView, hitting the delete button generates
            # an event in this class.
            #window.Bind(wx.EVT_KEY_UP, self.keyTyped)                         
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)             

            
    def getColumns(self):
        if sys.platform == 'win32':
            title = 'Down && Up Speed'
        else: 
            title = 'Down &&&& Up Speed'
        return [{'sort':'name', 'reverse':True, 'title':'Name', 'width':400,'weight':0,'tip':self.utility.lang.get('C_filename'), 'order':'down'},
                {'sort':'??', 'dummy':True, 'title':title,'width':130, 'tip':self.utility.lang.get('C_downupspeed')}, 
                {'sort':'progress', 'title':'Completion/ETA', 'width':116, 'tip':self.utility.lang.get('C_progress')}               
                ]     

    # pause or resume a download
    def pause_resume_clicked(self, event):
        if event.LeftUp():
            if self.pause_resume.GetLabel() == 'Pause':
                self.pauseDownload()
            else:
                self.resumeDownload()
        else:
            event.Skip()


    def pauseDownload(self):
        self.pause_resume.SetLabel('Resume')
        if self.data.get('ds'):
            ds = self.data.get('ds')
            ds.get_download().stop()



    def resumeDownload(self):
        self.pause_resume.SetLabel('Pause')
        if self.data.get('ds'):
            ds = self.data.get('ds')
            ds.get_download().restart()

                  
    def refreshData(self):
        self.setData(self.data)
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,0),wx.LI_VERTICAL)
#        vLine.Show(False)
        self.vSizer1.Add(vLine, 0, wx.LEFT|wx.RIGHT, 3)
        
    def updateProgress(self, infohash, progress):
        #print >> sys.stderr, 'Lib: updateProgress: %s %s' % (self.title.GetLabel(), progress)
        
        if infohash not in self.cache_progress:
            self.cache_progress[infohash] = 0 # progress
        now = time()
        if progress - self.cache_progress[infohash] > 1:
            self.cache_progress[infohash] = progress
            self.guiserver.add_task(lambda:self.updateProgressInDB(infohash,progress), 0)
        
    def updateProgressInDB(self, infohash, progress):
        try:
            mypref_db = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
            mypref_db.updateProgress(infohash, progress, commit=True)
        except:
            print_exc()    # lock error
        
    def setData(self, torrent):
        # set bitmap, rating, title
        
        #print_stack()
        #print >>sys.stderr,"lip: setData called"       

        #if torrent == None and self.library_play is not None:
        #    self.library_play.Destroy()
        
        if threading.currentThread().getName() != "MainThread":
            print >>sys.stderr,"lip: setData called by nonMainThread!",threading.currentThread().getName()
            print_stack()

        if self.data is None:
            oldinfohash = None
        else:
            oldinfohash = self.data['infohash']
        
        self.data = torrent
        
        if torrent is None:
            #for child in self.GetChildren():
            #    child.Hide()
            self.title.Hide()
            self.pb.Hide()
            self.percentage.Hide()
            self.speedDown2.Hide()
            self.speedUp2.Hide()
            self.remove.Hide()
            self.pause_resume.Hide()
            self.hLine.Show()
            torrent = {}
        else:
            for child in self.GetChildren():
                child.Show()
        
        if torrent and oldinfohash != self.data['infohash']:
            self.containsvideo = None
            
        if torrent.get('ds'):
            #print '%s is an active torrent' % torrent['name']
            ds = torrent['ds']
            #abctorrent.setLibraryPanel(self)
            
            # Check if torrent just finished for resort
            #abctorrent.status.checkJustFinished()


            if ds.get_status() == DLSTATUS_STOPPED:
                self.pause_resume.SetLabel('Resume')

            if ds.get_status() in (DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING):
                self.pause_resume.SetLabel('Pause')

            
            #self.pb.setEnabled(True)
            self.pb.Show()
#            self.downSpeed.Show()
            self.speedDown2.Show()
#            self.upSpeed.Show()
            self.speedUp2.Show()
            
            dls = ds.get_current_speed(DOWNLOAD)*1024 # speed_format needs byte/s
            uls = ds.get_current_speed(UPLOAD)*1024


            self.speedDown2.SetLabel(self.utility.speed_format_new(dls)) 
            self.speedUp2.SetLabel(self.utility.speed_format_new(uls))

            if DEBUG:
                print >> sys.stderr, '%s %s %s' % (`ds.get_download().get_def().get_name()`, ds.get_progress(), dlstatus_strings[ds.get_status()])
                if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                    print >> sys.stderr, "ERROR IS",ds.get_error()
            
            finished = ds.get_progress() == 1.0 or ds.get_status() == DLSTATUS_SEEDING
            progress = (ds.get_progress() or 0.0) * 100.0
            #print >> sys.stderr, '****** libraryitempanel:', torrent['torrent_id'], progress
            self.updateProgress(torrent['infohash'], progress)
            
            self.percentage.SetLabel('%.1f%%' % progress)
            eta = self.utility.eta_value(ds.get_eta(), truncate=2)
            if finished:
                eta = "Finished"
            elif eta == '' or eta.find('unknown') != -1:
                eta = ''
            self.eta.SetLabel(eta)
            self.eta.SetToolTipString(self.utility.lang.get('eta')+eta)
                            
            havedigest = None
            showPlayButton = False

            active = ds.get_status() in (DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING)
            
            # Allow STOPPED_ON_ERROR, sometimes transient
            startable = not ds.get_status() in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
            if startable:
                isVideo = bool(ds.get_download().get_def().get_files(exts=videoextdefaults))
                showPlayButton = isVideo
                havedigest = ds.get_pieces_complete()
                
            if finished:
                self.pb.reset(colour=2) # Show as complete
                self.pb.Refresh()
            elif havedigest:
                self.pb.set_pieces(havedigest)
                self.pb.Refresh()
            elif progress > 0:
                self.pb.reset(colour=1) # Show as having some
                self.pb.Refresh()
            else:
                self.pb.reset(colour=0) # Show as having none
                self.pb.Refresh()
                
            self.library_play.setEnabled(showPlayButton)            
                
        elif torrent: # inactive torrent
            
            if not self.listItem:
                #self.pb.setEnabled(False)
                self.downSpeed2.Hide()
                self.speedDown2.SetLabel('--')
                self.upSpeed.Hide()            
                self.speedUp2.SetLabel('--')
                self.library_play.setEnabled(False)
            else:
                if self.containsvideo is None:
                    self.async_check_torrentfile_contains_video(torrent)
                if self.containsvideo is not None:
                    self.library_play.setEnabled(self.containsvideo)
                else:
                    self.library_play.setEnabled(False)
            
            #self.eta.SetLabel('')
            
            if torrent.get('progress') != None:                
                self.percentage.SetLabel('%0.1f%%' % torrent['progress'])
                self.pb.setNormalPercentage(torrent['progress'])
            else:
                self.percentage.SetLabel('?')
                self.pb.reset()
            
            self.pb.Show()
            self.pb.Refresh()
            
        if torrent and oldinfohash != self.data['infohash']:
            if torrent.get('name'):
                title = torrent['name'][:self.titleLength]
                self.title.Show()
                self.title.SetLabel(title)
                self.title.Wrap(self.title.GetSize()[0])
                self.title.SetToolTipString(torrent['name'])
    
                # Only reload thumb when changing torrent displayed
                ##if torrent['infohash'] != oldinfohash:
                    #print >>sys.stderr,"REFRESH THUMBNAIL",`torrent['name']`
                    ##self.thumb.setTorrent(torrent)

                self.remove.SetToolTipString(self.utility.lang.get('C_remove'))
 

            
            else:
                self.title.SetLabel('')
                self.title.SetToolTipString('')
                self.title.Hide()
                self.hLine.Show()
               
        self.Layout()
        self.Refresh()
        self.GetContainingSizer().Layout()
        self.parent.Refresh()
        
    def select(self, rowIndex, colIndex, ignore1, ignore2, ignore3):
        self.selected = True        
        self.guiUtility.standardOverview.selectedTorrent = self.data['infohash']
        
    def deselect(self, rowIndex, colIndex):
        self.hLine.Show()
        self.selected = False
        
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'lib: deleting'
                    # Arno; 2007-05-11: TODO: use right method here, deleteTorrent does nothing at the 
                    # moment, see below for right method
                    #self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def setIndex(self, index):
        self.index=index


    def mouseAction(self, event):
        #if DEBUG:
        #    print >>sys.stderr,"lip: mouseaction: name",event.GetEventObject().GetName()

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
            
            
        if self.data.get('ds'):
            ds = self.data.get('ds')
#            if name == 'deleteLibraryitem':
#                removeFiles = False
#                ds.get_download().stop() # ??
#                            
            if name == 'pause':
                # ARNOCOMMENT: need to get/store/cache current status of Download somehow
                if ds.get_status() == DLSTATUS_STOPPED or ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                    if ds.get_download().get_def().get_live():
                        self.switch_to_vod(ds)
                    else:
                        ds.get_download().restart()
                        obj.setToggled(False)
                else:
                    ds.get_download().stop()
                    obj.setToggled(True)
                    
                    from Tribler.Video.VideoPlayer import VideoPlayer
                    videoplayer = VideoPlayer.getInstance()
                    stopd = ds.get_download()
                    playd = videoplayer.get_vod_download()
                    if stopd == playd:
                        videoplayer.close()
                    
            elif name == 'library_play':
                self.guiUtility.standardDetails.setVideodata(self.guiUtility.standardDetails.getData())
                self._get_videoplayer(exclude=ds).videoframe.get_videopanel().SetLoadingText(self.guiUtility.standardDetails.getVideodata()['name'])
                if sys.platform == 'darwin':
                    self._get_videoplayer(exclude=ds).videoframe.show_videoframe()
                    self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Refresh()
                    self._get_videoplayer(exclude=ds).videoframe.get_videopanel().Layout()

                self.play(ds)
                
                
            elif name == 'remove':
                from Tribler.Video.VideoPlayer import VideoPlayer
                videoplayer = VideoPlayer.getInstance()
                playd = videoplayer.get_vod_download()
                removed = ds.get_download()
                if playd == removed:
                    self._get_videoplayer(exclude=ds).stop_playback()




                #if self.guiUtility.standardDetails.getVideodata() is not None: 
                #    if self.guiUtility.standardDetails.getVideodata()['name'] == self.guiUtility.standardDetails.getData()['name']:
                #        self.guiUtility.standardDetails.setVideodata(None)
                #        self._get_videoplayer(exclude=ds).stop_playback()

                
        else: # no abctorrent
            #print >>sys.stderr,"lip: mouseAction: No ds"
            if name == 'pause':
                 #playbutton
                 dest_dir = self.data.get('destdir')
                 if dest_dir is not None:
                     # Start torrent again
                     if DEBUG:
                         print >>sys.stderr,'lip: starting torrent %s with data in dir %s' % (repr(self.data['name']), dest_dir)
                         
                     if os.path.isfile(dest_dir):
                         # Arno: the 4.1 database values are wrong, also for 
                         # single-file torrents the content_dir is 
                         # "savedir"+torrentname. Try to componsate
                         dest_dir = os.path.dirname(dest_dir)
                         print >>sys.stderr,'lip: starting torrent %s with data in corrected 4.1 dir %s' % (repr(self.data['name']), dest_dir)
                         
                     self.guiUtility.standardDetails.download(self.data, dest = dest_dir, force = True)
                 
                 elif DEBUG:
                     print >>sys.stderr,'lip: Could not make abctorrent active, no destdir in dictionary: %s' % repr(self.data.get('name'))
                     
            elif name == 'library_play':
                # Todo: make non-abctorrent files playable.
                dest_dir = self.data.get('destdir')
                
                if dest_dir is None: # workaround for testing
                    dest_dir = get_default_dest_dir()
                
                if  dest_dir is not None:
                    # Start torrent again
                    if DEBUG:
                        print >>sys.stderr,'lip: starting torrent %s with data in dir %s' % (repr(self.data['name']), dest_dir)
                    self.guiUtility.standardDetails.download(self.data, dest = dest_dir, force = True, vodmode = True)
                    
                elif DEBUG:
                    print >>sys.stderr,'lip: Could not make abctorrent active, no destdir in dictionary: %s' % repr(self.data.get('name')) 
               
        if name == 'deleteLibraryitem':
            # delete works for active and inactive torrents
            self.guiUtility.onDeleteTorrentFromLibrary()
            
        if event.RightDown():
            self.rightMouseButton(event)
   
   
    def rightMouseButton(self, event):     
        # Open right-click menu (windows menu key)
        # >>makePopup(self, menu, event = None, label = "", extralabel = "", bindto = None):

        menu = self.guiUtility.OnRightMouseAction(event)
        if menu is not None:
            self.PopupMenu(menu, (-1,-1))        
        
        
    def getIdentifier(self):
        if self.data:
            return self.data.get('infohash')
        else:
            return None

    def _get_videoplayer(self, exclude=None):
        """
        Returns the VideoPlayer instance and ensures that it knows if
        there are other downloads running.
        """

        # 22/08/08 Boudewijn: The videoplayer has to know if there are
        # downloads running.
        other_downloads = False
        for ds in self.parent.gridManager.dslist:
            if ds is not exclude and ds.get_status() not in (DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR):
                other_downloads = True
                break

        videoplayer = VideoPlayer.getInstance()
        videoplayer.set_other_downloads(other_downloads)
        return videoplayer
        
    def play(self,ds):
        
        print >>sys.stderr,"lip: play"

        self.pause_resume.SetLabel('Pause')

        self._get_videoplayer(exclude=ds).stop_playback() # stop current playback

        self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.agVideo.Show()
        self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.agVideo.Play()
        self._get_videoplayer(exclude=ds).videoframe.get_videopanel().vlcwin.Refresh()
        
        self._get_videoplayer(exclude=ds).play(ds)
    
            
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


    def async_check_torrentfile_contains_video(self,torrent):
        if 'torrent_file_name' in torrent and torrent['torrent_file_name'] != '':
            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])
            
            if DEBUG:
                print "lip: Scheduling read videofiles from",`torrent['name']`,"from",torrent_filename
            
            def loadMetaDataNow():
                try:
                    self.guiservthread_loadMetadata(torrent,torrent_filename)
                except wx.PyDeadObjectError:
                    pass
                
            try:
                self.GetParent().guiserver.add_task(loadMetaDataNow,0)
            except wx.PyDeadObjectError:
                # ARNO: TODO: The FileItemPanels that use this ThumbnailViewer now get deleted, and thus
                # also the ThumbnailViewer objects. Or at least the C++ part of them. As a result we
                # can no longer schedule these loadMetadata callbacks on the GUITaskQueue thread. 
                #
                # At the moment, the wx code protects us, and throws an exception that the C++ part
                # of the ThumbnailViewer object is gone. But we should clean this up. 
                pass
        else:
            self.containsvideo = False
        
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
