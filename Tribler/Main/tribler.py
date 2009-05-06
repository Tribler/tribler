#!/usr/bin/python

#########################################################################
#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#
# see LICENSE.txt for license information
#########################################################################

# Arno: M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#

# modify the sys.stderr and sys.stdout for safe output
import Tribler.Debug.console

import os,sys
import urllib
original_open_https = urllib.URLopener.open_https
import M2Crypto
urllib.URLopener.open_https = original_open_https

# Arno, 2008-03-21: see what happens when we disable this locale thing. Gives
# errors on Vista in "Regional and Language Settings Options" different from 
# "English[United Kingdom]" 
#import locale
import signal
import commands
import pickle

#try:
#    import wxversion
#    wxversion.select('2.8')
#except:
#    pass
import wx
import wx.animate
from wx import xrc
#import hotshot

from threading import Thread, Event,currentThread,enumerate
from time import time, ctime, sleep
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib2
import tempfile


import Tribler.Main.vwxGUI.font as font
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
from Tribler.Main.vwxGUI.MainFrame import MainFrame
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
## from Tribler.Main.vwxGUI.TasteHeart import set_tasteheart_bitmaps
## from Tribler.Main.vwxGUI.perfBar import set_perfBar_bitmaps
## from Tribler.Main.vwxGUI.FriendsItemPanel import fs2text 
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.notification import init as notification_init
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import *

from Tribler.Category.Category import Category
from Tribler.Policies.RateManager import UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager
from Tribler.Policies.SeedingManager import GlobalSeedingManager
from Tribler.Utilities.Instance2Instance import *
from Tribler.Utilities.LinuxSingleInstanceChecker import *

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid_short
#import Tribler.Core.CacheDB.friends as friends 

from Tribler.Video.defs import *
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoFrame import VideoDummyFrame, VideoFrame, VideoMacFrame

#import pdb

I2I_LISTENPORT = 57891
VIDEOHTTP_LISTENPORT = 6878
SESSION_CHECKPOINT_INTERVAL = 1800.0 # seconds

DEBUG = False
ALLOW_MULTIPLE = True

