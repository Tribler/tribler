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

import sys
import logging
from Tribler.Main.Utility.compat import convertSessionConfig, convertMainConfig, convertDefaultDownloadConfig, convertDownloadCheckpoints
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
from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUIDBProducer
from Tribler.dispersy.decorator import attach_profiler
from Tribler.dispersy.community import HardKilledCommunity
from Tribler.community.bartercast3.community import MASTER_MEMBER_PUBLIC_KEY_DIGEST as BARTER_MASTER_MEMBER_PUBLIC_KEY_DIGEST
from Tribler.Core.CacheDB.Notifier import Notifier
import traceback
from random import randint
from threading import currentThread
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

# Arno, 2008-03-21: see what happens when we disable this locale thing. Gives
# errors on Vista in "Regional and Language Settings Options" different from
# "English[United Kingdom]"
# import locale

import wx
from Tribler.Main.vwxGUI.gaugesplash import GaugeSplash
from Tribler.Main.vwxGUI.MainFrame import FileDropTarget
from Tribler.Main.Dialogs.FeedbackWindow import FeedbackWindow
# import hotshot

from traceback import print_exc
import urllib2
import tempfile

from Tribler.Main.vwxGUI.MainFrame import MainFrame  # py2exe needs this import
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.MainVideoFrame import VideoDummyFrame
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
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
from Tribler.Utilities.SingleInstanceChecker import SingleInstanceChecker

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
        self._logger = logging.getLogger(self.__class__.__name__)

        self.params = params
        self.single_instance_checker = single_instance_checker
        self.installdir = installdir

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

        self.gui_image_manager = GuiImageManager.getInstance(installdir)

        try:
            bm = self.gui_image_manager.getImage(u'splash.png')
            self.splash = GaugeSplash(bm)
            self.splash.setTicks(10)
            self.splash.Show()

            self._logger.info('Client Starting Up.')
            self._logger.info("Tribler is using %s as working directory", self.installdir)

            self.splash.tick('Starting API')
            s = self.startAPI(self.splash.tick)

            self._logger.info("Tribler is expecting swift in %s", self.sconfig.get_swift_path())

            self.dispersy = s.lm.dispersy

            self.utility = Utility(self.installdir, s.get_state_dir())
            self.utility.app = self
            self.utility.session = s
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params, self)
            GUIDBProducer.getInstance(self.dispersy.callback)

            self._logger.info('Tribler Version: %s Build: %s', self.utility.lang.get('version'), self.utility.lang.get('build'))

            self.splash.tick('Loading userdownloadchoice')
            from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
            UserDownloadChoice.get_singleton().set_utility(self.utility, s.get_state_dir())

            self.splash.tick('Initializing Family Filter')
            cat = Category.getInstance()

            state = self.utility.read_config('family_filter')
            if state in (1, 0):
                cat.set_family_filter(state == 1)
            else:
                self.utility.write_config('family_filter', 1)
                self.utility.flush_config()

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
            maxup = self.utility.read_config('maxuploadrate')
            if maxup == -1:  # no upload
                self.ratelimiter.set_global_max_speed(UPLOAD, 0.00001)
                self.ratelimiter.set_global_max_seedupload_speed(0.00001)
            else:
                self.ratelimiter.set_global_max_speed(UPLOAD, maxup)
                self.ratelimiter.set_global_max_seedupload_speed(maxup)

            maxdown = self.utility.read_config('maxdownloadrate')
            self.ratelimiter.set_global_max_speed(DOWNLOAD, maxdown)

            self.seedingmanager = GlobalSeedingManager(self.utility.read_config)

            # Only allow updates to come in after we defined ratelimiter
            self.prevActiveDownloads = []
            s.set_download_states_callback(self.sesscb_states_callback)

            # Schedule task for checkpointing Session, to avoid hash checks after
            # crashes.
            self.guiserver.add_task(self.guiservthread_checkpoint_timer, SESSION_CHECKPOINT_INTERVAL)

            if not ALLOW_MULTIPLE:
                # Put it here so an error is shown in the startup-error popup
                # Start server for instance2instance communication
                self.i2iconnhandler = InstanceConnectionHandler(self.i2ithread_readlinecallback)
                self.i2is = Instance2InstanceServer(self.utility.read_config('i2ilistenport'), self.i2iconnhandler)
                self.i2is.start()

            # Arno, 2010-01-15: VLC's reading behaviour of doing open-ended
            # Range: GETs causes performance problems in our code. Disable for now.
            # Arno, 2010-01-22: With the addition of a CachingStream the problem
            # is less severe (see VideoPlayer), so keep GET Range enabled.
            #
            # SimpleServer.RANGE_REQUESTS_ENABLED = False

            # Fire up the VideoPlayer, it abstracts away whether we're using
            # an internal or external video player.

            httpport = self.utility.read_config('videohttpport')
            if ALLOW_MULTIPLE or httpport == -1:
                httpport = self.utility.get_free_random_port('videohttpport')
            self.videoplayer = VideoPlayer.getInstance(httpport=httpport)

            playbackmode = self.utility.read_config('videoplaybackmode')
            self.videoplayer.register(self.utility, preferredplaybackmode=playbackmode)

            notification_init(self.utility)
            self.guiUtility.register()

            channel_only = os.path.exists(os.path.join(self.installdir, 'joinchannel'))
            if channel_only:
                f = open(os.path.join(self.installdir, 'joinchannel'), 'rb')
                channel_only = f.readline()
                f.close()

            self.frame = MainFrame(None, channel_only, PLAYBACKMODE_INTERNAL in return_feasible_playback_modes(self.utility.getPath()), self.splash.tick)
            self.frame.SetIcon(wx.Icon(os.path.join(self.installdir, 'Tribler', 'Main', 'vwxGUI', 'images', 'tribler.ico'), wx.BITMAP_TYPE_ICO))

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
            if self.utility.read_config('use_webui'):
                try:
                    from Tribler.Main.webUI.webUI import WebUI
                    self.webUI = WebUI.getInstance(self.guiUtility.library_manager, self.guiUtility.torrentsearch_manager, self.utility.read_config('webui_port'))
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
        self._logger.debug("main: Session config %s", cfgfilename)
        try:
            self.sconfig = SessionStartupConfig.load(cfgfilename)
        except:
            try:
                self.sconfig = convertSessionConfig(os.path.join(state_dir, 'sessconfig.pickle'), cfgfilename)
                convertMainConfig(state_dir, os.path.join(state_dir, 'abc.conf'), os.path.join(state_dir, 'tribler.conf'))
            except:
                self.sconfig = SessionStartupConfig()
                self.sconfig.set_state_dir(state_dir)

        self.sconfig.set_install_dir(self.installdir)

        # Boudewijn, 2013-06-17: Enable Dispersy tunnel (hard-coded)
        # self.sconfig.set_dispersy_tunnel_over_swift(True)
        # Boudewijn, 2013-07-17: Disabling Dispersy tunnel (hard-coded)
        self.sconfig.set_dispersy_tunnel_over_swift(False)

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
        self._logger.debug("main: Download config %s", dlcfgfilename)
        try:
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        except:
            try:
                defaultDLConfig = convertDefaultDownloadConfig(os.path.join(state_dir, 'dlconfig.pickle'), dlcfgfilename)
            except:
                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        if not defaultDLConfig.get_dest_dir():
            defaultDLConfig.set_dest_dir(get_default_dest_dir())
        if not os.path.isdir(defaultDLConfig.get_dest_dir()):
            try:
                os.makedirs(defaultDLConfig.get_dest_dir())
            except:
                # Could not create directory, ask user to select a different location
                dlg = wx.DirDialog(None, "Could not find download directory, please select a new location to store your downloads", style=wx.DEFAULT_DIALOG_STYLE)
                dlg.SetPath(get_default_dest_dir())
                if dlg.ShowModal() == wx.ID_OK:
                    new_dest_dir = dlg.GetPath()
                    defaultDLConfig.set_dest_dir(new_dest_dir)
                    defaultDLConfig.save(dlcfgfilename)
                    self.sconfig.set_torrent_collecting_dir(os.path.join(new_dest_dir, STATEDIR_TORRENTCOLL_DIR))
                    self.sconfig.set_swift_meta_dir(os.path.join(new_dest_dir, STATEDIR_SWIFTRESEED_DIR))
                    self.sconfig.save(cfgfilename)
                else:
                    # Quit
                    self.onError = lambda e: self._logger.error("tribler: quitting due to non-existing destination directory")
                    raise Exception()

        # Setting torrent collection dir based on default download dir
        if not self.sconfig.get_torrent_collecting_dir():
            self.sconfig.set_torrent_collecting_dir(os.path.join(defaultDLConfig.get_dest_dir(), STATEDIR_TORRENTCOLL_DIR))
        if not self.sconfig.get_swift_meta_dir():
            self.sconfig.set_swift_meta_dir(os.path.join(defaultDLConfig.get_dest_dir(), STATEDIR_SWIFTRESEED_DIR))

        progress('Creating session/Checking database (may take a minute)')
        s = Session(self.sconfig)
        s.start()

        def define_communities():
            from Tribler.community.search.community import SearchCommunity
            from Tribler.community.allchannel.community import AllChannelCommunity
            from Tribler.community.channel.community import ChannelCommunity
            from Tribler.community.channel.preview import PreviewChannelCommunity

            self._logger.info("tribler: Preparing communities...")
            now = time()

            # must be called on the Dispersy thread
            dispersy.define_auto_load(SearchCommunity,
                                     (s.dispersy_member,),
                                     load=True)
            dispersy.define_auto_load(AllChannelCommunity,
                                           (s.dispersy_member,),
                                           {},
                                           load=True)

            # 17/07/13 Boudewijn: the missing-member message send by the BarterCommunity on the swift port is crashing
            # 6.1 clients.  We will disable the BarterCommunity for version 6.2, giving people some time to upgrade
            # their version before enabling it again.
            # if swift_process:
            #     dispersy.define_auto_load(BarterCommunity,
            #                               (swift_process,),
            #                               load=True)

            dispersy.define_auto_load(ChannelCommunity, load=True)
            dispersy.define_auto_load(PreviewChannelCommunity)

            diff = time() - now
            self._logger.info("tribler: communities are ready in %.2f seconds", diff)

        swift_process = s.get_swift_proc() and s.get_swift_process()
        dispersy = s.get_dispersy_instance()
        dispersy.callback.call(define_communities)
        return s

    @staticmethod
    def determine_install_dir():
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
        return os.getcwdu()

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
            nr_channel_connections = 0
            if self.dispersy:
                for community in self.dispersy.get_communities():
                    from Tribler.community.search.community import SearchCommunity
                    from Tribler.community.allchannel.community import AllChannelCommunity

                    if isinstance(community, SearchCommunity):
                        nr_connections = community.get_nr_connections()
                    elif isinstance(community, AllChannelCommunity):
                        nr_channel_connections = community.get_nr_connections()

            return nr_connections, nr_channel_connections

        def do_wx(delayedResult):
            nr_connections, nr_channel_connections = delayedResult.get()

            # self.frame.SRstatusbar.set_reputation(myRep, total_down, total_up)

            # bitmap is 16px wide, -> but first and last pixel do not add anything.
            percentage = min(1.0, (nr_connections + 1) / 16.0)
            self.frame.SRstatusbar.SetConnections(percentage, nr_connections, nr_channel_connections)

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
            self._logger.debug("main: Stats: Total torrents found %s peers %s" % \
                (repr(torrentdb.size()), repr(peerdb.size())))

        try:
            # Print stats on Console
            if DEBUG:
                if self.ratestatecallbackcount % 5 == 0:
                    for ds in dslist:
                        safename = repr(ds.get_download().get_def().get_name())
                        self._logger.debug("%s %s %.1f%% dl %.1f ul %.1f n %d", safename, dlstatus_strings[ds.get_status()], 100.0 * ds.get_progress(), ds.get_current_speed(DOWNLOAD), ds.get_current_speed(UPLOAD), ds.get_num_peers())
                        # print >>sys.stderr,"main: Infohash:",`ds.get_download().get_def().get_infohash()`
                        if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                            self._logger.debug("main: Error: %s", repr(ds.get_error()))

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

