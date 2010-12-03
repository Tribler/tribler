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
import M2Crypto # Not a useless import! See above.
urllib.URLopener.open_https = original_open_https

# Arno, 2008-03-21: see what happens when we disable this locale thing. Gives
# errors on Vista in "Regional and Language Settings Options" different from 
# "English[United Kingdom]" 
#import locale

# 20/10/09 Boudewijn: on systems that install multiple wx versions we
# would prefer 2.8.
try:
    import wxversion
    wxversion.select('2.8')
except:
    pass

import wx
import wx.animate
from wx import xrc
#import hotshot

from traceback import print_exc
import urllib2
import tempfile

from Tribler.Main.vwxGUI.MainFrame import MainFrame # py2exe needs this import
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.MainVideoFrame import VideoDummyFrame,VideoMacFrame
## from Tribler.Main.vwxGUI.FriendsItemPanel import fs2text 
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.notification import init as notification_init
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import *

from Tribler.Category.Category import Category
from Tribler.Policies.RateManager import UserDefinedMaxAlwaysOtherwiseDividedOverActiveSwarmsRateManager
from Tribler.Policies.SeedingManager import GlobalSeedingManager
from Tribler.Utilities.Instance2Instance import *
from Tribler.Utilities.LinuxSingleInstanceChecker import *

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.Statistics.Status.Status import get_status_holder
from Tribler.Core.Statistics.Status.NullReporter import NullReporter

from Tribler.Video.defs import *
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoServer import SimpleServer

from Tribler.Subscriptions.rss_client import TorrentFeedThread


# Boudewijn: keep this import BELOW the imports from Tribler.xxx.* as
# one of those modules imports time as a module.
from time import time, sleep

I2I_LISTENPORT = 57891
VIDEOHTTP_LISTENPORT = 6875
SESSION_CHECKPOINT_INTERVAL = 1800.0 # seconds
CHANNELMODE_REFRESH_INTERVAL = 5.0