##############################################################
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App):
    def __init__(self, redirectstderrout, params, single_instance_checker, installdir):
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.installdir = installdir
        self.error = None
        self.last_update = 0
        self.update_freq = 0    # how often to update #peers/#torrents

        self.guiserver = GUITaskQueue.getInstance()
        self.said_start_playback = False
        self.decodeprogress = 0

        self.old_reputation = 0

        
        try:
            ubuntu = False
            if sys.platform == "linux2":
                f = open("/etc/issue","rb")
                data = f.read(100)
                f.close()
                if data.find("Ubuntu 8.10") != -1:
                    ubuntu = True
                    
            if not redirectstderrout and ubuntu:
                # On Ubuntu 8.10 not redirecting output causes the program to quit
                wx.App.__init__(self, redirect=True)
            else:
                wx.App.__init__(self, redirectstderrout)
        except:
            print_exc()
        
    def OnInit(self):
        try:
            print type(Session.get_default_state_dir()), repr(Session.get_default_state_dir())
            print type(self.installdir), repr(self.installdir)
            self.utility = Utility(self.installdir,Session.get_default_state_dir())
            self.utility.app = self

            #self.postinitstarted = False
            """
            Hanging self.OnIdle to the onidle event doesnot work under linux (ubuntu). The images in xrc files
            will not load in any but the filespanel.
            """
            #self.Bind(wx.EVT_IDLE, self.OnIdle)
            
        
            # Set locale to determine localisation
            #locale.setlocale(locale.LC_ALL, '')

            sys.stderr.write('Client Starting Up.\n')
            sys.stderr.write('Build: ' + self.utility.lang.get('build') + '\n')

            bm = wx.Bitmap(os.path.join(self.utility.getPath(),'Tribler','Images','splash.jpg'),wx.BITMAP_TYPE_JPEG)
            #s = wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN
            #s = wx.SIMPLE_BORDER|wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT
            self.splash = wx.SplashScreen(bm, wx.SPLASH_CENTRE_ON_SCREEN|wx.SPLASH_TIMEOUT, 1000, None, -1)
            
            # Arno: Do heavy startup on GUI thread after splash screen has been
            # painted.
            self.splash.Show()
            "Replacement for self.Bind(wx.EVT_IDLE, self.OnIdle)"
            wx.CallAfter(self.PostInit)    
            return True
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

    def OnIdle(self,event=None):
        if not self.postinitstarted:
            self.postinitstarted = True
            wx.CallAfter(self.PostInit)
            # Arno: On Linux I sometimes have to move the mouse into the splash
            # for the rest of Tribler to start. H4x0r
            if event is not None:
                event.RequestMore(True)
                event.Skip()


    def PostInit(self):
        try:
            # On Linux: allow painting of splash screen first.
            wx.Yield()
            
            # Initialise fonts
            font.init()

            
            self.utility.postAppInit(os.path.join(self.installdir,'Tribler','Images','tribler.ico'))
            
            # H4x0r a bit
            ## set_tasteheart_bitmaps(self.utility.getPath())
            ## set_perfBar_bitmaps(self.utility.getPath())

            cat = Category.getInstance(self.utility.getPath())
            cat.init_from_main(self.utility)

            # Put it here so an error is shown in the startup-error popup
            # Start server for instance2instance communication
            self.i2iconnhandler = InstanceConnectionHandler(self.i2ithread_readlinecallback)
            self.i2is = Instance2InstanceServer(I2I_LISTENPORT,self.i2iconnhandler) 
            self.i2is.start()

            self.triblerStyles = TriblerStyles.getInstance()
            
            # Fire up the VideoPlayer, it abstracts away whether we're using
            # an internal or external video player.
            playbackmode = self.utility.config.Read('videoplaybackmode', "int")
            self.videoplayer = VideoPlayer.getInstance(httpport=VIDEOHTTP_LISTENPORT)
            self.videoplayer.register(self.utility,preferredplaybackmode=playbackmode)

            notification_init( self.utility )

            #
            # Read and create GUI from .xrc files
            #
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params)
            self.res = xrc.XmlResource(os.path.join(self.utility.getPath(),'Tribler', 'Main','vwxGUI','MyFrame.xrc'))
            self.guiUtility.xrcResource = self.res
            self.frame = self.res.LoadFrame(None, "MyFrame")
            self.guiUtility.frame = self.frame

            self.frame.set_wxapp(self)
      

            self.guiUtility.scrollWindow = xrc.XRCCTRL(self.frame, "level0")
            self.guiUtility.mainSizer = self.guiUtility.scrollWindow.GetSizer()
            self.frame.topBackgroundRight = xrc.XRCCTRL(self.frame, "topBG3")
            #self.guiUtility.scrollWindow.SetScrollbars(1,1,1100,683)
            #self.guiUtility.scrollWindow.SetScrollRate(15,15)
            self.frame.mainButtonPersons = xrc.XRCCTRL(self.frame, "mainButtonPersons")
            self.frame.messageField = xrc.XRCCTRL(self.frame, "messageField")
            self.frame.pageTitle = xrc.XRCCTRL(self.frame, "pageTitle")
            self.frame.pageTitlePanel = xrc.XRCCTRL(self.frame, "pageTitlePanel")
            self.frame.standardDetails = xrc.XRCCTRL(self.frame, "standardDetails")
            self.frame.standardOverview = xrc.XRCCTRL(self.frame, "standardOverview")
            self.frame.firewallStatus = xrc.XRCCTRL(self.frame, "firewallStatus")
            
            # Make sure self.utility.frame is set
            self.startAPI()
            self.guiUtility.open_dbs()
            ##self.guiUtility.initStandardOverview(self.frame.standardOverview)

            # TEST: add mod for Gopher
            """
            moderation_cast_db = self.utility.session.open_dbhandler(NTFY_MODERATIONCAST)
            moderation = {}
            from Tribler.Core.CacheDB.sqlitecachedb import bin2str
            moderation['infohash'] = bin2str('\xbd\x0c\x86\xf9\xe4JE\x0e\xff\xff\x16\xedF01*<| \xe9')
            moderation_cast_db.addOwnModeration(moderation)
            """
            
            self.frame.searchtxtctrl = xrc.XRCCTRL(self.frame, "tx220cCCC")
            self.frame.search_icon = xrc.XRCCTRL(self.frame, "search_icon")
            self.frame.files_friends = xrc.XRCCTRL(self.frame, "files_friends")
            self.frame.top_image = xrc.XRCCTRL(self.frame, "top_image")
            
            self.frame.top_bg = xrc.XRCCTRL(self.frame,"top_search")
            self.frame.top_bg.set_frame(self.frame)
            self.frame.pagerPanel = xrc.XRCCTRL(self.frame,"pagerPanel")
            self.frame.horizontal = xrc.XRCCTRL(self.frame, "horizontal")
            self.frame.changePlay = xrc.XRCCTRL(self.frame, "changePlay")
 
            self.frame.BL = xrc.XRCCTRL(self.frame, "BL")
            self.frame.BR = xrc.XRCCTRL(self.frame, "BR")



            # on linux pagerpanel needs a SetMinSize call
            if sys.platform == "linux2":
                self.frame.pagerPanel.SetMinSize((626,20))
            elif sys.platform == 'darwin':
                self.frame.pagerPanel.SetMinSize((674,21))
            else:
                self.frame.pagerPanel.SetMinSize((626,20))



            # videopanel
            self.frame.videoparentpanel = xrc.XRCCTRL(self.frame,"videopanel")
            if sys.platform == 'darwin':
                self.frame.videoparentpanel.SetBackgroundColour((216,233,240))
                self.frame.videoparentpanel.Hide()
            if sys.platform == "linux2":
                self.frame.videoparentpanel.SetMinSize((363,400))
            elif sys.platform == 'win32':
                self.frame.videoparentpanel.SetMinSize((363,400))
            else:
                self.frame.videoparentpanel.SetMinSize((350,240))


            logopath = os.path.join(self.utility.getPath(),'Tribler','Main','vwxGUI','images','5.0','video.gif')
            if sys.platform == 'darwin':
                self.frame.videoframe = VideoMacFrame(self.frame.videoparentpanel,self.utility,"Videoplayer",os.path.join(self.installdir,'Tribler','Images','tribler.ico'),self.videoplayer.get_vlcwrap(),logopath)
                self.videoplayer.set_videoframe(self.frame.videoframe)
            else:
                self.frame.videoframe = VideoDummyFrame(self.frame.videoparentpanel,self.utility,self.videoplayer.get_vlcwrap(),logopath)
                self.videoplayer.set_videoframe(self.frame.videoframe)

            if sys.platform == "linux2":
                # On Linux the _PostInit does not get called if the thing
                # is not shown. We need the _PostInit to be called to set
                # the GUIUtility.standardOverview, etc. member variables.
                #
                wx.CallAfter(self.frame.standardOverview.Hide)
                wx.CallAfter(self.frame.standardDetails.Hide)
                hide_names = [self.frame.pageTitlePanel, self.frame.pageTitle,self.frame.pagerPanel,self.frame.BL,self.frame.BR]
            else:
                hide_names = [self.frame.standardOverview,self.frame.standardDetails,self.frame.pageTitlePanel, self.frame.pageTitle,self.frame.pagerPanel,self.frame.BL,self.frame.BR]



            for name in hide_names:
                name.Hide()
            self.frame.videoframe.hide_videoframe()

            if sys.platform != 'win32':
                self.frame.top_bg.createBackgroundImage()

            self.frame.top_bg.Layout()


            # reputation
            self.guiserver.add_task(self.guiservthread_update_reputation, .2)
          
            self.setDBStats()
            
            self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
            

            # Arno, 2007-05-03: wxWidgets 2.8.3.0 and earlier have the MIME-type for .bmp 
            # files set to 'image/x-bmp' whereas 'image/bmp' is the official one.
            try:
                bmphand = None
                hands = wx.Image.GetHandlers()
                for hand in hands:
                    #print "Handler",hand.GetExtension(),hand.GetType(),hand.GetMimeType()
                    if hand.GetMimeType() == 'image/x-bmp':
                        bmphand = hand
                        break
                #wx.Image.AddHandler()
                if bmphand is not None:
                    bmphand.SetMimeType('image/bmp')
            except:
                # wx < 2.7 don't like wx.Image.GetHandlers()
                print_exc()
            
            # Must be after ABCLaunchMany is created
            #self.torrentfeed = TorrentFeedThread.getInstance()
            #self.torrentfeed.register(self.utility)
            #self.torrentfeed.start()
            
            #print "DIM",wx.GetDisplaySize()
            #print "MM",wx.GetDisplaySizeMM()

            #self.frame.Refresh()
            #self.frame.Layout()
            self.frame.Show(True)

            wx.CallAfter(self.startWithRightView)
            # Delay this so GUI has time to paint
            wx.CallAfter(self.loadSessionCheckpoint)
                        

            #self.sr_indicator_left_image = wx.Image(os.path.join(self.utility.getPath(),"Tribler","Main","vwxGUI","images","5.0", "SRindicator_left.png", wx.BITMAP_TYPE_ANY))            
            #self.sr_indicator_left = wx.StaticBitmap(self, -1, wx.BitmapFromImage(self.sr_indicator_left_image))

            #self.sr_indicator_right_image = wx.Image(os.path.join(self.utility.getPath(),"Tribler","Main","vwxGUI","images","5.0", "SRindicator_right.png", wx.BITMAP_TYPE_ANY))            
            #self.sr_indicator_right = wx.StaticBitmap(self, -1, wx.BitmapFromImage(self.sr_indicator_right_image))

            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

        return True



    def OnSearchResultsPressed(self, event):
        self.guiUtility.OnResultsClicked()


    def helpClick(self,event=None):
        title = self.utility.lang.get('sharing_reputation_information_title')
        msg = self.utility.lang.get('sharing_reputation_information_message')
            
        dlg = wx.MessageDialog(None, msg, title, wx.OK|wx.ICON_INFORMATION)
        result = dlg.ShowModal()
        dlg.Destroy()

    def viewSettings(self,event):
        self.guiUtility.settingsOverview()

    def viewLibrary(self,event):
        self.guiUtility.standardLibraryOverview()

    def toggleFamilyFilter(self,event):
        self.guiUtility.toggleFamilyFilter()


    def startAPI(self):
        
        # Start Tribler Session
        state_dir = Session.get_default_state_dir()
        
        cfgfilename = Session.get_default_config_filename(state_dir)
        if DEBUG:
            print >>sys.stderr,"main: Session config",cfgfilename
        try:
            self.sconfig = SessionStartupConfig.load(cfgfilename)
        except:
            print_exc()
            self.sconfig = SessionStartupConfig()
            self.sconfig.set_state_dir(state_dir)
            # Set default Session params here
            destdir = get_default_dest_dir()
            torrcolldir = os.path.join(destdir,STATEDIR_TORRENTCOLL_DIR)
            self.sconfig.set_torrent_collecting_dir(torrcolldir)
            self.sconfig.set_nat_detect(True)
            
            # rename old collected torrent directory
            try:
                if not os.path.exists(destdir):
                    os.makedirs(destdir)
                old_collected_torrent_dir = os.path.join(state_dir, 'torrent2')
                if not os.path.exists(torrcolldir) and os.path.isdir(old_collected_torrent_dir):
                    os.rename(old_collected_torrent_dir, torrcolldir)
                    print >>sys.stderr,"main: Moved dir with old collected torrents to", torrcolldir
                    
                # Arno, 2008-10-23: Also copy torrents the user got himself
                old_own_torrent_dir = os.path.join(state_dir, 'torrent')
                for name in os.listdir(old_own_torrent_dir):
                    oldpath = os.path.join(old_own_torrent_dir,name)
                    newpath = os.path.join(torrcolldir,name)
                    if not os.path.exists(newpath):
                        print >>sys.stderr,"main: Copying own torrent",oldpath,newpath
                        os.rename(oldpath,newpath)
                    
                # Internal tracker
            except:
                print_exc()

        # 22/08/08 boudewijn: convert abc.conf to SessionConfig
        self.utility.convert__presession_4_1__4_2(self.sconfig)
        
        s = Session(self.sconfig)
        self.utility.session = s

        s.add_observer(self.sesscb_ntfy_reachable,NTFY_REACHABLE,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_activities,NTFY_ACTIVITIES,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_TORRENTS,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_PEERS,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_friends,NTFY_PEERS,[NTFY_UPDATE])


        # set port number in GuiUtility
        if DEBUG:
            print >> sys.stderr, 'LISTEN PORT :' , s.get_listen_port()
        port = s.get_listen_port()
        self.guiUtility.set_port_number(port)


        # Load the default DownloadStartupConfig
        dlcfgfilename = get_default_dscfg_filename(s)
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
           #print_exc()
            defaultdestdir = os.path.join(get_default_dest_dir())
            defaultDLConfig.set_dest_dir(defaultdestdir)

        # 29/08/08 boudewijn: convert abc.conf to DefaultDownloadStartupConfig
        self.utility.convert__postsession_4_1__4_2(s, defaultDLConfig)

        s.set_coopdlconfig(defaultDLConfig)

        # Loading of checkpointed Downloads delayed to allow GUI to paint,
        # see loadSessionCheckpoint

        # Create global rate limiter
        self.ratelimiter = UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager()
        self.rateadjustcount = 0 

        maxup = self.utility.config.Read('maxuploadrate', "int")
        if maxup == -1: # no upload
            self.ratelimiter.set_global_max_speed(UPLOAD, 0.00001)
        else:
            self.ratelimiter.set_global_max_speed(UPLOAD, maxup)


        maxdown = self.utility.config.Read('maxdownloadrate', "int")
        self.ratelimiter.set_global_max_speed(DOWNLOAD, maxdown)


        maxupseed = self.utility.config.Read('maxseeduploadrate', "int")
        self.ratelimiter.set_global_max_seedupload_speed(maxupseed)
        self.utility.ratelimiter = self.ratelimiter
 
