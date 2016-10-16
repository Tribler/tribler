#!/usr/bin/python


# Description : Tribler main Python script.
#               This script starts the Tribler session and boots the GUI.
#
#
#
# see LICENSE.txt for license information
#
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Main.Dialogs.NewVersionDialog import NewVersionDialog

try:
    import prctl
except ImportError as e:
    pass

# Make sure the in thread reactor is installed.
from Tribler.Core.Utilities.twisted_thread import reactor

# importmagic: manage

import logging
import os
import sys
import traceback
from collections import defaultdict
from random import randint
from traceback import print_exc

import wx
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread
from twisted.python.threadable import isInIOThread

from Tribler.Core.DownloadConfig import get_default_dest_dir, get_default_dscfg_filename, DefaultDownloadStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.osutils import get_free_space, get_home_dir
from Tribler.Core.simpledefs import (DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR, DOWNLOAD, NTFY_ACTIVITIES, NTFY_CHANNELCAST,
                                     NTFY_COMMENTS, NTFY_CREATE, NTFY_DELETE, NTFY_FINISHED, NTFY_INSERT,
                                     NTFY_MAGNET_CLOSE, NTFY_MAGNET_GOT_PEERS, NTFY_MAGNET_STARTED, NTFY_MARKINGS,
                                     NTFY_MODERATIONS, NTFY_MODIFICATIONS, NTFY_MODIFIED, NTFY_MYPREFERENCES,
                                     NTFY_PLAYLISTS, NTFY_REACHABLE, NTFY_STARTED, NTFY_STATE, NTFY_TORRENTS,
                                     NTFY_UPDATE, NTFY_VOTECAST, UPLOAD, dlstatus_strings, NTFY_STARTUP_TICK,
                                     NTFY_CLOSE_TICK, NTFY_UPGRADER, NTFY_WATCH_FOLDER_CORRUPT_TORRENT,
                                     NTFY_NEW_VERSION)
from Tribler.Core.version import commit_id, version_id
from Tribler.Main.Dialogs.FeedbackWindow import FeedbackWindow
from Tribler.Main.Utility.GuiDBHandler import GUIDBProducer, startWorker
from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Main.Utility.utility import Utility, get_download_upload_speed
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.MainFrame import MainFrame
from Tribler.Main.vwxGUI.TriblerApp import TriblerApp
from Tribler.Main.vwxGUI.TriblerUpgradeDialog import TriblerUpgradeDialog
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import attach_profiler, blockingCallFromThread

logger = logging.getLogger(__name__)

# Boudewijn: keep this import BELOW the imports from Tribler.xxx.* as
# one of those modules imports time as a module.
from time import time, sleep

SESSION_CHECKPOINT_INTERVAL = 900.0  # 15 minutes
FREE_SPACE_CHECK_INTERVAL = 300.0

ALLOW_MULTIPLE = os.environ.get("TRIBLER_ALLOW_MULTIPLE", "False").lower() == "true"

#
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
#


