#!/usr/bin/python

#
#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#
# see LICENSE.txt for license information
#

import logging.config
logging.config.fileConfig("logger.conf")  # , disable_existing_loggers = False)
logger = logging.getLogger(__name__)

# Arno: M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#
import urllib
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
import shutil
original_open_https = urllib.URLopener.open_https
import M2Crypto  # Not a useless import! See above.
urllib.URLopener.open_https = original_open_https

# modify the sys.stderr and sys.stdout for safe output
import Tribler.Debug.console

import os
import sys
from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUIDBProducer
from Tribler.dispersy.decorator import attach_profiler
from Tribler.dispersy.community import HardKilledCommunity
from Tribler.community.bartercast3.community import MASTER_MEMBER_PUBLIC_KEY_DIGEST as BARTER_MASTER_MEMBER_PUBLIC_KEY_DIGEST
from Tribler.Core.CacheDB.Notifier import Notifier
import traceback
from random import randint
from threading import current_thread, currentThread
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

# Arno, 2008-03-21: see what happens when we disable this locale thing. Gives
# errors on Vista in "Regional and Language Settings Options" different from
# "English[United Kingdom]"
# import locale

# 20/10/09 Boudewijn: on systems that install multiple wx versions we
# would prefer 2.8.
try:
    import wxversion
    wxversion.select('2.8')
except:
    pass

import wx
from wx import xrc
from Tribler.Main.vwxGUI.gaugesplash import GaugeSplash
from Tribler.Main.vwxGUI.MainFrame import FileDropTarget
from Tribler.Main.Dialogs.FeedbackWindow import FeedbackWindow
# import hotshot

from traceback import print_exc
import urllib2
import tempfile
import thread

from Tribler.Main.vwxGUI.MainFrame import MainFrame  # py2exe needs this import
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.MainVideoFrame import VideoDummyFrame, VideoMacFrame
# from Tribler.Main.vwxGUI.FriendsItemPanel import fs2text
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.notification import init as notification_init
from Tribler.Main.globals import DefaultDownloadStartupConfig, get_default_dscfg_filename

from Tribler.Main.Utility.utility import Utility
from Tribler.Main.Utility.constants import *
from Tribler.Main.Utility.Feeds.rssparser import RssParser

from Tribler.Category.Category import Category
from Tribler.Policies.RateManager import UserDefinedMaxAlwaysOtherwiseDividedOverActiveSwarmsRateManager
from Tribler.Policies.SeedingManager import GlobalSeedingManager
from Tribler.Utilities.Instance2Instance import *
from Tribler.Utilities.LinuxSingleInstanceChecker import *

from Tribler.Core.API import *
from Tribler.Core.simpledefs import NTFY_MODIFIED
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.Statistics.Status.Status import get_status_holder, \
    delete_status_holders
from Tribler.Core.Statistics.Status.NullReporter import NullReporter

from Tribler.Video.defs import *
from Tribler.Video.VideoPlayer import VideoPlayer, return_feasible_playback_modes, PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoServer import SimpleServer

# Arno, 2012-06-20: h4x0t DHT import for py2...
import Tribler.Core.DecentralizedTracking.pymdht.core
import Tribler.Core.DecentralizedTracking.pymdht.core.identifier
import Tribler.Core.DecentralizedTracking.pymdht.core.message
import Tribler.Core.DecentralizedTracking.pymdht.core.node
import Tribler.Core.DecentralizedTracking.pymdht.core.ptime
import Tribler.Core.DecentralizedTracking.pymdht.core.routing_table
import Tribler.Core.DecentralizedTracking.pymdht.core.bootstrap


# Boudewijn: keep this import BELOW the imports from Tribler.xxx.* as
# one of those modules imports time as a module.
from time import time, sleep

I2I_LISTENPORT = 57891
VIDEOHTTP_LISTENPORT = 6875
SESSION_CHECKPOINT_INTERVAL = 900.0  # 15 minutes
CHANNELMODE_REFRESH_INTERVAL = 5.0

DEBUG = False
DEBUG_DOWNLOADS = False
ALLOW_MULTIPLE = False

#
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
#