DEBUG = False
ALLOW_MULTIPLE = False

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
        self.state_dir = None
        self.error = None
        self.last_update = 0
        self.update_freq = 0    # how often to update #peers/#torrents
        self.ready = False

        self.guiserver = GUITaskQueue.getInstance()
        self.said_start_playback = False
        self.decodeprogress = 0

        self.old_reputation = 0
        self.lastchannelrefresh = -1.0

        try:
            import sys
            self.pre_stdout, self.pre_stderr = sys.stdout, sys.stderr

            ubuntu = False
            if sys.platform == "linux2":
                f = open("/etc/issue","rb")
                data = f.read(100)
                f.close()
                if data.find("Ubuntu 8.10") != -1:
                    ubuntu = True
                if data.find("Ubuntu 9.04") != -1:
                    ubuntu = True
                    
            print >>sys.stderr,"tribler: Activating workaround for Ubuntu?",ubuntu
                    
            if not redirectstderrout and ubuntu:
                # On Ubuntu 8.10 not redirecting output causes the program to quit
                wx.App.__init__(self, redirect=True)
            else:
                wx.App.__init__(self, redirectstderrout)
        except:
            # boudewijn: wx messes around with streams
            import sys
            sys.stdout, sys.stderr = self.pre_stdout, self.pre_stderr
            print_exc()
            # boudewijn: we need to flush, otherwise exception is not
            # always shown
            sys.stderr.flush()
        
    def OnInit(self):
        try:
            import sys
            sys.stdout, sys.stderr = self.pre_stdout, self.pre_stderr

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
            self.splash.Show()

            # Arno, 2009-08-18: Don't delay postinit anymore, gives problems on Ubuntu 9.04
            self.PostInit()    
            return True
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

    def PostInit(self):
        try:
            # On Linux: allow painting of splash screen first.
            wx.Yield()
            
            self.utility.postAppInit(os.path.join(self.installdir,'Tribler','Images','tribler.ico'))
            
            cat = Category.getInstance(self.utility.getPath())
            cat.init_from_main(self.utility)

            # Put it here so an error is shown in the startup-error popup
            # Start server for instance2instance communication
            self.i2iconnhandler = InstanceConnectionHandler(self.i2ithread_readlinecallback)
            self.i2is = Instance2InstanceServer(I2I_LISTENPORT,self.i2iconnhandler) 
            self.i2is.start()

            # Arno, 2010-01-15: VLC's reading behaviour of doing open-ended
            # Range: GETs causes performance problems in our code. Disable for now.
            # Arno, 2010-01-22: With the addition of a CachingStream the problem
            # is less severe (see VideoPlayer), so keep GET Range enabled.
            #
            #SimpleServer.RANGE_REQUESTS_ENABLED = False
            
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
            self.startAPI()
            self.guiUtility.register()
           
            self.res = xrc.XmlResource(os.path.join(self.utility.getPath(),'Tribler', 'Main','vwxGUI','MyFrame.xrc'))
            self.frame = self.res.LoadFrame(None, "MyFrame")
            self.guiUtility.frame = self.frame

            self.frame.set_wxapp(self)
            self.frame.top_bg = xrc.XRCCTRL(self.frame,"top_search")
            self.frame.home = xrc.XRCCTRL(self.frame,"home")
            self.frame.stats = xrc.XRCCTRL(self.frame,"stats")
            self.frame.searchlist = xrc.XRCCTRL(self.frame, "searchlist")
            self.frame.channellist = xrc.XRCCTRL(self.frame, "channellist")
            self.frame.selectedchannellist = xrc.XRCCTRL(self.frame, "selchannellist")
            self.frame.mychannel = xrc.XRCCTRL(self.frame, "mychannel")
            self.frame.channelselector = xrc.XRCCTRL(self.frame, "channelSelector")
            self.frame.channelcategories = xrc.XRCCTRL(self.frame, "channelcategories")
            self.frame.channelcategories.SetQuicktip(xrc.XRCCTRL(self.frame, "quicktip"))
            self.frame.librarylist = xrc.XRCCTRL(self.frame, "librarylist")

            # videopanel
            self.guiUtility.useExternalVideo = self.guiUtility.utility.config.Read('popup_player', "boolean") or sys.platform == 'darwin'
            vlcwrap = self.videoplayer.get_vlcwrap()
            if self.guiUtility.useExternalVideo:
                self.frame.videoparentpanel = None
                
                self.frame.videoframe = VideoMacFrame(self.frame,self.utility,"Videoplayer",os.path.join(self.installdir,'Tribler','Images','tribler.ico'), vlcwrap)
                self.videoplayer.set_videoframe(self.frame.videoframe)
            else:
                self.frame.videoparentpanel = xrc.XRCCTRL(self.frame,"videopanel")
                
                self.frame.videoframe = VideoDummyFrame(self.frame.videoparentpanel,self.utility,vlcwrap)
                self.videoplayer.set_videoframe(self.frame.videoframe)
        
            if sys.platform == 'win32':
                wx.CallAfter(self.frame.top_bg.Refresh)
                wx.CallAfter(self.frame.top_bg.Layout)
            else:
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
        
            self.frame.Show(True)

            wx.CallAfter(self.startWithRightView)
            
            # Delay this so GUI has time to paint
            wx.CallAfter(self.loadSessionCheckpoint)
            
            # start the torrent feed thread
            self.torrentfeed = TorrentFeedThread.getInstance()
            self.torrentfeed.register(self.utility.session)
            self.torrentfeed.start()             

            # 08/02/10 Boudewijn: Working from home though console
            # doesn't allow me to press close.  The statement below
            # gracefully closes Tribler after 120 seconds.
            # wx.CallLater(120*1000, wx.GetApp().Exit)

            # report client version
            # from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
            reporter = get_status_holder("LivingLab")
            reporter.create_and_add_event("client-startup-version", [self.utility.lang.get("version")])
            reporter.create_and_add_event("client-startup-build", [self.utility.lang.get("build")])
            reporter.create_and_add_event("client-startup-build-date", [self.utility.lang.get("build_date")])
            
            
            self.ready = True
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

        return True

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
            
            # 13-04-2010, Andrea: subtitles collecting dir definition
            subscolldir = os.path.join(destdir, STATEDIR_SUBSCOLL_DIR)
            self.sconfig.set_subtitles_collecting(True)
            self.sconfig.set_subtitles_collecting_dir(subscolldir)
            
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
        
        # Arno, 2010-03-31: Hard upgrade to 50000 torrents collected
        self.sconfig.set_torrent_collecting_max_torrents(50000)
        
        s = Session(self.sconfig)
        self.utility.session = s

        from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
        UserDownloadChoice.get_singleton().set_session_dir(self.utility.session.get_state_dir())

        s.add_observer(self.sesscb_ntfy_reachable,NTFY_REACHABLE,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_activities,NTFY_ACTIVITIES,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_TORRENTS,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_dbstats,NTFY_PEERS,[NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_channelupdates,NTFY_CHANNELCAST,[NTFY_INSERT,NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_channelupdates,NTFY_VOTECAST,[NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_myprefupdates,NTFY_MYPREFERENCES,[NTFY_INSERT,NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_torrentupdates,NTFY_TORRENTS,[NTFY_UPDATE])

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
        self.ratelimiter = UserDefinedMaxAlwaysOtherwiseDividedOverActiveSwarmsRateManager()
        self.rateadjustcount = 0

        # Counter to suppress console output containing download
        # current statistics
        self.rateprintcount = 0

        # boudewijn 01/04/2010: hack to fix the seedupload speed that
        # was never used and defaulted to 0 (unlimited upload)
        maxup = self.utility.config.Read('maxuploadrate', "int")
        if maxup == -1: # no upload
            self.ratelimiter.set_global_max_speed(UPLOAD, 0.00001)
            self.ratelimiter.set_global_max_seedupload_speed(0.00001)
        else:
            self.ratelimiter.set_global_max_speed(UPLOAD, maxup)
            self.ratelimiter.set_global_max_seedupload_speed(maxup)


        maxdown = self.utility.config.Read('maxdownloadrate', "int")
        self.ratelimiter.set_global_max_speed(DOWNLOAD, maxdown)


#        maxupseed = self.utility.config.Read('maxseeduploadrate', "int")
#        self.ratelimiter.set_global_max_seedupload_speed(maxupseed)
        self.utility.ratelimiter = self.ratelimiter
 
# SelectiveSeeding _       
        self.seedingmanager = GlobalSeedingManager(self.utility.config.Read, os.path.join(state_dir, STATEDIR_SEEDINGMANAGER_DIR))
        # self.seedingcount = 0 
# _SelectiveSeeding

        # seeding stats crawling
        self.seeding_snapshot_count = 0
        seedstatsdb = s.open_dbhandler(NTFY_SEEDINGSTATSSETTINGS)
        if seedstatsdb is None:
            raise ValueError("Seeding stats DB not created?!")
        self.seedingstats_settings = seedstatsdb.loadCrawlingSettings()
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
        
        # RePEX: Start scheduler and logger
        from Tribler.Core.DecentralizedTracking.repex import RePEXScheduler, RePEXLogger
        #RePEXLogger.getInstance().start() #no more need for logging
        RePEXScheduler.getInstance().start()


    def sesscb_states_callback(self,dslist):
        """ Called by SessionThread """
        wx.CallAfter(self.gui_states_callback,dslist)
        return(1.0, True)
    
    def sesscb_ntfy_myprefupdates(self, subject,changeType,objectID,*args):
        wx.CallAfter(self.gui_ntfy_myprefupdates, objectID)
    
    def gui_ntfy_myprefupdates(self, infohash):
        manager = self.frame.searchlist.GetManager()
        manager.downloadStarted(infohash)
        manager = self.frame.selectedchannellist.GetManager()
        manager.downloadStarted(infohash)

    def get_reputation(self):
        """ get the current reputation score"""
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        reputation = bc_db.getMyReputation()
        #self.utility.session.close_dbhandler(bc_db)
        return reputation

    def get_total_down(self):
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        return bc_db.total_down

    def get_total_up(self):
        bc_db = self.utility.session.open_dbhandler(NTFY_BARTERCAST)
        return bc_db.total_up


    def set_reputation(self):
        """ set the reputation in the GUI"""
        self.frame.SRstatusbar.set_reputation(self.get_reputation(), self.get_total_down(), self.get_total_up())

    def guiservthread_update_reputation(self):
        """ update the reputation"""
        # 26/10/09 boudewijn: the guiservthread_update_reputation will
        # use parameters from self.frame.top_bg that have not yet been
        # created. They are eventually created when the UI thread is
        # ready for it. Therefore, we will set an 'init_ready'
        # parameter when it is ready.
        if self.frame.top_bg.init_ready:
            wx.CallAfter(self.set_reputation)
            self.guiserver.add_task(self.guiservthread_update_reputation,10.0)
        else:
            self.guiserver.add_task(self.guiservthread_update_reputation,.2)
        
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
            if True:
                if self.rateprintcount % 5 == 0:
                    for ds in dslist:
                        safename = `ds.get_download().get_def().get_name()`
                        if DEBUG:
                            print >>sys.stderr,"%s %s %.1f%% dl %.1f ul %.1f n %d" % (safename, dlstatus_strings[ds.get_status()],100.0*ds.get_progress(),ds.get_current_speed(DOWNLOAD),ds.get_current_speed(UPLOAD),ds.get_num_peers())
                        # print >>sys.stderr,"main: Infohash:",`ds.get_download().get_def().get_infohash()`
                        if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                            print >>sys.stderr,"main: Error:",`ds.get_error()`
                self.rateprintcount += 1

            # Find State of currently playing video
            playds = None
            d = self.videoplayer.get_vod_download()
            for ds in dslist:
                # ProxyService 90s Test_
                from Tribler.Core.Statistics.Status.Status import get_status_holder
                #from Tribler.Core.Statistics.Status.ProxyTestReporter import *
                #from Tribler.Core.Statistics.Status import *
                
                safename = `ds.get_download().get_def().get_name()`
                if safename == "'Data.90s-test.8M.bin'":
                    status = get_status_holder("Proxy90secondsTest")
                    status.create_and_add_event("transfer-rate", [safename, dlstatus_strings[ds.get_status()], 100.0*ds.get_progress(), ds.get_current_speed(DOWNLOAD), ds.get_current_speed(UPLOAD), ds.get_num_peers()])
                # _ProxyService 90s Test

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
                self.guiUtility.torrentsearch_manager.download_state_gui_callback(dslist)
            except KeyError:
                # Apparently libraryMode only has has a 'grid' key when visible
                print_exc()
            except AttributeError:
                print_exc()
            except:
                print_exc()
            
            # The VideoPlayer instance manages both pausing and
            # restarting of torrents before and after VOD playback
            # occurs.
            self.videoplayer.restart_other_downloads(dslist)
                     
            # Adjust speeds once every 4 seconds
            adjustspeeds = False
            if self.rateadjustcount % 4 == 0:
                adjustspeeds = True
            self.rateadjustcount += 1
    
            if adjustspeeds:
                self.ratelimiter.add_downloadstatelist(dslist)
                self.ratelimiter.adjust_speeds()
                
            # Update stats in lower right overview box
            # self.guiUtility.refreshTorrentStats(dslist)
            
            # Upload overall upload states
            # self.guiUtility.refreshUploadStats(dslist)
            
# SelectiveSeeding_
            # Apply seeding policy every 60 seconds, for performance
            # Boudewijn 12/01/10: apply seeding policies immediately
            # applyseedingpolicy = False
            # if self.seedingcount % 60 == 0:
            #     applyseedingpolicy = True
            # self.seedingcount += 1
            # if applyseedingpolicy:
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
                    #self.utility.session.close_dbhandler(bc_db)
                    
                    seedingstats_db = self.utility.session.open_dbhandler(NTFY_SEEDINGSTATS)
                    seedingstats_db.updateSeedingStats(self.utility.session.get_permid(), reputation, dslist, self.seedingstats_interval) 
                    #self.utility.session.close_dbhandler(seedingstats_db)
# _Crawling Seeding Stats

        except:
            print_exc()

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
        now = time()
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
        # print >> sys.stderr, "************>>>>>>>> setDBStats", npeers, nfiles
        
    def sesscb_ntfy_activities(self,subject,changeType,objectID,*args):
        # Called by SessionCallback thread
        #print >>sys.stderr,"main: sesscb_ntfy_activities called:",subject,"ct",changeType,"oid",objectID,"a",args
        if self.ready and self.frame.ready:
            wx.CallAfter(self.frame.setActivity,objectID,*args)
    
    def sesscb_ntfy_reachable(self,subject,changeType,objectID,msg):
        if self.ready and self.frame.ready:
            wx.CallAfter(self.frame.SRstatusbar.onReachable)

    def sesscb_ntfy_channelupdates(self,subject,changeType,objectID,*args):
        if self.ready and self.frame.ready:
            wx.CallAfter(self.gui_ntfy_channelupdates,subject,changeType,objectID)
    
    def gui_ntfy_channelupdates(self,subject,changeType,objectID,*args):
        manager = self.frame.channellist.GetManager()
        manager.channelUpdated(objectID)
        
        manager = self.frame.selectedchannellist.GetManager()
        manager.channelUpdated(objectID)
        
    def sesscb_ntfy_torrentupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            wx.CallAfter(self.gui_ntfy_torrentupdates,subject,changeType,objectID)
    
    def gui_ntfy_torrentupdates(self, subject, changeType, objectID, *args):
        manager = self.frame.searchlist.GetManager()
        manager.torrentUpdated(objectID)
        
        manager = self.frame.selectedchannellist.GetManager()
        manager.torrentUpdated(objectID)

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
        self.ready = False

        # write all persistent data to disk
        self.seedingmanager.write_all_storage()
        
        #friends.done(self.utility.session)
        
        self.torrentfeed.shutdown()

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
            self.guiUtility.ShowPage('my_files')
 
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
                if torrentfilename.startswith("magnet:"):
                    self.frame.startDownloadFromMagnet(torrentfilename)
                else:
                    self.frame.startDownload(torrentfilename,vodmode=True)
                self.guiUtility.ShowPage('my_files')

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
            app = ABCApp(False, params, single_instance_checker, installdir)
            configpath = app.getConfigPath()

            # Arno, 2010-06-18: Logging to ULANC disabled for Tribler Main
            
            # Setup the statistic reporter while waiting for proper integration
            status = get_status_holder("LivingLab")
            status.add_reporter(NullReporter("Periodically remove all events", 60))
            #id = "Tribler client"
            #reporter = LivingLabPeriodicReporter("Living lab CS reporter", 300, id) # Report every 5 minutes
            # reporter = LivingLabPeriodicReporter("Living lab CS reporter", 30, id) # Report every 30 seconds - ONLY FOR TESTING
            #status.add_reporter(reporter)

            # ProxyService 90s Test_
            from Tribler.Core.Statistics.Status.ProxyTestReporter import *
    
            status = get_status_holder("Proxy90secondsTest")
            status.add_reporter(ProxyTestPeriodicReporter("DataTransferAndBuddyCast", 60, "id01"))
            # _ProxyService 90s Test


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