class ABCApp(TaskManager):

    def __init__(self, params, installdir, autoload_discovery=True,
                 use_torrent_search=True, use_channel_search=True):
        super(ABCApp, self).__init__()
        assert not isInIOThread(), "isInIOThread() seems to not be working correctly"
        self._logger = logging.getLogger(self.__class__.__name__)

        self.params = params
        self.installdir = installdir

        self.state_dir = None
        self.error = None
        self.last_update = 0
        self.ready = False
        self.done = False
        self.frame = None
        self.upgrader = None
        self.i2i_server = None

        # DISPERSY will be set when available
        self.dispersy = None
        self.tunnel_community = None

        self.webUI = None
        self.utility = None

        # Stage 1 start
        session = self.InitStage1(installdir, autoload_discovery=autoload_discovery,
                                  use_torrent_search=use_torrent_search, use_channel_search=use_channel_search)

        try:
            self._logger.info('Client Starting Up.')
            self._logger.info("Tribler is using %s as working directory", self.installdir)

            # Stage 2: show the splash window and start the session

            self.utility = Utility(self.installdir, session.get_state_dir())

            if self.utility.read_config(u'saveas', u'downloadconfig'):
                DefaultDownloadStartupConfig.getInstance().set_dest_dir(self.utility.read_config(u'saveas', u'downloadconfig'))

            self.utility.set_app(self)
            self.utility.set_session(session)
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params, self)
            GUIDBProducer.getInstance()

            # Broadcast that the initialisation is starting for the splash gauge and those who are interested
            self.utility.session.notifier.notify(NTFY_STARTUP_TICK, NTFY_CREATE, None, None)

            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_INSERT, None, 'Starting API')
            wx.Yield()

            self._logger.info('Tribler Version: %s Build: %s', version_id, commit_id)

            version_info = self.utility.read_config('version_info')
            if version_info.get('version_id', None) != version_id:
                # First run of a different version
                version_info['first_run'] = int(time())
                version_info['version_id'] = version_id
                self.utility.write_config('version_info', version_info)

            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_INSERT, None, 'Starting session and upgrading database (it may take a while)')
            wx.Yield()

            session.start()
            self.dispersy = session.lm.dispersy
            self.dispersy.attach_progress_handler(self.progressHandler)

            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_INSERT, None, 'Initializing Family Filter')
            wx.Yield()
            cat = session.lm.category

            state = self.utility.read_config('family_filter')
            if state in (1, 0):
                cat.set_family_filter(state == 1)
            else:
                self.utility.write_config('family_filter', 1)
                self.utility.flush_config()

                cat.set_family_filter(True)

            # Create global speed limits
            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_INSERT, None, 'Setting up speed limits')
            wx.Yield()

            # Counter to suppress some event from occurring
            self.ratestatecallbackcount = 0

            maxup = self.utility.read_config('maxuploadrate')
            maxdown = self.utility.read_config('maxdownloadrate')
            # set speed limits using LibtorrentMgr
            session.set_max_upload_speed(maxup)
            session.set_max_download_speed(maxdown)

            # Only allow updates to come in after we defined ratelimiter
            self.prevActiveDownloads = []

            # Schedule task for checkpointing Session, to avoid hash checks after
            # crashes.
            self.register_task("checkpoint_loop", LoopingCall(self.guiservthread_checkpoint_timer))\
                .start(SESSION_CHECKPOINT_INTERVAL, now=False)

            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_INSERT, None, 'GUIUtility register')
            wx.Yield()
            self.guiUtility.register()

            self.frame = MainFrame(self, None, False)
            self.frame.SetIcon(wx.Icon(os.path.join(self.installdir, 'Tribler',
                                                    'Main', 'vwxGUI', 'images',
                                                    'tribler.ico'),
                                       wx.BITMAP_TYPE_ICO))

            # Arno, 2011-06-15: VLC 1.1.10 pops up separate win, don't have two.
            self.frame.videoframe = None

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
                    if hand.GetMimeType() == 'image/x-bmp':
                        bmphand = hand
                        break
                # wx.Image.AddHandler()
                if bmphand is not None:
                    bmphand.SetMimeType('image/bmp')
            except:
                # wx < 2.7 don't like wx.Image.GetHandlers()
                print_exc()

            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_DELETE, None, None)
            wx.Yield()
            self.frame.Show(True)
            self.register_task('free_space_check', LoopingCall(self.guiservthread_free_space_check))\
                .start(FREE_SPACE_CHECK_INTERVAL)

            self.webUI = None
            if self.utility.read_config('use_webui'):
                try:
                    from Tribler.Main.webUI.webUI import WebUI
                    self.webUI = WebUI.getInstance(self.guiUtility.library_manager,
                                                   self.guiUtility.torrentsearch_manager,
                                                   self.utility.read_config('webui_port'))
                    self.webUI.start()
                except Exception:
                    print_exc()

            self.emercoin_mgr = None
            try:
                from Tribler.Main.Emercoin.EmercoinMgr import EmercoinMgr
                self.emercoin_mgr = EmercoinMgr(self.utility)
            except Exception:
                print_exc()

            wx.CallAfter(self.PostInit2)

            # 08/02/10 Boudewijn: Working from home though console
            # doesn't allow me to press close.  The statement below
            # gracefully closes Tribler after 120 seconds.
            # wx.CallLater(120*1000, wx.GetApp().Exit)

            self.ready = True

        except Exception as e:
            session.notifier.notify(NTFY_STARTUP_TICK, NTFY_DELETE, None, None)
            self.onError(e)

    def InitStage1(self, installdir, autoload_discovery=True,
                   use_torrent_search=True, use_channel_search=True):
        """ Stage 1 start: pre-start the session to handle upgrade.
        """

        self.gui_image_manager = GuiImageManager.getInstance(installdir)

        # Start Tribler Session
        defaultConfig = SessionStartupConfig()
        state_dir = defaultConfig.get_state_dir()

        # Switch to the state dir so relative paths can be used (IE, in LevelDB store paths)
        if not os.path.exists(state_dir):
            os.makedirs(state_dir)
        os.chdir(state_dir)

        cfgfilename = Session.get_default_config_filename(state_dir)

        self._logger.debug(u"Session config %s", cfgfilename)

        self.sconfig = SessionStartupConfig.load(cfgfilename)
        self.sconfig.set_install_dir(self.installdir)

        if not self.sconfig.get_watch_folder_path():
            default_watch_folder_dir = os.path.join(get_home_dir(), u'Downloads', u'TriblerWatchFolder')
            self.sconfig.set_watch_folder_path(default_watch_folder_dir)
            if not os.path.exists(default_watch_folder_dir):
                os.makedirs(default_watch_folder_dir)

        # TODO(emilon): Do we still want to force limit this? With the new
        # torrent store it should be pretty fast even with more that that.

        # Arno, 2010-03-31: Hard upgrade to 50000 torrents collected
        self.sconfig.set_torrent_collecting_max_torrents(50000)

        dlcfgfilename = get_default_dscfg_filename(self.sconfig.get_state_dir())
        self._logger.debug("main: Download config %s", dlcfgfilename)

        if os.path.exists(dlcfgfilename):
            defaultDLConfig = DefaultDownloadStartupConfig.load(dlcfgfilename)
        else:
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        if not defaultDLConfig.get_dest_dir():
            defaultDLConfig.set_dest_dir(get_default_dest_dir())
        if not os.path.isdir(defaultDLConfig.get_dest_dir()):
            try:
                os.makedirs(defaultDLConfig.get_dest_dir())
            except:
                # Could not create directory, ask user to select a different location
                dlg = wx.DirDialog(None,
                                   "Could not find download directory, please select a new location to store your downloads",
                                   style=wx.DEFAULT_DIALOG_STYLE)
                dlg.SetPath(get_default_dest_dir())
                if dlg.ShowModal() == wx.ID_OK:
                    new_dest_dir = dlg.GetPath()
                    defaultDLConfig.set_dest_dir(new_dest_dir)
                    defaultDLConfig.save(dlcfgfilename)
                    self.sconfig.save(cfgfilename)
                else:
                    # Quit
                    self.onError = lambda e: self._logger.error(
                        "tribler: quitting due to non-existing destination directory")
                    raise Exception()

        if not use_torrent_search:
            self.sconfig.set_enable_torrent_search(False)
        if not use_channel_search:
            self.sconfig.set_enable_channel_search(False)

        session = Session(self.sconfig, autoload_discovery=autoload_discovery)
        session.add_observer(self.show_upgrade_dialog, NTFY_UPGRADER, [NTFY_STARTED])
        self.upgrader = session.prestart()

        while not self.upgrader.is_done:
            wx.SafeYield()
            sleep(0.1)

        return session

    @forceWxThread
    def show_upgrade_dialog(self, subject, changetype, objectID, *args):
        assert wx.Thread_IsMain()

        upgrade_dialog = TriblerUpgradeDialog(self.gui_image_manager, self.upgrader)
        failed = upgrade_dialog.ShowModal()
        upgrade_dialog.Destroy()
        if failed:
            wx.MessageDialog(None, "Failed to upgrade the on disk data.\n\n"
                             "Tribler has backed up the old data and will now start from scratch.\n\n"
                             "Get in contact with the Tribler team if you want to help debugging this issue.\n\n"
                             "Error was: %s" % self.upgrader.current_status,
                             "Data format upgrade failed", wx.OK | wx.CENTRE | wx.ICON_EXCLAMATION).ShowModal()

    def _frame_and_ready(self):
        return self.ready and self.frame and self.frame.ready

    def PostInit2(self):
        self.frame.Raise()
        self.startWithRightView()
        self.set_reputation()

        s = self.utility.session
        s.add_observer(self.sesscb_ntfy_reachable, NTFY_REACHABLE, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_activities, NTFY_ACTIVITIES, [NTFY_INSERT], cache=10)
        s.add_observer(self.sesscb_ntfy_channelupdates,
                       NTFY_CHANNELCAST, [NTFY_INSERT, NTFY_UPDATE, NTFY_CREATE, NTFY_STATE, NTFY_MODIFIED],
                       cache=10)
        s.add_observer(self.sesscb_ntfy_channelupdates, NTFY_VOTECAST, [NTFY_UPDATE], cache=10)
        s.add_observer(self.sesscb_ntfy_myprefupdates, NTFY_MYPREFERENCES, [NTFY_INSERT, NTFY_UPDATE, NTFY_DELETE])
        s.add_observer(self.sesscb_ntfy_torrentupdates, NTFY_TORRENTS, [NTFY_UPDATE, NTFY_INSERT], cache=10)
        s.add_observer(self.sesscb_ntfy_playlistupdates, NTFY_PLAYLISTS, [NTFY_INSERT, NTFY_UPDATE])
        s.add_observer(self.sesscb_ntfy_commentupdates, NTFY_COMMENTS, [NTFY_INSERT, NTFY_DELETE])
        s.add_observer(self.sesscb_ntfy_modificationupdates, NTFY_MODIFICATIONS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_moderationupdats, NTFY_MODERATIONS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_markingupdates, NTFY_MARKINGS, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_torrentfinished, NTFY_TORRENTS, [NTFY_FINISHED])
        s.add_observer(self.sesscb_ntfy_magnet,
                       NTFY_TORRENTS, [NTFY_MAGNET_GOT_PEERS, NTFY_MAGNET_STARTED, NTFY_MAGNET_CLOSE])
        s.add_observer(self.sesscb_ntfy_corrupt_torrent, NTFY_WATCH_FOLDER_CORRUPT_TORRENT, [NTFY_INSERT])
        s.add_observer(self.sesscb_ntfy_newversion, NTFY_NEW_VERSION, [NTFY_INSERT])

        # Check for a new version
        s.lm.version_check_manager.start(24 * 3600)

        # TODO(emilon): Use the LogObserver I already implemented
        # self.dispersy.callback.attach_exception_handler(self.frame.exceptionHandler)

    @forceWxThread
    def sesscb_ntfy_myprefupdates(self, subject, changeType, objectID, *args):
        if self._frame_and_ready():
            if changeType in [NTFY_INSERT, NTFY_UPDATE]:
                if changeType == NTFY_INSERT:
                    if self.frame.searchlist:
                        manager = self.frame.searchlist.GetManager()
                        manager.downloadStarted(objectID)

                    manager = self.frame.selectedchannellist.GetManager()
                    manager.downloadStarted(objectID)

                manager = self.frame.librarylist.GetManager()
                manager.downloadStarted(objectID)
            elif changeType == NTFY_DELETE:
                self.guiUtility.frame.librarylist.RemoveItem(objectID)

                if self.guiUtility.frame.librarylist.IsShownOnScreen() and \
                   self.guiUtility.frame.librarydetailspanel.torrent and \
                   self.guiUtility.frame.librarydetailspanel.torrent.infohash == objectID:
                    self.guiUtility.frame.librarylist.ResetBottomWindow()
                    self.guiUtility.frame.top_bg.ClearButtonHandlers()

                if self.guiUtility.frame.librarylist.list.IsEmpty():
                    self.guiUtility.frame.librarylist.SetData([])

    def progressHandler(self, title, message, maximum):
        from Tribler.Main.Dialogs.ThreadSafeProgressDialog import ThreadSafeProgressDialog
        return ThreadSafeProgressDialog(title,
                                        message,
                                        maximum,
                                        None,
                                        wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME |
                                        wx.PD_ESTIMATED_TIME | wx.PD_REMAINING_TIME |
                                        wx.PD_AUTO_HIDE)

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
            if not self.frame:
                return

            nr_connections, nr_channel_connections = delayedResult.get()

            # self.frame.SRstatusbar.set_reputation(myRep, total_down, total_up)

            # bitmap is 16px wide, -> but first and last pixel do not add anything.
            percentage = min(1.0, (nr_connections + 1) / 16.0)
            self.frame.SRstatusbar.SetConnections(percentage, nr_connections, nr_channel_connections)

        """ set the reputation in the GUI"""
        if self._frame_and_ready():
            startWorker(do_wx, do_db, uId=u"tribler.set_reputation")
        startWorker(None, self.set_reputation, delay=5.0, workerType="ThreadPool")

    @forceWxThread
    def guiservthread_free_space_check(self):
        free_space = get_free_space(DefaultDownloadStartupConfig.getInstance().get_dest_dir())
        self.frame.SRstatusbar.RefreshFreeSpace(free_space)

        storage_locations = defaultdict(list)
        for download in self.utility.session.get_downloads():
            if download.get_status() == DLSTATUS_DOWNLOADING:
                storage_locations[download.get_dest_dir()].append(download)

        show_message = False
        low_on_space = [
            path for path in storage_locations.keys(
            ) if 0 < get_free_space(
                path) < self.utility.read_config(
                'free_space_threshold')]
        for path in low_on_space:
            for download in storage_locations[path]:
                download.stop()
                show_message = True

        if show_message:
            wx.CallAfter(wx.MessageBox, "Tribler has detected low disk space. Related downloads have been stopped.",
                         "Error")

    def guiservthread_checkpoint_timer(self):
        """ Periodically checkpoint Session """
        self._logger.info("main: Checkpointing Session")
        return deferToThread(self.utility.session.checkpoint)

    @forceWxThread
    def sesscb_ntfy_activities(self, events):
        if self._frame_and_ready():
            for args in events:
                objectID = args[2]
                args = args[3:]

                self.frame.setActivity(objectID, *args)

    @forceWxThread
    def sesscb_ntfy_reachable(self, subject, changeType, objectID, msg):
        if self._frame_and_ready():
            self.frame.SRstatusbar.onReachable()

    @forceWxThread
    def sesscb_ntfy_channelupdates(self, events):
        if self._frame_and_ready():
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
                manager.channelUpdated(
                    objectID,
                    stateChanged=changeType == NTFY_STATE,
                    modified=changeType == NTFY_MODIFIED)

                if changeType == NTFY_CREATE:
                    if self.frame.channellist:
                        self.frame.channellist.SetMyChannelId(objectID)

                self.frame.managechannel.channelUpdated(
                    objectID,
                    created=changeType == NTFY_CREATE,
                    modified=changeType == NTFY_MODIFIED)

    @forceWxThread
    def sesscb_ntfy_torrentupdates(self, events):
        if self._frame_and_ready():
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

                if self.utility.session.get_creditmining_enable():
                    manager = self.frame.creditminingpanel.cmlist.GetManager()
                    manager.torrents_updated(infohashes)

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
        self.guiUtility.Notify(
            "Download Completed", "Torrent '%s' has finished downloading. Now seeding." %
            args[0], icon='seed')

        if self._frame_and_ready():
            infohash = objectID
            torrent = self.guiUtility.torrentsearch_manager.getTorrentByInfohash(infohash)
            # Check if we got the actual torrent as the bandwidth investor
            # downloads aren't going to be there.
            if torrent:
                self.guiUtility.library_manager.addDownloadState(torrent)

    @forceWxThread
    def sesscb_ntfy_newversion(self, subject, changeType, objectID, *args):
        if str(self.utility.read_config('last_reported_version')) == args[0]:
            return

        new_version_dialog = NewVersionDialog(args[0], self.frame, 'new_version_dialog', 'New version available',
                                              title='New version',
                                              msg="Version %s of Tribler is available. "
                                                  "Do you want to visit the website to download the newest version?"
                                                  % args[0])
        new_version_dialog.ShowModal()
        new_version_dialog.Destroy()

    @forceWxThread
    def sesscb_ntfy_magnet(self, subject, changetype, objectID, *args):
        if changetype == NTFY_MAGNET_STARTED:
            self.guiUtility.library_manager.magnet_started(objectID)
        elif changetype == NTFY_MAGNET_GOT_PEERS:
            self.guiUtility.library_manager.magnet_got_peers(objectID, args[0])
        elif changetype == NTFY_MAGNET_CLOSE:
            self.guiUtility.library_manager.magnet_close(objectID)

    @forceWxThread
    def sesscb_ntfy_corrupt_torrent(self, subject, changetype, objectID, *args):
        dlg = wx.MessageDialog(self.frame,
                               "Unable to add corrupt torrent in watch folder to downloads: %s" % args[0],
                               "Corrupt torrent",
                               wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    @forceWxThread
    def sesscb_ntfy_playlistupdates(self, subject, changeType, objectID, *args):
        if self._frame_and_ready():
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
        if self._frame_and_ready():
            self.frame.selectedchannellist.OnCommentCreated(objectID)
            self.frame.playlist.OnCommentCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_modificationupdates(self, subject, changeType, objectID, *args):
        if self._frame_and_ready():
            self.frame.selectedchannellist.OnModificationCreated(objectID)
            self.frame.playlist.OnModificationCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_moderationupdats(self, subject, changeType, objectID, *args):
        if self._frame_and_ready():
            self.frame.selectedchannellist.OnModerationCreated(objectID)
            self.frame.playlist.OnModerationCreated(objectID)

    @forceWxThread
    def sesscb_ntfy_markingupdates(self, subject, changeType, objectID, *args):
        if self._frame_and_ready():
            self.frame.selectedchannellist.OnMarkingCreated(objectID)
            self.frame.playlist.OnModerationCreated(objectID)

    @forceWxThread
    def onError(self, e):
        print_exc()
        _, value, stack = sys.exc_info()
        backtrace = traceback.format_exception(type, value, stack)

        win = FeedbackWindow("Unfortunately, Tribler ran into an internal error")
        win.CreateOutputWindow('')
        for line in backtrace:
            win.write(line)

        win.ShowModal()

    @forceWxThread
    def OnExit(self):
        self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_CREATE, None, None)

        blockingCallFromThread(reactor, self.cancel_all_pending_tasks)

        if self.i2i_server:
            self.i2i_server.stop()

        self._logger.info("main: ONEXIT")
        self.ready = False
        self.done = True

        # write all persistent data to disk
        self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_INSERT, None, 'Write all persistent data to disk')
        wx.Yield()

        if self.webUI:
            self.webUI.stop()
            self.webUI.delInstance()

        if self.frame:
            self.frame.Destroy()
            self.frame = None

        # Don't checkpoint, interferes with current way of saving Preferences,
        # see Tribler/Main/Dialogs/abcoption.py
        if self.utility:
            # Niels: lets add a max waiting time for this session shutdown.
            session_shutdown_start = time()

            # TODO(emilon): probably more notification callbacks should be remmoved
            # here
            s = self.utility.session
            s.remove_observer(self.sesscb_ntfy_newversion)
            s.remove_observer(self.sesscb_ntfy_corrupt_torrent)
            s.remove_observer(self.sesscb_ntfy_magnet)
            s.remove_observer(self.sesscb_ntfy_torrentfinished)
            s.remove_observer(self.sesscb_ntfy_markingupdates)
            s.remove_observer(self.sesscb_ntfy_moderationupdats)
            s.remove_observer(self.sesscb_ntfy_modificationupdates)
            s.remove_observer(self.sesscb_ntfy_commentupdates)
            s.remove_observer(self.sesscb_ntfy_playlistupdates)
            s.remove_observer(self.sesscb_ntfy_torrentupdates)
            s.remove_observer(self.sesscb_ntfy_myprefupdates)
            s.remove_observer(self.sesscb_ntfy_channelupdates)
            s.remove_observer(self.sesscb_ntfy_channelupdates)
            s.remove_observer(self.sesscb_ntfy_activities)
            s.remove_observer(self.sesscb_ntfy_reachable)

            try:
                self._logger.info("ONEXIT cleaning database")
                self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_INSERT, None, 'Cleaning database')
                wx.Yield()
                torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
                torrent_db._db.clean_db(randint(0, 24) == 0, exiting=True)
            except:
                print_exc()

            self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_INSERT, None, 'Shutdown session')
            wx.Yield()
            self.utility.session.shutdown(hacksessconfcheckpoint=False)

            # Arno, 2012-07-12: Shutdown should be quick
            # Niels, 2013-03-21: However, setting it too low will prevent checkpoints from being written to disk
            waittime = 60
            while not self.utility.session.has_shutdown():
                diff = time() - session_shutdown_start
                if diff > waittime:
                    self._logger.info("main: ONEXIT NOT Waiting for Session to shutdown, took too long")
                    break

                self._logger.info(
                    "ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds",
                    waittime - diff)
                sleep(3)
            self._logger.info("ONEXIT Session is shutdown")

        self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_INSERT, None, 'Deleting instances')
        self._logger.debug("ONEXIT deleting instances")

        Session.del_instance()
        GUIDBProducer.delInstance()
        DefaultDownloadStartupConfig.delInstance()
        GuiImageManager.delInstance()

        self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_INSERT, None, 'Exiting now')

        self.utility.session.notifier.notify(NTFY_CLOSE_TICK, NTFY_DELETE, None, None)

        GUIUtility.delInstance()

    def db_exception_handler(self, e):
        self._logger.debug("Database Exception handler called %s value %s #", e, e.args)
        try:
            if e.args[1] == "DB object has been closed":
                return  # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return  # don't repeat same error
        except:
            self._logger.error("db_exception_handler error %s %s", e, type(e))
            print_exc()
            # print_stack()

        self.onError(e)

    def getConfigPath(self):
        return self.utility.getConfigPath()

    def startWithRightView(self):
        if self.params[0] != "":
            self.guiUtility.ShowPage('my_files')