class ABCApp():

    def __init__(self, params, single_instance_checker, installdir):
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.installdir = self.configure_install_dir(installdir)

        self.state_dir = None
        self.error = None
        self.last_update = 0
        self.ready = False
        self.done = False
        self.frame = None

        self.guiserver = GUITaskQueue.getInstance()
        self.said_start_playback = False
        self.decodeprogress = 0

        self.old_reputation = 0

        # DISPERSY will be set when available
        self.dispersy = None
        # BARTER_COMMUNITY will be set when both Dispersy and the EffortCommunity are available
        self.barter_community = None

        self.seedingmanager = None
        self.i2is = None
        self.torrentfeed = None
        self.webUI = None
        self.utility = None
        self.videoplayer = None

        try:
            bm = wx.Bitmap(os.path.join(self.installdir, 'Tribler', 'Images', 'splash.png'), wx.BITMAP_TYPE_ANY)
            self.splash = GaugeSplash(bm)
            self.splash.setTicks(10)
            self.splash.Show()

            print >> sys.stderr, 'Client Starting Up.'
            print >> sys.stderr, "Tribler is using", self.installdir, "as working directory"

            self.splash.tick('Starting API')
            s = self.startAPI(self.splash.tick)

            print >> sys.stderr, "Tribler is expecting swift in", self.sconfig.get_swift_path()

            self.dispersy = s.lm.dispersy

            self.utility = Utility(self.installdir, s.get_state_dir())
            self.utility.app = self
            self.utility.session = s
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params, self)
            GUIDBProducer.getInstance(self.dispersy.callback)

            print >> sys.stderr, 'Tribler Version:', self.utility.lang.get('version'), ' Build:', self.utility.lang.get('build')

            self.splash.tick('Loading userdownloadchoice')
            from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
            UserDownloadChoice.get_singleton().set_session_dir(s.get_state_dir())

            self.splash.tick('Initializing Family Filter')
            cat = Category.getInstance()

            state = self.utility.config.Read('family_filter')
            if state in ('1', '0'):
                cat.set_family_filter(state == '1')
            else:
                self.utility.config.Write('family_filter', '1')
                self.utility.config.Flush()

                cat.set_family_filter(True)

            # Create global rate limiter
            self.splash.tick('Setting up ratelimiters')
            self.ratelimiter = UserDefinedMaxAlwaysOtherwiseDividedOverActiveSwarmsRateManager()

            # Counter to suppress some event from occurring
            self.ratestatecallbackcount = 0

            # So we know if we asked for peer details last cycle
            self.lastwantpeers = []

            # boudewijn 01/04/2010: hack to fix the seedupload speed that
            # was never used and defaulted to 0 (unlimited upload)
            maxup = self.utility.config.Read('maxuploadrate', "int")
            if maxup == -1:  # no upload
                self.ratelimiter.set_global_max_speed(UPLOAD, 0.00001)
                self.ratelimiter.set_global_max_seedupload_speed(0.00001)
            else:
                self.ratelimiter.set_global_max_speed(UPLOAD, maxup)
                self.ratelimiter.set_global_max_seedupload_speed(maxup)

            maxdown = self.utility.config.Read('maxdownloadrate', "int")
            self.ratelimiter.set_global_max_speed(DOWNLOAD, maxdown)

            self.seedingmanager = GlobalSeedingManager(self.utility.config.Read)

            # Only allow updates to come in after we defined ratelimiter
            self.prevActiveDownloads = []
            s.set_download_states_callback(self.sesscb_states_callback)

            # Schedule task for checkpointing Session, to avoid hash checks after
            # crashes.
            self.guiserver.add_task(self.guiservthread_checkpoint_timer, SESSION_CHECKPOINT_INTERVAL)

            self.utility.postAppInit(os.path.join(self.installdir, 'Tribler', 'Images', 'tribler.ico'))

            # Put it here so an error is shown in the startup-error popup
            # Start server for instance2instance communication
            self.i2iconnhandler = InstanceConnectionHandler(self.i2ithread_readlinecallback)
            self.i2is = Instance2InstanceServer(I2I_LISTENPORT, self.i2iconnhandler)
            self.i2is.start()

            # Arno, 2010-01-15: VLC's reading behaviour of doing open-ended
            # Range: GETs causes performance problems in our code. Disable for now.
            # Arno, 2010-01-22: With the addition of a CachingStream the problem
            # is less severe (see VideoPlayer), so keep GET Range enabled.
            #
            # SimpleServer.RANGE_REQUESTS_ENABLED = False

            # Fire up the VideoPlayer, it abstracts away whether we're using
            # an internal or external video player.
            playbackmode = self.utility.config.Read('videoplaybackmode', "int")
            self.videoplayer = VideoPlayer.getInstance(httpport=VIDEOHTTP_LISTENPORT)
            self.videoplayer.register(self.utility, preferredplaybackmode=playbackmode)

            notification_init(self.utility)
            self.guiUtility.register()

            channel_only = os.path.exists(os.path.join(self.installdir, 'joinchannel'))
            if channel_only:
                f = open(os.path.join(self.installdir, 'joinchannel'), 'rb')
                channel_only = f.readline()
                f.close()

            self.frame = MainFrame(None, channel_only, PLAYBACKMODE_INTERNAL in return_feasible_playback_modes(self.utility.getPath()), self.splash.tick)

            # Arno, 2011-06-15: VLC 1.1.10 pops up separate win, don't have two.
            self.frame.videoframe = None
            if PLAYBACKMODE_INTERNAL in return_feasible_playback_modes(self.utility.getPath()):
                vlcwrap = self.videoplayer.get_vlcwrap()

                self.frame.videoframe = VideoDummyFrame(self.frame.videoparentpanel, self.utility, vlcwrap)
                self.videoplayer.set_videoframe(self.frame.videoframe)

            if sys.platform == 'win32':
                wx.CallAfter(self.frame.top_bg.Refresh)
                wx.CallAfter(self.frame.top_bg.Layout)
            else:
                self.frame.top_bg.Layout()

            # Arno, 2007-05-03: wxWidgets 2.8.3.0 and earlier have the MIME-type for .bmp
            # files set to 'image/x-bmp' whereas 'image/bmp' is the official one.
            try:
                bmphand = None
                hands = wx.Image.GetHandlers()
                for hand in hands:
                    # print "Handler",hand.GetExtension(),hand.GetType(),hand.GetMimeType()
                    if hand.GetMimeType() == 'image/x-bmp':
                        bmphand = hand
                        break
                # wx.Image.AddHandler()
                if bmphand is not None:
                    bmphand.SetMimeType('image/bmp')
            except:
                # wx < 2.7 don't like wx.Image.GetHandlers()
                print_exc()

            self.splash.Destroy()
            self.frame.Show(True)

            self.torrentfeed = RssParser.getInstance()

            self.webUI = None
            if self.utility.config.Read('use_webui', "boolean"):
                try:
                    from Tribler.Main.webUI.webUI import WebUI
                    self.webUI = WebUI.getInstance(self.guiUtility.library_manager, self.guiUtility.torrentsearch_manager, self.utility.config.Read('webui_port', "int"))
                    self.webUI.start()
                except Exception:
                    print_exc()

            wx.CallAfter(self.PostInit2)

            # 08/02/10 Boudewijn: Working from home though console
            # doesn't allow me to press close.  The statement below
            # gracefully closes Tribler after 120 seconds.
            # wx.CallLater(120*1000, wx.GetApp().Exit)

            status = get_status_holder("LivingLab")
            status.add_reporter(NullReporter("Periodically remove all events", 0))