# SelectiveSeeding _       
        self.seedingmanager = GlobalSeedingManager(self.utility.config.Read)#, self.utility.session)
        self.seedingcount = 0 
# _SelectiveSeeding

        # seeding stats crawling
        self.seeding_snapshot_count = 0
        self.seedingstats_settings = s.open_dbhandler(NTFY_SEEDINGSTATSSETTINGS).loadCrawlingSettings()
        self.seedingstats_enabled = self.seedingstats_settings[0][2]
        self.seedingstats_interval = self.seedingstats_settings[0][1]
        
        # Only allow updates to come in after we defined ratelimiter
        s.set_download_states_callback(self.sesscb_states_callback)
        
        # Load friends from friends.txt
        #friends.init(s)

        # Schedule task for checkpointing Session, to avoid hash checks after
        # crashes.
        #
        self.guiserver.add_task(self.guiservthread_checkpoint_timer,SESSION_CHECKPOINT_INTERVAL)

        
    def sesscb_states_callback(self,dslist):
        """ Called by SessionThread """
        wx.CallAfter(self.gui_states_callback,dslist)
        return(1.0, True)

    def get_reputation(self):
        """ get the current reputation score"""
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        reputation = bc_db.getMyReputation()
        self.utility.session.close_dbhandler(bc_db)
        return reputation

    def get_total_down(self):
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        return bc_db.total_down

    def get_total_up(self):
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        return bc_db.total_up


    def set_reputation(self):
        """ set the reputation in the GUI"""
        reputation = self.get_reputation()
        if reputation < -0.33:
            self.frame.top_bg.sr_msg.SetLabel('Poor')
            self.frame.top_bg.sr_msg.SetForegroundColour((255,51,0))
        elif reputation < 0.33:
            self.frame.top_bg.sr_msg.SetLabel('Average')
            self.frame.top_bg.sr_msg.SetForegroundColour(wx.BLACK)
        else:
            self.frame.top_bg.sr_msg.SetLabel('Good')
            self.frame.top_bg.sr_msg.SetForegroundColour((0,80,120))



 
        if DEBUG:
            print >> sys.stderr , "main: My Reputation",reputation
        
        self.frame.top_bg.help.SetToolTipString(self.utility.lang.get('help') % (reputation))

        d = int(self.get_total_down()) * 1024.0
 
        if d < 10:
            s = '%dB Down   ' % d         
        elif d < 100:
            s = '%dB Down  ' % d         
        elif d < 1000:
            s = '%dB Down ' % d
        elif d < 1024:
            s = '%1.1fKB Down' % (d/1024.0)
        elif d < 10240:
            s = '%dKB Down  ' % (d//1024)
        elif d < 102400:
            s = '%dKB Down ' % (d//1024)
        elif d < 1022796:
            s = '%dKB Down' % (d//1024)
        elif d < 1048576:
            s = '%1.1fMB Down' % (d//1048576.0)
        elif d < 10485760:
            s = '%dMB Down  ' % (d//1048576)
        elif d < 104857600:
            s = '%dMB Down ' % (d//1048576)
        elif d < 1047527425:
            s = '%dMB Down' % (d//1048576)
        elif d < 1073741824:
            s = '%1.1fGB Down' % (d//1073741824.0)
        elif d < 10737418240:
            s = '%dGB Down  ' % (d//1073741824)
        elif d < 107374182400:
            s = '%dGB Down ' % (d//1073741824)
        else: 
            s = '%dGB Down' % (d//1073741824)


        #if d < 10:
        #    s = '%dB Down   ' % d         
        #elif d < 100:
        #    s = '%dB Down  ' % d         
        #elif d < 1000:
        #    s = '%dB Down ' % d
        #elif d < 10000:
        #    s = '%dKB Down  ' % (d//1000L)
        #elif d < 100000:
        #    s = '%dKB Down ' % (d//1000L)
        #elif d < 1000000:
        #    s = '%dKB Down' % (d//1000L)
        #elif d < 10000000:
        #    s = '%dMB Down  ' % (d//1000000L)
        #elif d < 100000000:
        #    s = '%dMB Down ' % (d//1000000L)
        #elif d < 1000000000:
        #    s = '%dMB Down' % (d//1000000L)
        #elif d < 10000000000:
        #    s = '%dGB Down  ' % (d//1000000000L)
        #elif d < 100000000000:
        #    s = '%dGB Down ' % (d//1000000000L)
        #else:
        #    s = '%dGB Down' % (d//1000000000L)
        
        self.frame.top_bg.total_down.SetLabel(s)


        u = self.get_total_up() * 1024.0


        if u < 1000:
            s = '%4dB Up' % u
        elif u < 1024:
            s = '%1.1fKB Up' % (u/1024.0)
        elif u < 1022796:
            s = '%3dKB Up' % (u//1024)
        elif u < 1048576:
            s = '%1.1fMB Up' % (u//1048576.0)
        elif u < 1047527425:
            s = '%3dMB Up' % (u//1048576)
        elif u < 1073741824:
            s = '%1.1fGB Up' % (u//1073741824.0)
        else: 
            s = '%3dGB Up' % (u//1073741824)


        #if u < 1000:
        #    s = '%4dB Up' % u
        #elif u < 1000000:
        #    s = '%3dKB Up' % (u//1000L)
        #elif u < 1000000000:
        #    s = '%3dMB Up' % (u//1000000L)
        #else:
        #    s = '%3dGB Up' % (u//1000000000L)

        self.frame.top_bg.total_up.SetLabel(s)


        self.frame.hsizer = self.frame.top_bg.sr_indicator.GetContainingSizer()
        self.frame.hsizer.Remove(0)
        self.frame.hsizer.Prepend(wx.Size(reputation*40+50,0),0,wx.LEFT,0)
   
        self.frame.hsizer.Layout()
 
        ##self.old_reputation = reputation


    def guiservthread_update_reputation(self):
        """ update the reputation"""
        wx.CallAfter(self.set_reputation)
        self.guiserver.add_task(self.guiservthread_update_reputation,10.0) 



        
    def gui_states_callback(self,dslist):
        """ Called by MainThread  """
        if DEBUG: 
            print >>sys.stderr,"main: Stats:"
            
        torrentdb = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
        if DEBUG:
            print >>sys.stderr,"main: Stats: Total torrents found",torrentdb.size(),"peers",peerdb.size()    
            
        #print >>sys.stderr,"main: Stats: NAT",self.utility.session.get_nat_type()
        try:
            # Print stats on Console
            for ds in dslist:
                # safename = `ds.get_download().get_def().get_name()`
                # print >>sys.stderr,"main: Stats: %s %.1f%% %s dl %.1f ul %.1f n %d\n" % (dlstatus_strings[ds.get_status()],100.0*ds.get_progress(),safename,ds.get_current_speed(DOWNLOAD),ds.get_current_speed(UPLOAD),ds.get_num_peers())
                # print >>sys.stderr,"main: Infohash:",`ds.get_download().get_def().get_infohash()`
                if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                    print >>sys.stderr,"main: Error:",`ds.get_error()`

            # Find State of currently playing video
            playds = None
            d = self.videoplayer.get_vod_download()
            for ds in dslist:
                if ds.get_download() == d:
                    playds = ds
                    break
            
            # Apply status displaying from SwarmPlayer
            if playds:
                videoplayer_mediastate = self.videoplayer.get_state()

                totalhelping = 0
                totalspeed = {UPLOAD:0.0,DOWNLOAD:0.0}
                for ds in dslist:
                    totalspeed[UPLOAD] += ds.get_current_speed(UPLOAD)
                    totalspeed[DOWNLOAD] += ds.get_current_speed(DOWNLOAD)
                    totalhelping += ds.get_num_peers()

                [topmsg,msg,self.said_start_playback,self.decodeprogress] = get_status_msgs(playds,videoplayer_mediastate,"Tribler",self.said_start_playback,self.decodeprogress,totalhelping,totalspeed)
                # Update status msg and progress bar
                if topmsg != '':
                    
                    if videoplayer_mediastate == MEDIASTATE_PLAYING or (videoplayer_mediastate == MEDIASTATE_STOPPED and self.said_start_playback):
                        # In SwarmPlayer we would display "Decoding: N secs" 
                        # when VLC was playing but the video was not yet
                        # being displayed (because VLC was looking for an
                        # I-frame). We would display it in the area where
                        # VLC would paint if it was ready to display.
                        # Hence, our text would be overwritten when the
                        # video was ready. We write the status text to
                        # its own area here, so trick doesn't work.
                        # For now: just hide.
                        text = msg
                    else:
                        text = topmsg
                else:
                    text = msg
                    
                #print >>sys.stderr,"main: Messages",topmsg,msg,`playds.get_download().get_def().get_name()`
                    
                self.videoplayer.set_player_status_and_progress(text,playds.get_pieces_complete())
            
            # Pass DownloadStates to libaryView
            try:
                if self.guiUtility.standardOverview is not None:
                    mode = self.guiUtility.standardOverview.mode 
                    #if mode == 'libraryMode' or mode == 'friendsMode':
                    # Also pass dslist to friendsView, for coopdl boosting info
                    # Arno, 2009-02-11: We also need it in filesMode now.
                    modedata = self.guiUtility.standardOverview.data[mode]
                    grid = modedata.get('grid')
                    if grid is not None:
                        gm = grid.gridManager
                        gm.download_state_gui_callback(dslist)
            except KeyError:
                # Apparently libraryMode only has has a 'grid' key when visible
                print_exc()
                pass
            except AttributeError:
                print_exc()
            except:
                print_exc()
            
            # Restart other torrents when the single torrent that was
            # running in VOD mode is done
            currdlist = []
            for ds in dslist:
                currdlist.append(ds.get_download())
            vodd = self.videoplayer.get_vod_download()
            for ds in dslist:
                d = ds.get_download()
                if d == vodd and ds.get_status() == DLSTATUS_SEEDING:
                    self.restart_other_downloads(currdlist)
                    break
                            
            # Adjust speeds once every 4 seconds
            adjustspeeds = False
            if self.rateadjustcount % 4 == 0:
                adjustspeeds = True
            self.rateadjustcount += 1
    
            if adjustspeeds:
                self.ratelimiter.add_downloadstatelist(dslist)
                self.ratelimiter.adjust_speeds()
                
            # Update stats in lower right overview box
            self.guiUtility.refreshTorrentStats(dslist)
            
            # Upload overall upload states
            self.guiUtility.refreshUploadStats(dslist)
            
# SelectiveSeeding_
            # Apply seeding policy every 60 seconds, for performance
            applyseedingpolicy = False
            if self.seedingcount % 60 == 0:
                applyseedingpolicy = True
            self.seedingcount += 1
    
            if applyseedingpolicy:
                self.seedingmanager.apply_seeding_policy(dslist)
# _SelectiveSeeding
            
# Crawling Seeding Stats_
            if self.seedingstats_enabled == 1:
                snapshot_seeding_stats = False
                if self.seeding_snapshot_count % self.seedingstats_interval == 0:
                    snapshot_seeding_stats = True
                self.seeding_snapshot_count += 1
                
                if snapshot_seeding_stats:
                    bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
                    reputation = bc_db.getMyReputation()
                    self.utility.session.close_dbhandler(bc_db)
                    
                    seedingstats_db = self.utility.session.open_dbhandler(NTFY_SEEDINGSTATS)
                    seedingstats_db.updateSeedingStats(self.utility.session.get_permid(), reputation, dslist, self.seedingstats_interval) 
                    self.utility.session.close_dbhandler(seedingstats_db)
# _Crawling Seeding Stats

        except:
            print_exc()

    def restart_other_downloads(self,currdlist):
        restartdlist = self.videoplayer.get_vod_postponed_downloads()
        self.videoplayer.set_vod_postponed_downloads([]) # restart only once
        for d in restartdlist:
            if d in currdlist:
                d.set_mode(DLMODE_NORMAL)
                d.restart()


    def OnClosingVideoFrameOrExtPlayer(self):
        vodd = self.videoplayer.get_vod_download()
        if vodd is not None:
            if vodd.get_def().get_live():
                # Arno, 2009-03-27: Works poorly with VLC 0.9 without MPEGTS 
                # patch. There VLC may close the HTTP connection and we interpret
                # it as a window close (no window in 5.0) and stop live, thereby
                # killing any future attempts. Should see how this works with
                # MPEGTS patch put in.
                #
                print >>sys.stderr,"main: OnClosingVideoFrameOrExtPlayer: vodd is live, stopping",vodd.get_def().get_name_as_unicode()
                vodd.stop()
            self.restart_other_downloads(self.utility.session.get_downloads())
        #else: playing Web2 video

    def loadSessionCheckpoint(self):
        # Load all other downloads
        # TODO: reset all saved DownloadConfig to new default?
        if self.params[0] != "":
            # There is something on the cmdline, start all stopped
            self.utility.session.load_checkpoint(initialdlstatus=DLSTATUS_STOPPED)
        else:
            self.utility.session.load_checkpoint()

    def guiservthread_checkpoint_timer(self):
        """ Periodically checkpoint Session """
        try:
            print >>sys.stderr,"main: Checkpointing Session"
            self.utility.session.checkpoint()
            self.guiserver.add_task(self.guiservthread_checkpoint_timer,SESSION_CHECKPOINT_INTERVAL)
        except:
            print_exc()


    def sesscb_ntfy_dbstats(self,subject,changeType,objectID,*args):
        """ Called by SessionCallback thread """
        wx.CallAfter(self.setDBStats)
        # Test
        #if subject == NTFY_PEERS:
        #    self.frame.friendsmgr.sesscb_friendship_callback(objectID,{})
        
    def setDBStats(self):
        """ Set total # peers and torrents discovered """
        
        # Arno: GUI thread accessing database
        now = time.time()
        if now - self.last_update < self.update_freq:
            return  
        self.last_update = now
        peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
        npeers = peer_db.getNumberPeers()
        torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        nfiles = torrent_db.getNumberTorrents()
        if nfiles > 30 and npeers > 30:
            self.update_freq = 2
        # Arno: not closing db connections, assuming main thread's will be 
        # closed at end.
                
        #self.frame.numberPersons.SetLabel('%d' % npeers)
        #self.frame.numberFiles.SetLabel('%d' % nfiles)
        #print >> sys.stderr, "************>>>>>>>> setDBStats", npeers, nfiles
        
    def sesscb_ntfy_activities(self,subject,changeType,objectID,*args):
        # Called by SessionCallback thread
        #print >>sys.stderr,"main: sesscb_ntfy_activities called:",subject,"ct",changeType,"oid",objectID,"a",args
        wx.CallAfter(self.frame.setActivity,objectID,*args)
    
    def sesscb_ntfy_reachable(self,subject,changeType,objectID,msg):
        wx.CallAfter(self.frame.standardOverview.onReachable)


    def sesscb_ntfy_friends(self,subject,changeType,objectID,*args):
        """ Called by SessionCallback thread """
        if subject == NTFY_PEERS:
            peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
            peer = peerdb.getPeer(objectID)
            #self.utility.session.close_dbhandler(peerdb)
        else:
            peer = None
        wx.CallAfter(self.gui_ntfy_friends,subject,changeType,objectID,args,peer)

    def gui_ntfy_friends(self,subject,changeType,objectID,args,peer):
        """ A change in friendship status, report via message window """
        if len(args) == 2:
            if args[0] == 'friend':
                fs = args[1]
                if fs != FS_I_INVITED and fs != FS_I_DENIED and fs != FS_NOFRIEND:
                    fstext = fs2text(fs)
                    if peer['name'] is None or peer['name'] == '':
                        name = show_permid_short(objectID)
                    else:
                        name = peer['name']
                    msg = name + u" " + fstext
                    wx.CallAfter(self.frame.setActivity,NTFY_ACT_NONE,msg)

    def onError(self,source=None):
        # Don't use language independence stuff, self.utility may not be
        # valid.
        msg = "Unfortunately, Tribler ran into an internal error:\n\n"
        if source is not None:
            msg += source
        msg += str(self.error.__class__)+':'+str(self.error)
        msg += '\n'
        msg += 'Please see the FAQ on www.tribler.org on how to act.'
        dlg = wx.MessageDialog(None, msg, "Tribler Fatal Error", wx.OK|wx.ICON_ERROR)
        result = dlg.ShowModal()
        print_exc()
        dlg.Destroy()


    def OnExit(self):
        print >>sys.stderr,"main: ONEXIT"
        
        #friends.done(self.utility.session)
        
        #self.torrentfeed.shutdown()

        # Don't checkpoint, interferes with current way of saving Preferences,
        # see Tribler/Main/Dialogs/abcoption.py
        self.utility.session.shutdown(hacksessconfcheckpoint=False) 

        while not self.utility.session.has_shutdown():
            print >>sys.stderr,"main ONEXIT: Waiting for Session to shutdown"
            sleep(1)
            
        
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        return 0
    
    def db_exception_handler(self,e):
        if DEBUG:
            print >> sys.stderr,"main: Database Exception handler called",e,"value",e.args,"#"
        try:
            if e.args[1] == "DB object has been closed":
                return # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return # don't repeat same error
        except:
            print >> sys.stderr, "main: db_exception_handler error", e, type(e)
            print_exc()
            #print_stack()
        self.error = e
        onerror_lambda = lambda:self.onError(source="The database layer reported:  ") 
        wx.CallAfter(onerror_lambda)
    
    def getConfigPath(self):
        return self.utility.getConfigPath()

    def startWithRightView(self):
        if self.params[0] != "":
            self.guiUtility.standardLibraryOverview()
 
 
    def i2ithread_readlinecallback(self,ic,cmd):
        """ Called by Instance2Instance thread """
        
        print >>sys.stderr,"main: Another instance called us with cmd",cmd
        ic.close()
        
        if cmd.startswith('START '):
            param = cmd[len('START '):]
            torrentfilename = None
            if param.startswith('http:'):
                # Retrieve from web 
                f = tempfile.NamedTemporaryFile()
                n = urllib2.urlopen(param)
                data = n.read()
                f.write(data)
                f.close()
                n.close()
                torrentfilename = f.name
            else:
                torrentfilename = param
                
            # Switch to GUI thread
            # New for 5.0: Start in VOD mode
            def start_asked_download():
                self.frame.startDownload(torrentfilename,vodmode=True)
                self.guiUtility.standardLibraryOverview(refresh=True)
            
            wx.CallAfter(start_asked_download)
    
        

def get_status_msgs(ds,videoplayer_mediastate,appname,said_start_playback,decodeprogress,totalhelping,totalspeed):

    intime = "Not playing for quite some time."
    ETA = ((60 * 15, "Playing in less than 15 minutes."),
           (60 * 10, "Playing in less than 10 minutes."),
           (60 * 5, "Playing in less than 5 minutes."),
           (60, "Playing in less than a minute."))

    topmsg = ''
    msg = ''
    
    logmsgs = ds.get_log_messages()
    logmsg = None
    if len(logmsgs) > 0:
        print >>sys.stderr,"main: Log",logmsgs[0]
        logmsg = logmsgs[-1][1]
        
    preprogress = ds.get_vod_prebuffering_progress()
    playable = ds.get_vod_playable()
    t = ds.get_vod_playable_after()

    intime = ETA[0][1]
    for eta_time, eta_msg in ETA:
        if t > eta_time:
            break
        intime = eta_msg
    
    #print >>sys.stderr,"main: playble",playable,"preprog",preprogress
    #print >>sys.stderr,"main: ETA is",t,"secs"
    # if t > float(2 ** 30):
    #     intime = "inf"
    # elif t == 0.0:
    #     intime = "now"
    # else:
    #     h, t = divmod(t, 60.0*60.0)
    #     m, s = divmod(t, 60.0)
    #     if h == 0.0:
    #         if m == 0.0:
    #             intime = "%ds" % (s)
    #         else:
    #             intime = "%dm:%02ds" % (m,s)
    #     else:
    #         intime = "%dh:%02dm:%02ds" % (h,m,s)
            
    #print >>sys.stderr,"main: VODStats",preprogress,playable,"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"

    if ds.get_status() == DLSTATUS_HASHCHECKING:
        genprogress = ds.get_progress()
        pstr = str(int(genprogress*100))
        msg = "Checking already downloaded parts "+pstr+"% done"
    elif ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
        msg = 'Error playing: '+str(ds.get_error())
    elif ds.get_progress() == 1.0:
        msg = ''
    elif playable:
        if not said_start_playback:
            msg = "Starting playback..."
            
        if videoplayer_mediastate == MEDIASTATE_STOPPED and said_start_playback:
            if totalhelping == 0:
                topmsg = u"Please leave the "+appname+" running, this will help other "+appname+" users to download faster."
            else:
                topmsg = u"Helping "+str(totalhelping)+" "+appname+" users to download. Please leave it running in the background."
                
            # Display this on status line
            # TODO: Show balloon in systray when closing window to indicate things continue there
            msg = ''
            
        elif videoplayer_mediastate == MEDIASTATE_PLAYING:
            said_start_playback = True
            # It may take a while for VLC to actually start displaying
            # video, as it is trying to tune in to the stream (finding
            # I-Frame). Display some info to show that:
            #
            cname = ds.get_download().get_def().get_name_as_unicode()
            topmsg = u'Decoding: '+cname+' '+str(decodeprogress)+' s'
            decodeprogress += 1
            msg = ''
        elif videoplayer_mediastate == MEDIASTATE_PAUSED:
            # msg = "Buffering... " + str(int(100.0*preprogress))+"%" 
            msg = "Buffering... " + str(int(100.0*preprogress))+"%. " + intime
        else:
            msg = ''
            
    elif preprogress != 1.0:
        pstr = str(int(preprogress*100))
        npeers = ds.get_num_peers()
        npeerstr = str(npeers)
        if npeers == 0 and logmsg is not None:
            msg = logmsg
        elif npeers == 1:
            msg = "Prebuffering "+pstr+"% done (connected to 1 person). " + intime
        else:
            msg = "Prebuffering "+pstr+"% done (connected to "+npeerstr+" people). " + intime
            
        try:
            d = ds.get_download()
            tdef = d.get_def()
            videofiles = d.get_selected_files()
            if len(videofiles) >= 1:
                videofile = videofiles[0]
            else:
                videofile = None
            if tdef.get_bitrate(videofile) is None:
                msg += ' This video may not play properly because its bitrate is unknown'
        except:
            print_exc()
    else:
        # msg = "Waiting for sufficient download speed... "+intime
        msg = 'Waiting for sufficient download speed... ' + intime
        
    npeers = ds.get_num_peers()
    if npeers == 1:
        msg = "One person found, receiving %.1f KB/s" % totalspeed[DOWNLOAD]
    else:
        msg = "%d people found, receiving %.1f KB/s" % (npeers, totalspeed[DOWNLOAD])

    if playable:
        if videoplayer_mediastate == MEDIASTATE_PAUSED and not ds.get_status() == DLSTATUS_SEEDING:
            msg = "Buffering... " + msg
        else:
            msg = ""

    return [topmsg,msg,said_start_playback,decodeprogress]
        
        
##############################################################
#
# Main Program Start Here
#
##############################################################
def run(params = None):
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    try:
        # Create single instance semaphore
        # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
        # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
        #
        if sys.platform != 'linux2':
            single_instance_checker = wx.SingleInstanceChecker("tribler-" + wx.GetUserId())
        else:
            single_instance_checker = LinuxSingleInstanceChecker("tribler")
    
        if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
            #Send  torrent info to abc single instance
            if params[0] != "":
                torrentfilename = params[0]
                i2ic = Instance2InstanceClient(I2I_LISTENPORT,'START',torrentfilename)
        else:
            arg0 = sys.argv[0].lower()
            if arg0.endswith('.exe'):
                # supply a unicode string to ensure that the unicode filesystem API is used (applies to windows)
                installdir = os.path.abspath(os.path.dirname(unicode(sys.argv[0])))
            else:
                # call the unicode specific getcwdu() otherwise homedirectories may crash
                installdir = os.getcwdu()  
            # Arno: don't chdir to allow testing as other user from other dir.
            #os.chdir(installdir)
    
            # Launch first abc single instance
            app = ABCApp(0, params, single_instance_checker, installdir)
            configpath = app.getConfigPath()
            app.MainLoop()
    
        print "Client shutting down. Sleeping for a few seconds to allow other threads to finish"
        sleep(1)
    except:
        print_exc()

    # This is the right place to close the database, unfortunately Linux has
    # a problem, see ABCFrame.OnCloseWindow
    #
    #if sys.platform != 'linux2':
    #    tribler_done(configpath)
    #os._exit(0)

if __name__ == '__main__':
    run()