#
#
# Main Program Start Here
#
#
@attach_profiler
def run(params=[""], autoload_discovery=True, use_torrent_search=True, use_channel_search=True):

    from .hacks import patch_crypto_be_discovery
    patch_crypto_be_discovery()

    if len(sys.argv) > 1:
        if sys.platform.startswith("win"):
            from .hacks import get_unicode_sys_argv
            params = get_unicode_sys_argv()[1:]
        else:
            params = sys.argv[1:]
    try:
        # Create single instance semaphore
        process_checker = ProcessChecker()

        installdir = determine_install_dir()

        if not ALLOW_MULTIPLE and process_checker.already_running:
            logger.info("Client shutting down. Detected another instance.")
        else:
            # Launch first abc single instance
            app = wx.GetApp()
            if not app:
                app = TriblerApp(redirect=False)

            abc = ABCApp(params, installdir, autoload_discovery=autoload_discovery,
                         use_torrent_search=use_torrent_search, use_channel_search=use_channel_search)
            app.set_abcapp(abc)
            if abc.frame:
                app.SetTopWindow(abc.frame)
                abc.frame.set_wxapp(app)
                app.MainLoop()

            # since ABCApp is not a wx.App anymore, we need to call OnExit explicitly.
            abc.OnExit()

            # Niels: No code should be present here, only executed after gui closes

        process_checker.remove_lock_file()

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