# status.add_reporter(LivingLabPeriodicReporter("Living lab CS reporter", 300, "Tribler client")) # Report every 5 minutes
# status.add_reporter(LivingLabPeriodicReporter("Living lab CS reporter", 30, "Tribler client")) # Report every 30 seconds - ONLY FOR TESTING

            # report client version
            status.create_and_add_event("client-startup-version", [self.utility.lang.get("version")])
            status.create_and_add_event("client-startup-build", [self.utility.lang.get("build")])
            status.create_and_add_event("client-startup-build-date", [self.utility.lang.get("build_date")])

            self.ready = True

        except Exception as e:
            self.onError(e)
            return False

    def PostInit2(self):
        self.frame.Raise()
        self.startWithRightView()
        self.set_reputation()

        s = self.utility.session
        s.add_observer(self.sesscb_ntfy_reachable, NTFY_REACHABLE, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_activities, NTFY_ACTIVITIES, [NTFY_INSERT], cache=10)
        s.add_observer(self.sesscb_ntfy_channelupdates, NTFY_CHANNELCAST, [NTFY_INSERT, NTFY_UPDATE, NTFY_CREATE, NTFY_STATE, NTFY_MODIFIED], cache=10)
        s.add_observer(self.sesscb_ntfy_channelupdates, NTFY_VOTECAST, [NTFY_UPDATE], cache=10)
        s.add_observer(self.sesscb_ntfy_myprefupdates, NTFY_MYPREFERENCES, [NTFY_INSERT, NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_torrentupdates, NTFY_TORRENTS, [NTFY_UPDATE, NTFY_INSERT], cache=10)
        s.add_observer(self.sesscb_ntfy_playlistupdates, NTFY_PLAYLISTS, [NTFY_INSERT, NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_commentupdates, NTFY_COMMENTS, [NTFY_INSERT, NTFY_DELETE])
        s.add_observer(self.sesscb_ntfy_modificationupdates, NTFY_MODIFICATIONS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_moderationupdats, NTFY_MODERATIONS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_markingupdates, NTFY_MARKINGS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_torrentfinished, NTFY_TORRENTS, [NTFY_FINISHED])
        s.add_observer(self.sesscb_ntfy_magnet, NTFY_TORRENTS, [NTFY_MAGNET_GOT_PEERS, NTFY_MAGNET_PROGRESS, NTFY_MAGNET_STARTED, NTFY_MAGNET_CLOSE])

        self.dispersy.attach_progress_handler(self.frame.progressHandler)
        self.dispersy.callback.attach_exception_handler(self.frame.exceptionHandler)

        startWorker(None, self.loadSessionCheckpoint, delay=5.0, workerType="guiTaskQueue")

        # initialize the torrent feed thread
        channelcast = ChannelCastDBHandler.getInstance()

        def db_thread():
            return channelcast.getMyChannelId()

        def wx_thread(delayedResult):
            my_channel = delayedResult.get()
            if my_channel:
                self.torrentfeed.register(self.utility.session, my_channel)
                self.torrentfeed.addCallback(my_channel, self.guiUtility.channelsearch_manager.createTorrentFromDef)

        startWorker(wx_thread, db_thread, delay=5.0)

    def startAPI(self, progress):
        # Start Tribler Session
        defaultConfig = SessionStartupConfig()
        state_dir = defaultConfig.get_state_dir()
        if not state_dir:
            state_dir = Session.get_default_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)

        progress('Loading sessionconfig')
        if DEBUG:
            print >> sys.stderr, "main: Session config", cfgfilename
        try:
            self.sconfig = SessionStartupConfig.load(cfgfilename)
        except:
            self.sconfig = SessionStartupConfig()
            self.sconfig.set_state_dir(state_dir)

        self.sconfig.set_install_dir(self.installdir)

        # Arno, 2010-03-31: Hard upgrade to 50000 torrents collected
        self.sconfig.set_torrent_collecting_max_torrents(50000)

        # Arno, 2012-05-21: Swift part II
        swiftbinpath = os.path.join(self.sconfig.get_install_dir(), "swift")
        if sys.platform == "darwin":
            if not os.path.exists(swiftbinpath):
                swiftbinpath = os.path.join(os.getcwdu(), "..", "MacOS", "swift")
        self.sconfig.set_swift_path(swiftbinpath)

        progress('Loading downloadconfig')
        dlcfgfilename = get_default_dscfg_filename(self.sconfig.get_state_dir())
        if DEBUG:
            print >> sys.stderr, "main: Download config", dlcfgfilename
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        if not defaultDLConfig.get_dest_dir():
            defaultDLConfig.set_dest_dir(get_default_dest_dir())
        if not os.path.isdir(defaultDLConfig.get_dest_dir()):
            os.makedirs(defaultDLConfig.get_dest_dir())

        # Setting torrent collection dir based on default download dir
        if not self.sconfig.get_torrent_collecting_dir():
            torrcolldir = os.path.join(defaultDLConfig.get_dest_dir(), STATEDIR_TORRENTCOLL_DIR)
            self.sconfig.set_torrent_collecting_dir(torrcolldir)

        if not defaultDLConfig.get_swift_meta_dir():
            defaultDLConfig.set_swift_meta_dir(os.path.join(self.sconfig.get_state_dir(), STATEDIR_SWIFTRESEED_DIR))
        if not os.path.isdir(defaultDLConfig.get_swift_meta_dir()):
            os.makedirs(defaultDLConfig.get_swift_meta_dir())

        # 15/05/12 niels: fixing swift port
        defaultDLConfig.set_swift_listen_port(7758)

        progress('Creating session/Checking database (may take a minute)')
        s = Session(self.sconfig)
        s.start()

        def define_communities():
            from Tribler.community.search.community import SearchCommunity
            from Tribler.community.allchannel.community import AllChannelCommunity
            from Tribler.community.bartercast3.community import BarterCommunity
            from Tribler.community.channel.community import ChannelCommunity
            from Tribler.community.channel.preview import PreviewChannelCommunity

            # must be called on the Dispersy thread
            dispersy.define_auto_load(SearchCommunity,
                                     (s.dispersy_member,),
                                     load=True)
            dispersy.define_auto_load(AllChannelCommunity,
                                           (s.dispersy_member,),
                                           {"auto_join_channel": True} if sys.argv[0].endswith("dispersy-channel-booster.py") else {},
                                           load=True)
            if swift_process:
                dispersy.define_auto_load(BarterCommunity,
                                          (swift_process,),
                                          load=True)
                
            dispersy.define_auto_load(ChannelCommunity, load=True)
            dispersy.define_auto_load(PreviewChannelCommunity)

            print >> sys.stderr, "tribler: Dispersy communities are ready"

        swift_process = s.get_swift_proc() and s.get_swift_process()
        dispersy = s.get_dispersy_instance()
        dispersy.callback.call(define_communities)
        return s

    def configure_install_dir(self, installdir):
        # Niels, 2011-03-03: Working dir sometimes set to a browsers working dir
        # only seen on windows

        # apply trick to obtain the executable location
        # see http://www.py2exe.org/index.cgi/WhereAmI
        # Niels, 2012-01-31: py2exe should only apply to windows
        if sys.platform == 'win32':
            def we_are_frozen():
                """Returns whether we are frozen via py2exe.
                This will affect how we find out where we are located."""
                return hasattr(sys, "frozen")

            def module_path():
                """ This will get us the program's directory,
                even if we are frozen using py2exe"""
                if we_are_frozen():
                    return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))

                filedir = os.path.dirname(unicode(__file__, sys.getfilesystemencoding()))
                return os.path.abspath(os.path.join(filedir, '..', '..'))

            return module_path()
        return installdir

    @forceWxThread
    def sesscb_ntfy_myprefupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            if changeType == NTFY_INSERT:
                if self.frame.searchlist:
                    manager = self.frame.searchlist.GetManager()
                    manager.downloadStarted(objectID)

                manager = self.frame.selectedchannellist.GetManager()
                manager.downloadStarted(objectID)

            manager = self.frame.librarylist.GetManager()
            manager.downloadStarted(objectID)

    def set_reputation(self):
        def do_db():
            nr_connections = 0
            if self.dispersy:
                for community in self.dispersy.get_communities():
                    from Tribler.community.search.community import SearchCommunity
                    if isinstance(community, SearchCommunity):
                        nr_connections = community.get_nr_connections()

            return nr_connections

        def do_wx(delayedResult):
            nr_connections = delayedResult.get()

            # self.frame.SRstatusbar.set_reputation(myRep, total_down, total_up)

            # bitmap is 16px wide, -> but first and last pixel do not add anything.
            percentage = min(1.0, (nr_connections + 1) / 16.0)
            self.frame.SRstatusbar.SetConnections(percentage, nr_connections)

        """ set the reputation in the GUI"""
        if self.ready and self.frame.ready:
            startWorker(do_wx, do_db, uId=u"tribler.set_reputation")
        startWorker(None, self.set_reputation, delay=5.0, workerType="guiTaskQueue")

    def _dispersy_get_barter_community(self):
        try:
            return self.dispersy.get_community(BARTER_MASTER_MEMBER_PUBLIC_KEY_DIGEST, load=False, auto_load=False)
        except KeyError:
            return None

    def sesscb_states_callback(self, dslist):
        if not self.ready:
            return (5.0, [])

        wantpeers = []
        self.ratestatecallbackcount += 1
        if DEBUG:
            torrentdb = self.utility.session.open_dbhandler(NTFY_TORRENTS)
            peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
            print >> sys.stderr, "main: Stats: Total torrents found", torrentdb.size(), "peers", peerdb.size()

        try:
            # Print stats on Console
            if DEBUG:
                if self.ratestatecallbackcount % 5 == 0:
                    for ds in dslist:
                        safename = repr(ds.get_download().get_def().get_name())
                        if DEBUG:
                            print >> sys.stderr, "%s %s %.1f%% dl %.1f ul %.1f n %d" % (safename, dlstatus_strings[ds.get_status()], 100.0 * ds.get_progress(), ds.get_current_speed(DOWNLOAD), ds.get_current_speed(UPLOAD), ds.get_num_peers())
                        # print >>sys.stderr,"main: Infohash:",`ds.get_download().get_def().get_infohash()`
                        if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                            print >> sys.stderr, "main: Error:", repr(ds.get_error())

            # Pass DownloadStates to libaryView
            no_collected_list = []
            try:
                coldir = os.path.basename(os.path.abspath(self.utility.session.get_torrent_collecting_dir()))
                for ds in dslist:
                    destdir = os.path.basename(ds.get_download().get_dest_dir())
                    if destdir != coldir:
                        no_collected_list.append(ds)
                # Arno, 2012-07-17: Retrieving peerlist for the DownloadStates takes CPU
                # so only do it when needed for display.
                wantpeers.extend(self.guiUtility.library_manager.download_state_callback(no_collected_list))
            except:
                print_exc()

            # Update bandwidth statistics in the Barter Community
            if not self.barter_community:
                self.barter_community = self.dispersy.callback.call(self._dispersy_get_barter_community)

            if self.barter_community and not isinstance(self.barter_community, HardKilledCommunity):
                if self.barter_community.has_been_killed:
                    # set BARTER_COMMUNITY to None.  next state callback we will again get the
                    # community resulting in the HardKilledCommunity instead
                    self.barter_community = None
                else:
                    if True in self.lastwantpeers:
                        self.dispersy.callback.register(self.barter_community.download_state_callback, (dslist, True))

                    # only request peer info every 120 intervals
                    if self.ratestatecallbackcount % 120 == 0:
                        wantpeers.append(True)

            # Find State of currently playing video
            playds = None
            d = self.videoplayer.get_vod_download()
            for ds in dslist:
                if ds.get_download() == d:
                    playds = ds

            # Apply status displaying from SwarmPlayer
            if playds:
                def do_video():
                    videoplayer_mediastate = self.videoplayer.get_state()

                    totalhelping = 0
                    totalspeed = {UPLOAD: 0.0, DOWNLOAD: 0.0}
                    for ds in dslist:
                        totalspeed[UPLOAD] += ds.get_current_speed(UPLOAD)
                        totalspeed[DOWNLOAD] += ds.get_current_speed(DOWNLOAD)
                        totalhelping += ds.get_num_peers()

                    [topmsg, msg, self.said_start_playback, self.decodeprogress] = get_status_msgs(playds, videoplayer_mediastate, "Tribler", self.said_start_playback, self.decodeprogress, totalhelping, totalspeed)
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

                    # print >>sys.stderr,"main: Messages",topmsg,msg,`playds.get_download().get_def().get_name()`
                    playds.vod_status_msg = text
                    self.videoplayer.set_player_status_and_progress(text, playds.get_pieces_complete())
                wx.CallAfter(do_video)

            # Check to see if a download has finished
            newActiveDownloads = []
            doCheckpoint = False
            for ds in dslist:
                state = ds.get_status()
                safename = ds.get_download().get_def().get_name()

                if state == DLSTATUS_DOWNLOADING:
                    newActiveDownloads.append(safename)

                elif state == DLSTATUS_SEEDING:
                    if safename in self.prevActiveDownloads:
                        download = ds.get_download()
                        cdef = download.get_def()

                        coldir = os.path.basename(os.path.abspath(self.utility.session.get_torrent_collecting_dir()))
                        destdir = os.path.basename(download.get_dest_dir())
                        if destdir != coldir:
                            hash = cdef.get_id()

                            notifier = Notifier.getInstance()
                            notifier.notify(NTFY_TORRENTS, NTFY_FINISHED, hash, safename)

                            # Arno, 2012-05-04: Swift reseeding
                            if self.utility.config.Read('swiftreseed') == 1 and cdef.get_def_type() == 'torrent' and not download.get_selected_files():
                                self.sesscb_reseed_via_swift(download)

                            doCheckpoint = True

            self.prevActiveDownloads = newActiveDownloads
            if doCheckpoint:
                self.utility.session.checkpoint()

            self.seedingmanager.apply_seeding_policy(no_collected_list)

            # The VideoPlayer instance manages both pausing and
            # restarting of torrents before and after VOD playback
            # occurs.
            self.videoplayer.restart_other_downloads(no_collected_list)

            # Adjust speeds once every 4 seconds
            adjustspeeds = False
            if self.ratestatecallbackcount % 4 == 0:
                adjustspeeds = True

            if adjustspeeds:
                swift_dslist = [ds for ds in no_collected_list if ds.get_download().get_def().get_def_type() == 'swift']
                self.ratelimiter.add_downloadstatelist(swift_dslist)
                self.ratelimiter.adjust_speeds()

                if DEBUG_DOWNLOADS:
                    for ds in dslist:
                        cdef = ds.get_download().get_def()
                        state = ds.get_status()
                        if cdef.get_def_type() == 'swift':
                            safename = cdef.get_name()
                            print >> sys.stderr, "tribler: SW", dlstatus_strings[state], safename, ds.get_current_speed(UPLOAD)
                        else:
                            print >> sys.stderr, "tribler: BT", dlstatus_strings[state], cdef.get_name(), ds.get_current_speed(UPLOAD)

        except:
            print_exc()

        self.lastwantpeers = wantpeers
        return (1.0, wantpeers)

    def loadSessionCheckpoint(self):
        # Niels: first remove all "swift" torrent collect checkpoints
        dir = self.utility.session.get_downloads_pstate_dir()
        coldir = os.path.basename(os.path.abspath(self.utility.session.get_torrent_collecting_dir()))

        filelist = os.listdir(dir)
        filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.pickle')]

        for file in filelist:
            try:
                pstate = self.utility.session.lm.load_download_pstate(file)
                dlconfig = pstate['dlconfig']

                if dlconfig.get('saveas', ''):
                    destdir = os.path.basename(dlconfig['saveas'])
                    if destdir == coldir:
                        os.remove(file)
            except:
                pass

        from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
        user_download_choice = UserDownloadChoice.get_singleton()
        initialdlstatus_dict = {}
        for id, state in user_download_choice.get_download_states().iteritems():
            if state == 'stop':
                initialdlstatus_dict[id] = DLSTATUS_STOPPED

        self.utility.session.load_checkpoint(initialdlstatus_dict=initialdlstatus_dict)

    def guiservthread_checkpoint_timer(self):
        """ Periodically checkpoint Session """
        if self.done:
            return
        try:
            print >> sys.stderr, "main: Checkpointing Session"
            self.utility.session.checkpoint()

            self.guiserver.add_task(self.guiservthread_checkpoint_timer, SESSION_CHECKPOINT_INTERVAL)
        except:
            print_exc()

    @forceWxThread
    def sesscb_ntfy_activities(self, events):
        if self.ready and self.frame.ready:
            for args in events:
                objectID = args[2]
                args = args[3:]

                self.frame.setActivity(objectID, *args)

    @forceWxThread
    def sesscb_ntfy_reachable(self, subject, changeType, objectID, msg):
        if self.ready and self.frame.ready:
            self.frame.SRstatusbar.onReachable()

    @forceWxThread
    def sesscb_ntfy_channelupdates(self, events):
        if self.ready and self.frame.ready:
            for args in events:
                subject = args[0]
                changeType = args[1]
                objectID = args[2]

                if self.frame.channellist:
                    if len(args) > 3:
                        myvote = args[3]
                    else:
                        myvote = False

                    manager = self.frame.channellist.GetManager()
                    manager.channelUpdated(objectID, subject == NTFY_VOTECAST, myvote=myvote)

                manager = self.frame.selectedchannellist.GetManager()
                manager.channelUpdated(objectID, stateChanged=changeType == NTFY_STATE, modified=changeType == NTFY_MODIFIED)

                if changeType == NTFY_CREATE:
                    if self.frame.channellist:
                        self.frame.channellist.SetMyChannelId(objectID)

                    self.torrentfeed.register(self.utility.session, objectID)
                    self.torrentfeed.addCallback(objectID, self.guiUtility.channelsearch_manager.createTorrentFromDef)

                self.frame.managechannel.channelUpdated(objectID, created=changeType == NTFY_CREATE, modified=changeType == NTFY_MODIFIED)

    @forceWxThread
    def sesscb_ntfy_torrentupdates(self, events):
        if self.ready and self.frame.ready:
            infohashes = [args[2] for args in events]

            if self.frame.searchlist:
                manager = self.frame.searchlist.GetManager()
                manager.torrentsUpdated(infohashes)

                manager = self.frame.selectedchannellist.GetManager()
                manager.torrentsUpdated(infohashes)

                manager = self.frame.playlist.GetManager()
                manager.torrentsUpdated(infohashes)

                manager = self.frame.librarylist.GetManager()
                manager.torrentsUpdated(infohashes)

    def sesscb_ntfy_torrentfinished(self, subject, changeType, objectID, *args):
        self.guiUtility.Notify("Download Completed", "Torrent '%s' has finished downloading. Now seeding." % args[0], icon='seed')

        if self.ready and self.frame.ready:
            self.guiUtility.torrentstate_manager.torrentFinished(objectID)

    def sesscb_ntfy_magnet(self, subject, changetype, objectID, *args):
        if changetype == NTFY_MAGNET_STARTED:
            self.guiUtility.library_manager.magnet_started(objectID)
        elif changetype == NTFY_MAGNET_GOT_PEERS:
            self.guiUtility.library_manager.magnet_got_peers(objectID, args[0])
        elif changetype == NTFY_MAGNET_PROGRESS:
            self.guiUtility.library_manager.magnet_got_piece(objectID, args[0])
        elif changetype == NTFY_MAGNET_CLOSE:
            self.guiUtility.library_manager.magnet_close(objectID)

    @forceWxThread
    def sesscb_ntfy_playlistupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            if changeType == NTFY_INSERT:
                self.frame.managechannel.playlistCreated(objectID)

                manager = self.frame.selectedchannellist.GetManager()
                manager.playlistCreated(objectID)

            else:
                self.frame.managechannel.playlistUpdated(objectID, modified=changeType == NTFY_MODIFIED)

                if len(args) > 0:
                    infohash = args[0]
                else:
                    infohash = False
                manager = self.frame.selectedchannellist.GetManager()
                manager.playlistUpdated(objectID, infohash, modified=changeType == NTFY_MODIFIED)

                manager = self.frame.playlist.GetManager()
                manager.playlistUpdated(objectID, modified=changeType == NTFY_MODIFIED)

    @forceWxThread
    def sesscb_ntfy_commentupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            self.frame.selectedchannellist.OnCommentCreated(objectID)
            self.frame.playlist.OnCommentCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_modificationupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            self.frame.selectedchannellist.OnModificationCreated(objectID)
            self.frame.playlist.OnModificationCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_moderationupdats(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            self.frame.selectedchannellist.OnModerationCreated(objectID)
            self.frame.playlist.OnModerationCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_markingupdates(self, subject, changeType, objectID, *args):
        if self.ready and self.frame.ready:
            self.frame.selectedchannellist.OnMarkingCreated(objectID)
            self.frame.playlist.OnModerationCreated(objectID)

    @forceWxThread
    def onError(self, e):
        print_exc()
        type, value, stack = sys.exc_info()
        backtrace = traceback.format_exception(type, value, stack)

        win = FeedbackWindow("Unfortunately, Tribler ran into an internal error")
        win.CreateOutputWindow('')
        for line in backtrace:
            win.write(line)

        win.ShowModal()

    def MacOpenFile(self, filename):
        print >> sys.stderr, filename
        target = FileDropTarget(self.frame)
        target.OnDropFiles(None, None, [filename])

    def OnExit(self):
        print >> sys.stderr, "main: ONEXIT"
        self.ready = False
        self.done = True

        # write all persistent data to disk
        if self.i2is:
            self.i2is.shutdown()
        if self.torrentfeed:
            self.torrentfeed.shutdown()
            self.torrentfeed.delInstance()
        if self.webUI:
            self.webUI.stop()
        if self.guiserver:
            self.guiserver.shutdown(True)
            self.guiserver.delInstance()
        if self.videoplayer:
            self.videoplayer.shutdown()
            self.videoplayer.delInstance()

        delete_status_holders()

        if self.frame:
            del self.frame

        # Don't checkpoint, interferes with current way of saving Preferences,
        # see Tribler/Main/Dialogs/abcoption.py
        if self.utility:
            # Niels: lets add a max waiting time for this session shutdown.
            session_shutdown_start = time()

            self.utility.session.shutdown(hacksessconfcheckpoint=False)

            # Arno, 2012-07-12: Shutdown should be quick
            # Niels, 2013-03-21: However, setting it too low will prevent checkpoints from being written to disk
            waittime = 60
            while not self.utility.session.has_shutdown():
                diff = time() - session_shutdown_start
                if diff > waittime:
                    print >> sys.stderr, "main: ONEXIT NOT Waiting for Session to shutdown, took too long"
                    break

                print >> sys.stderr, "main: ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds" % (waittime - diff)
                sleep(3)
            print >> sys.stderr, "main: ONEXIT Session is shutdown"

            try:
                print >> sys.stderr, "main: ONEXIT cleaning database"
                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
                peerdb._db.clean_db(randint(0, 24) == 0, exiting=True)
            except:
                print_exc()

            print >> sys.stderr, "main: ONEXIT deleting instances"

        Session.del_instance()
        GUIUtility.delInstance()
        GUIDBProducer.delInstance()
        DefaultDownloadStartupConfig.delInstance()

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        return 0

    def db_exception_handler(self, e):
        if DEBUG:
            print >> sys.stderr, "main: Database Exception handler called", e, "value", e.args, "#"
        try:
            if e.args[1] == "DB object has been closed":
                return  # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return  # don't repeat same error
        except:
            print >> sys.stderr, "main: db_exception_handler error", e, type(e)
            print_exc()
            # print_stack()

        self.onError(e)

    def getConfigPath(self):
        return self.utility.getConfigPath()

    def startWithRightView(self):
        if self.params[0] != "":
            self.guiUtility.ShowPage('my_files')

    def i2ithread_readlinecallback(self, ic, cmd):
        """ Called by Instance2Instance thread """

        print >> sys.stderr, "main: Another instance called us with cmd", cmd
        ic.close()

        if cmd.startswith('START '):
            param = cmd[len('START '):].strip()
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
                elif torrentfilename.startswith("tswift://") or torrentfilename.startswith("ppsp://"):
                    self.frame.startDownloadFromSwift(torrentfilename)
                else:
                    self.frame.startDownload(torrentfilename)
                self.guiUtility.ShowPage('my_files')

            wx.CallAfter(start_asked_download)

    def sesscb_reseed_via_swift(self, td, callback=None):
        # Arno, 2012-05-07: root hash calculation may take long time, halting
        # SessionCallbackThread meaning download statuses won't be updated.
        # Offload to diff thread.
        #
        t = Thread(target=self.workerthread_reseed_via_swift_run, args=(td, callback), name="SwiftRootHashCalculator")
        t.start()
        # apparently daemon by default

    def workerthread_reseed_via_swift_run(self, td, callback=None):
        # Open issues:
        # * how to display these "parallel" downloads in GUI?
        # * make swift reseed user configurable (see 'swiftreseed' in utility.py
        # * roothash calc on separate thread?
        # * Update pymDHT to one with swift interface.
        # * Save (infohash,roothash) pair such that when BT download is removed
        #   the other is (kept/deleted/...) too.
        #
        try:
            if prctlimported:
                prctl.set_name(currentThread().getName())

            # 1. Get torrent info
            tdef = td.get_def()
            destdir = td.get_dest_dir()

            # renaming swarmname for now not supported in swift
            if td.correctedinfoname != fix_filebasename(tdef.get_name_as_unicode()):
                return

            # 2. Convert to swift def
            sdef = SwiftDef()
            # RESEEDTODO: set to swift inf of pymDHT
            sdef.set_tracker("127.0.0.1:%d" % self.sconfig.get_swift_dht_listen_port())
            iotuples = td.get_dest_files()
            for i, o in iotuples:
                # print >>sys.stderr,"python: add_content",i,o
                if len(iotuples) == 1:
                    sdef.add_content(o)  # single file .torrent
                else:
                    xi = os.path.join(tdef.get_name_as_unicode(), i)
                    if sys.platform == "win32":
                        xi = xi.replace("\\", "/")
                    si = xi.encode("UTF-8")  # spec format
                    sdef.add_content(o, si)  # multi-file .torrent

            specpn = sdef.finalize(self.sconfig.get_swift_path(), destdir=destdir)

            # 3. Save swift files to metadata dir
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            metadir = defaultDLConfig.get_swift_meta_dir()
            if len(iotuples) == 1:
                storagepath = iotuples[0][1]  # Point to file on disk
                metapath = os.path.join(metadir, os.path.split(storagepath)[1])

                try:
                    shutil.move(storagepath + '.mhash', metapath + '.mhash')
                    shutil.move(storagepath + '.mbinmap', metapath + '.mbinmap')
                except:
                    print_exc()

            else:
                storagepath = destdir  # Point to dest dir
                metapath = os.path.join(metadir, sdef.get_roothash_as_hex())

                # Reuse .mhash and .mbinmap (happens automatically for single-file)
                try:
                    shutil.move(specpn, metapath + '.mfspec')
                    shutil.move(specpn + '.mhash', metapath + '.mhash')
                    shutil.move(specpn + '.mbinmap', metapath + '.mbinmap')
                except:
                    print_exc()

            # 4. Start Swift download via GUI Thread
            wx.CallAfter(self.frame.startReseedSwiftDownload, tdef, storagepath, sdef)

            # 5. Call the callback to notify
            if callback:
                callback(sdef)
        except:
            print_exc()
            raise


def get_status_msgs(ds, videoplayer_mediastate, appname, said_start_playback, decodeprogress, totalhelping, totalspeed):

    intime = "Not playing for quite some time."
    ETA = ((60 * 15, "Playing in less than 15 minutes."),
           (60 * 10, "Playing in less than 10 minutes."),
           (60 * 5, "Playing in less than 5 minutes."),
           (60, "Playing in less than a minute."))

    topmsg = ''
    msg = ''

    logmsgs = ds.get_log_messages()
    logmsg = None
    if DEBUG and len(logmsgs) > 0:
        print >> sys.stderr, "main: Log", logmsgs[0]
        logmsg = logmsgs[-1][1]

    preprogress = ds.get_vod_prebuffering_progress()
    playable = ds.get_vod_playable()
    t = ds.get_vod_playable_after()

    intime = ETA[0][1]
    for eta_time, eta_msg in ETA:
        if t > eta_time:
            break
        intime = eta_msg

    # print >>sys.stderr,"main: playble",playable,"preprog",preprogress
    # print >>sys.stderr,"main: ETA is",t,"secs"
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

    # print >>sys.stderr,"main: VODStats",preprogress,playable,"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"

    if ds.get_status() == DLSTATUS_HASHCHECKING:
        genprogress = ds.get_progress()
        pstr = str(int(genprogress * 100))
        msg = "Checking already downloaded parts " + pstr + "% done"
    elif ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
        msg = 'Error playing: ' + str(ds.get_error())
    elif ds.get_status() == DLSTATUS_ALLOCATING_DISKSPACE:
        msg = 'Allocating disk space'
    elif ds.get_progress() == 1.0:
        msg = ''
    elif playable:
        if not said_start_playback:
            msg = "Starting playback..."

        if videoplayer_mediastate == MEDIASTATE_STOPPED and said_start_playback:
            if totalhelping == 0:
                topmsg = u"Please leave the " + appname + " running, this will help other " + appname + " users to download faster."
            else:
                topmsg = u"Helping " + str(totalhelping) + " " + appname + " users to download. Please leave it running in the background."

            # Display this on status line
            # TODO: Show balloon in systray when closing window to indicate things continue there
            msg = ''

        elif videoplayer_mediastate == MEDIASTATE_PLAYING:
            said_start_playback = True
            # It may take a while for VLC to actually start displaying
            # video, as it is trying to tune in to the stream (finding
            # I-Frame). Display some info to show that:
            #
            cdef = ds.get_download().get_def()
            if cdef.get_def_type() == 'torrent':
                cname = cdef.get_name_as_unicode()
            else:
                cname = cdef.get_def_type()
            topmsg = u'Decoding: ' + cname + ' ' + str(decodeprogress) + ' s'
            decodeprogress += 1
            msg = ''
        elif videoplayer_mediastate == MEDIASTATE_PAUSED:
            # msg = "Buffering... " + str(int(100.0*preprogress))+"%"
            msg = "Buffering... " + str(int(100.0 * preprogress)) + "%. " + intime
        else:
            msg = ''

    elif preprogress != 1.0:
        pstr = str(int(preprogress * 100))
        npeers = ds.get_num_peers()
        npeerstr = str(npeers)
        if npeers == 0 and logmsg is not None:
            msg = logmsg
        elif npeers == 1:
            msg = "Prebuffering " + pstr + "% done (connected to 1 peer). " + intime
        else:
            msg = "Prebuffering " + pstr + "% done (connected to " + npeerstr + " peers). " + intime

        try:
            d = ds.get_download()
            tdef = d.get_def()
            videofiles = d.get_selected_files()
            if len(videofiles) >= 1:
                videofile = videofiles[0]
            else:
                videofile = None

            bitrate = None
            if tdef.get_def_type() == "torrent":
                try:
                    bitrate = tdef.get_bitrate(videofile)
                except:
                    print_exc()

            if bitrate is None:
                msg += ' This video may not play properly because its bitrate is unknown.'
        except:
            print_exc()
    else:
        # msg = "Waiting for sufficient download speed... "+intime
        msg = 'Waiting for sufficient download speed... ' + intime

    """
    npeers = ds.get_num_peers()
    if npeers == 1:
        msg = "One person found, receiving %.1f KB/s" % totalspeed[DOWNLOAD]
    else:
        msg = "%d people found, receiving %.1f KB/s" % (npeers, totalspeed[DOWNLOAD])
    """
    return [topmsg, msg, said_start_playback, decodeprogress]


#
#
# Main Program Start Here
#
#
@attach_profiler
def run(params=None):
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
            # Send  torrent info to abc single instance
            if params[0] != "":
                torrentfilename = params[0]
                i2ic = Instance2InstanceClient(I2I_LISTENPORT, 'START', torrentfilename)

            print "Client shutting down. Detected another instance."
        else:
            arg0 = sys.argv[0].lower()
            if arg0.endswith('.exe'):
                # supply a unicode string to ensure that the unicode filesystem API is used (applies to windows)
                installdir = os.path.abspath(os.path.dirname(unicode(sys.argv[0])))
            else:
                # call the unicode specific getcwdu() otherwise homedirectories may crash
                installdir = os.getcwdu()
            # Arno: don't chdir to allow testing as other user from other dir.
            # os.chdir(installdir)

            # Launch first abc single instance
            app = wx.GetApp()
            if not app:
                app = wx.PySimpleApp(redirect=False)
            abc = ABCApp(params, single_instance_checker, installdir)
            if abc.frame:
                app.SetTopWindow(abc.frame)
                abc.frame.set_wxapp(app)
                app.MainLoop()

            # since ABCApp is not a wx.App anymore, we need to call OnExit explicitly.
            abc.OnExit()

            # Niels: No code should be present here, only executed after gui closes

        print "Client shutting down. Sleeping for a few seconds to allow other threads to finish"
        sleep(5)

    except:
        print_exc()


    # This is the right place to close the database, unfortunately Linux has
    # a problem, see ABCFrame.OnCloseWindow
    #
    # if sys.platform != 'linux2':
    #    tribler_done(configpath)
    # os._exit(0)

if __name__ == '__main__':
    run()