#            # Update bandwidth statistics in the Barter Community
#            if not self.barter_community:
#                self.barter_community = self.dispersy.callback.call(self._dispersy_get_barter_community)
#
#            if self.barter_community and not isinstance(self.barter_community, HardKilledCommunity):
#                if self.barter_community.has_been_killed:
#                    # set BARTER_COMMUNITY to None.  next state callback we will again get the
#                    # community resulting in the HardKilledCommunity instead
#                    self.barter_community = None
#                else:
#                    if True in self.lastwantpeers:
#                        self.dispersy.callback.register(self.barter_community.download_state_callback, (dslist, True))
#
#                    # only request peer info every 120 intervals
#                    if self.ratestatecallbackcount % 120 == 0:
#                        wantpeers.append(True)

            # Find State of currently playing video
            playds = None
            d = self.videoplayer.get_vod_download()
            for ds in dslist:
                if ds.get_download() == d:
                    playds = ds

            # Apply status displaying from SwarmPlayer
            if playds:
                def do_video():
                    if playds.get_status() == DLSTATUS_HASHCHECKING:
                        progress = progress_consec = playds.get_progress()
                    else:
                        progress = playds.get_vod_prebuffering_progress()
                        progress_consec = playds.get_vod_prebuffering_progress_consec()
                    self.videoplayer.set_player_status_and_progress(progress, progress_consec, \
                                                                    playds.get_pieces_complete() if playds.get_progress() < 1.0 else [True], \
                                                                    playds.get_status() == DLSTATUS_STOPPED_ON_ERROR)
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
                            if self.utility.read_config('swiftreseed') == 1 and cdef.get_def_type() == 'torrent' and not download.get_selected_files():
                                self.sesscb_reseed_via_swift(download)

                            doCheckpoint = True

            self.prevActiveDownloads = newActiveDownloads
            if doCheckpoint:
                self.utility.session.checkpoint()

            self.seedingmanager.apply_seeding_policy(no_collected_list)

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
                            self._logger.debug("tribler: SW %s %s %s", dlstatus_strings[state], safename, ds.get_current_speed(UPLOAD))
                        else:
                            self._logger.debug("tribler: BT %s %s %s", dlstatus_strings[state], cdef.get_name(), ds.get_current_speed(UPLOAD))

        except:
            print_exc()

        self.lastwantpeers = wantpeers
        return (1.0, wantpeers)

    def loadSessionCheckpoint(self):
        # Niels: first remove all "swift" torrent collect checkpoints
        dir = self.utility.session.get_downloads_pstate_dir()
        coldir = os.path.basename(os.path.abspath(self.utility.session.get_torrent_collecting_dir()))

        filelist = os.listdir(dir)
        if any([filename.endswith('.pickle') for filename in filelist]):
            convertDownloadCheckpoints(dir)
            filelist = os.listdir(dir)

        filelist = [os.path.join(dir, filename) for filename in filelist if filename.endswith('.state')]

        for file in filelist:
            try:
                pstate = self.utility.session.lm.load_download_pstate(file)

                saveas = pstate.get('downloadconfig', 'saveas')
                if saveas:
                    destdir = os.path.basename(saveas)
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
            self._logger.info("main: Checkpointing Session")
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

            from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent

            if self.frame.torrentdetailspanel.torrent and self.frame.torrentdetailspanel.torrent.infohash in infohashes:
                # If an updated torrent is being shown in the detailspanel, make sure the information gets refreshed.
                t = self.frame.torrentdetailspanel.torrent
                torrent = t.torrent if isinstance(t, CollectedTorrent) else t
                self.frame.torrentdetailspanel.setTorrent(torrent)

            if self.frame.librarydetailspanel.torrent and self.frame.librarydetailspanel.torrent.infohash in infohashes:
                t = self.frame.librarydetailspanel.torrent
                torrent = t.torrent if isinstance(t, CollectedTorrent) else t
                self.frame.librarydetailspanel.setTorrent(torrent)

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
        self._logger.info(repr(filename))
        target = FileDropTarget(self.frame)
        target.OnDropFiles(None, None, [filename])

    def OnExit(self):
        self._logger.info("main: ONEXIT")
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
            self.webUI.delInstance()
        if self.guiserver:
            self.guiserver.shutdown(True)
            self.guiserver.delInstance()
        if self.videoplayer:
            self.videoplayer.shutdown()
            self.videoplayer.delInstance()

        delete_status_holders()

        if self.frame:
            self.frame.Destroy()
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
                    self._logger.info("main: ONEXIT NOT Waiting for Session to shutdown, took too long")
                    break

                self._logger.info("main: ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds", waittime - diff)
                sleep(3)
            self._logger.info("main: ONEXIT Session is shutdown")

            try:
                self._logger.info("main: ONEXIT cleaning database")
                peerdb = self.utility.session.open_dbhandler(NTFY_PEERS)
                peerdb._db.clean_db(randint(0, 24) == 0, exiting=True)
            except:
                print_exc()

            self._logger.info("main: ONEXIT deleting instances")

        Session.del_instance()
        GUIUtility.delInstance()
        GUIDBProducer.delInstance()
        DefaultDownloadStartupConfig.delInstance()
        GuiImageManager.delInstance()

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        return 0

    def db_exception_handler(self, e):
        self._logger.debug("main: Database Exception handler called %s value %s #", e, e.args)
        try:
            if e.args[1] == "DB object has been closed":
                return  # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return  # don't repeat same error
        except:
            self._logger.error("main: db_exception_handler error %s %s", e, type(e))
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

        self._logger.info("main: Another instance called us with cmd %s", cmd)
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
            metadir = self.sconfig.get_swift_meta_dir()
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
        single_instance_checker = SingleInstanceChecker("tribler")

        installdir = ABCApp.determine_install_dir()

        if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
            statedir = SessionStartupConfig().get_state_dir() or Session.get_default_state_dir()

            # Send  torrent info to abc single instance
            if params[0] != "":
                torrentfilename = params[0]
                i2ic = Instance2InstanceClient(Utility(installdir, statedir).read_config('i2ilistenport'), 'START', torrentfilename)

            logger.info("Client shutting down. Detected another instance.")
        else:

            if sys.platform == 'linux2':
                try:
                    import ctypes
                    x11 = ctypes.cdll.LoadLibrary('libX11.so')
                    x11.XInitThreads()
                except OSError as e:
                    logger.debug("Failed to call XInitThreads '%s'", str(e))
                except:
                    logger.exception('Failed to call xInitThreads')

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

        logger.info("Client shutting down. Sleeping for a few seconds to allow other threads to finish")
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
