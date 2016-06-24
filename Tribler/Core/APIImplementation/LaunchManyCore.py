# Written by Arno Bakker
# Updated by Niels Zeilemaker
# see LICENSE.txt for license information
import binascii
import errno
import logging
import os
import sys
import time as timemod
from glob import iglob
from threading import Event, enumerate as enumerate_threads
from traceback import print_exc
from twisted.internet.defer import Deferred

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.APIImplementation.threadpoolmanager import ThreadPoolManager
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.DownloadConfig import DownloadStartupConfig, DefaultDownloadStartupConfig
from Tribler.Core.Modules.search_manager import SearchManager
from Tribler.Core.Modules.versioncheck_manager import VersionCheckManager
from Tribler.Core.Modules.watch_folder import WatchFolder
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Video.VideoPlayer import VideoPlayer
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.simpledefs import NTFY_DISPERSY, NTFY_STARTED, NTFY_TORRENTS, NTFY_UPDATE, NTFY_TRIBLER
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blockingCallFromThread, blocking_call_on_reactor_thread

try:
    import prctl
except ImportError:
    pass

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK


# Internal classes
#


class TriblerLaunchMany(TaskManager):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        super(TriblerLaunchMany, self).__init__()

        self.initComplete = False
        self.registered = False
        self.dispersy = None

        self._logger = logging.getLogger(self.__class__.__name__)

        self.downloads = {}
        self.upnp_ports = []

        self.session = None
        self.sesslock = None
        self.sessdoneflag = Event()

        self.shutdownstarttime = None

        # modules
        self.threadpool = ThreadPoolManager()
        self.torrent_store = None
        self.metadata_store = None
        self.rtorrent_handler = None
        self.tftp_handler = None
        self.api_manager = None
        self.watch_folder = None
        self.version_check_manager = None

        self.cat = None
        self.peer_db = None
        self.torrent_db = None
        self.mypref_db = None
        self.votecast_db = None
        self.channelcast_db = None

        self.search_manager = None
        self.channel_manager = None

        self.videoplayer = None

        self.mainline_dht = None
        self.ltmgr = None
        self.tracker_manager = None
        self.torrent_checker = None
        self.tunnel_community = None

        self.startup_deferred = Deferred()

    def register(self, session, sesslock):
        if not self.registered:
            self.registered = True

            self.session = session
            self.sesslock = sesslock

            if self.session.get_torrent_store():
                from Tribler.Core.leveldbstore import LevelDbStore
                self.torrent_store = LevelDbStore(self.session.get_torrent_store_dir())

            if self.session.get_enable_metadata():
                from Tribler.Core.leveldbstore import LevelDbStore
                self.metadata_store = LevelDbStore(self.session.get_metadata_store_dir())

            # torrent collecting: RemoteTorrentHandler
            if self.session.get_torrent_collecting():
                from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                self.rtorrent_handler = RemoteTorrentHandler(self.session)

            # TODO(emilon): move this to a megacache component or smth
            if self.session.get_megacache():
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import (PeerDBHandler, TorrentDBHandler,
                                                                       MyPreferenceDBHandler, VoteCastDBHandler,
                                                                       ChannelCastDBHandler)
                from Tribler.Category.Category import Category

                self._logger.debug('tlm: Reading Session state from %s', self.session.get_state_dir())

                self.cat = Category.getInstance()

                # create DBHandlers
                self.peer_db = PeerDBHandler(self.session)
                self.torrent_db = TorrentDBHandler(self.session)
                self.mypref_db = MyPreferenceDBHandler(self.session)
                self.votecast_db = VoteCastDBHandler(self.session)
                self.channelcast_db = ChannelCastDBHandler(self.session)

                # initializes DBHandlers
                self.peer_db.initialize()
                self.torrent_db.initialize()
                self.mypref_db.initialize()
                self.votecast_db.initialize()
                self.channelcast_db.initialize()

                from Tribler.Core.Modules.tracker_manager import TrackerManager
                self.tracker_manager = TrackerManager(self.session)
                self.tracker_manager.initialize()

            if self.session.get_videoplayer():
                self.videoplayer = VideoPlayer(self.session)

            # Dispersy
            self.tftp_handler = None
            if self.session.get_dispersy():
                from Tribler.dispersy.dispersy import Dispersy
                from Tribler.dispersy.endpoint import StandaloneEndpoint

                # set communication endpoint
                endpoint = StandaloneEndpoint(self.session.get_dispersy_port(), ip=self.session.get_ip())

                working_directory = unicode(self.session.get_state_dir())
                self.dispersy = Dispersy(endpoint, working_directory)

                # register TFTP service
                from Tribler.Core.TFTP.handler import TftpHandler
                self.tftp_handler = TftpHandler(self.session, endpoint, "fffffffd".decode('hex'), block_size=1024)
                self.tftp_handler.initialize()

            if self.session.get_enable_torrent_search() or self.session.get_enable_channel_search():
                self.search_manager = SearchManager(self.session)
                self.search_manager.initialize()

        if not self.initComplete:
            self.init()

        self.session.add_observer(self.on_tribler_started, NTFY_TRIBLER, [NTFY_STARTED])
        self.session.notifier.notify(NTFY_TRIBLER, NTFY_STARTED, None)
        return self.startup_deferred

    def on_tribler_started(self, subject, changetype, objectID, *args):
        self.startup_deferred.callback(None)

    def init(self):
        if self.dispersy:
            from Tribler.dispersy.community import HardKilledCommunity

            self._logger.info("lmc: Starting Dispersy...")

            now = timemod.time()
            success = self.dispersy.start(self.session.autoload_discovery)

            diff = timemod.time() - now
            if success:
                self._logger.info("lmc: Dispersy started successfully in %.2f seconds [port: %d]",
                                  diff, self.dispersy.wan_address[1])
            else:
                self._logger.info("lmc: Dispersy failed to start in %.2f seconds", diff)

            self.upnp_ports.append((self.dispersy.wan_address[1], 'UDP'))

            from Tribler.dispersy.crypto import M2CryptoSK
            self.session.dispersy_member = blockingCallFromThread(reactor, self.dispersy.get_member,
                                                                  private_key=self.dispersy.crypto.key_to_bin(M2CryptoSK(filename=self.session.get_permid_keypair_filename())))

            blockingCallFromThread(reactor, self.dispersy.define_auto_load, HardKilledCommunity,
                                   self.session.dispersy_member, load=True)

            if self.session.get_megacache():
                self.dispersy.database.attach_commit_callback(self.session.sqlite_db.commit_now)

            # notify dispersy finished loading
            self.session.notifier.notify(NTFY_DISPERSY, NTFY_STARTED, None)

            @blocking_call_on_reactor_thread
            def load_communities():
                self._logger.info("tribler: Preparing communities...")
                now_time = timemod.time()
                default_kwargs = {'tribler_session': self.session}

                # Search Community
                if self.session.get_enable_torrent_search():
                    from Tribler.community.search.community import SearchCommunity
                    self.dispersy.define_auto_load(SearchCommunity, self.session.dispersy_member, load=True,
                                                   kargs=default_kwargs)

                # AllChannel Community
                if self.session.get_enable_channel_search():
                    from Tribler.community.allchannel.community import AllChannelCommunity
                    self.dispersy.define_auto_load(AllChannelCommunity, self.session.dispersy_member, load=True,
                                                   kargs=default_kwargs)

                # Bartercast Community
                if self.session.get_barter_community_enabled():
                    from Tribler.community.bartercast4.community import BarterCommunity
                    self.dispersy.define_auto_load(BarterCommunity, self.session.dispersy_member, load=True)

                # Channel Community
                if self.session.get_channel_community_enabled():
                    from Tribler.community.channel.community import ChannelCommunity
                    self.dispersy.define_auto_load(ChannelCommunity,
                                                   self.session.dispersy_member, load=True, kargs=default_kwargs)

                # PreviewChannel Community
                if self.session.get_preview_channel_community_enabled():
                    from Tribler.community.channel.preview import PreviewChannelCommunity
                    self.dispersy.define_auto_load(PreviewChannelCommunity,
                                                   self.session.dispersy_member, kargs=default_kwargs)

                if self.session.get_tunnel_community_enabled():
                    tunnel_settings = TunnelSettings(tribler_session=self.session)
                    tunnel_kwargs = {'tribler_session': self.session, 'settings': tunnel_settings}

                    if self.session.get_enable_multichain():
                        # If the multichain is enabled, we use the permanent multichain keypair
                        # for both the multichain and the tunnel community
                        keypair = self.session.multichain_keypair
                        dispersy_member = self.dispersy.get_member(private_key=keypair.key_to_bin())

                        from Tribler.community.multichain.community import MultiChainCommunity
                        self.dispersy.define_auto_load(MultiChainCommunity, dispersy_member, load=True)

                        from Tribler.community.tunnel.hidden_community_multichain import HiddenTunnelCommunityMultichain
                        self.tunnel_community = self.dispersy.define_auto_load(
                            HiddenTunnelCommunityMultichain, dispersy_member, load=True, kargs=tunnel_kwargs)[0]
                    else:
                        keypair = self.dispersy.crypto.generate_key(u"curve25519")
                        dispersy_member = self.dispersy.get_member(private_key=self.dispersy.crypto.key_to_bin(keypair))

                        from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
                        self.tunnel_community = self.dispersy.define_auto_load(
                            HiddenTunnelCommunity, dispersy_member, load=True, kargs=tunnel_kwargs)[0]

                self.session.set_anon_proxy_settings(2, ("127.0.0.1",
                                                         self.session.get_tunnel_community_socks5_listen_ports()))

                self._logger.info("tribler: communities are ready in %.2f seconds", timemod.time() - now_time)

            load_communities()

            if self.session.get_enable_channel_search():
                from Tribler.Core.Modules.channel.channel_manager import ChannelManager
                self.channel_manager = ChannelManager(self.session)
                self.channel_manager.initialize()

        from Tribler.Core.DecentralizedTracking import mainlineDHT
        try:
            self.mainline_dht = mainlineDHT.init(('127.0.0.1', self.session.get_mainline_dht_listen_port()),
                                                 self.session.get_state_dir())
            self.upnp_ports.append((self.session.get_mainline_dht_listen_port(), 'UDP'))
        except:
            print_exc()

        if self.session.get_libtorrent():
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session)
            self.ltmgr.initialize()
            for port, protocol in self.upnp_ports:
                self.ltmgr.add_upnp_mapping(port, protocol)

        # add task for tracker checking
        if self.session.get_torrent_checking():
            try:
                from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
                self.torrent_checker = TorrentChecker(self.session)
                self.torrent_checker.initialize()
            except:
                print_exc()

        if self.rtorrent_handler:
            self.rtorrent_handler.initialize()

        if self.api_manager:
            self.api_manager.root_endpoint.start_endpoints()

        if self.session.get_watch_folder_enabled():
            self.watch_folder = WatchFolder(self.session)
            self.watch_folder.start()

        self.version_check_manager = VersionCheckManager(self.session)

        self.initComplete = True

    def add(self, tdef, dscfg, pstate=None, initialdlstatus=None, setupDelay=0, hidden=False):
        """ Called by any thread """
        d = None
        with self.sesslock:
            if not isinstance(tdef, TorrentDefNoMetainfo) and not tdef.is_finalized():
                raise ValueError("TorrentDef not finalized")

            infohash = tdef.get_infohash()

            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException()

            from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
            d = LibtorrentDownloadImpl(self.session, tdef)

            if pstate is None:  # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    self._logger.debug("tlm: add: pstate is %s %s",
                                       pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            setup_deferred = d.setup(dscfg, pstate, initialdlstatus, wrapperDelay=setupDelay)
            setup_deferred.addCallback(self.on_download_wrapper_created)

        if d and not hidden and self.session.get_megacache():
            @forceDBThread
            def write_my_pref():
                torrent_id = self.torrent_db.getTorrentID(infohash)
                data = {'destination_path': d.get_dest_dir()}
                self.mypref_db.addMyPreference(torrent_id, data)

            if isinstance(tdef, TorrentDefNoMetainfo):
                self.torrent_db.addOrGetTorrentID(tdef.get_infohash())
                self.torrent_db.updateTorrent(tdef.get_infohash(), name=tdef.get_name_as_unicode())
                write_my_pref()
            elif self.rtorrent_handler:
                self.rtorrent_handler.save_torrent(tdef, write_my_pref)
            else:
                self.torrent_db.addExternalTorrent(tdef, extra_info={'status': 'good'})
                write_my_pref()

        return d

    def on_download_wrapper_created(self, (d, pstate)):
        """ Called by network thread """
        try:
            if pstate is None:
                # Checkpoint at startup
                (infohash, pstate) = d.network_checkpoint()
                self.save_download_pstate(infohash, pstate)
        except:
            print_exc()

    def remove(self, d, removecontent=False, removestate=True, hidden=False):
        """ Called by any thread """
        with self.sesslock:
            d.stop_remove(removestate=removestate, removecontent=removecontent)
            infohash = d.get_def().get_infohash()
            if infohash in self.downloads:
                del self.downloads[infohash]

        if not hidden:
            self.remove_id(infohash)

    def remove_id(self, infohash):
        @forceDBThread
        def do_db():
            torrent_id = self.torrent_db.getTorrentID(infohash)
            if torrent_id:
                self.mypref_db.deletePreference(torrent_id)

        if self.session.get_megacache():
            do_db()

    def get_downloads(self):
        """ Called by any thread """
        with self.sesslock:
            return self.downloads.values()  # copy, is mutable

    def get_download(self, infohash):
        """ Called by any thread """
        with self.sesslock:
            return self.downloads.get(infohash, None)

    def download_exists(self, infohash):
        with self.sesslock:
            return infohash in self.downloads

    def update_trackers(self, infohash, trackers):
        """ Update the trackers for a download.
        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls.
        """
        dl = self.get_download(infohash)
        old_def = dl.get_def() if dl else None

        if old_def:
            old_trackers = old_def.get_trackers_as_single_tuple()
            new_trackers = list(set(trackers) - set(old_trackers))
            all_trackers = list(old_trackers) + new_trackers

            if new_trackers:
                # Add new trackers to the download
                dl.add_trackers(new_trackers)

                # Create a new TorrentDef
                if isinstance(old_def, TorrentDefNoMetainfo):
                    new_def = TorrentDefNoMetainfo(old_def.get_infohash(), old_def.get_name(), dl.get_magnet_link())
                else:
                    metainfo = old_def.get_metainfo()
                    if len(all_trackers) > 1:
                        metainfo["announce-list"] = [all_trackers]
                    else:
                        metainfo["announce"] = all_trackers[0]
                    new_def = TorrentDef.load_from_dict(metainfo)

                # Set TorrentDef + checkpoint
                dl.set_def(new_def)
                dl.checkpoint()

                if isinstance(old_def, TorrentDefNoMetainfo):
                    @forceDBThread
                    def update_trackers_db(infohash, new_trackers):
                        torrent_id = self.torrent_db.getTorrentID(infohash)
                        if torrent_id is not None:
                            self.torrent_db.addTorrentTrackerMappingInBatch(torrent_id, new_trackers)
                            self.session.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, infohash)

                    if self.session.get_megacache():
                        update_trackers_db(infohash, new_trackers)

                elif not isinstance(old_def, TorrentDefNoMetainfo) and self.rtorrent_handler:
                    # Update collected torrents
                    self.rtorrent_handler.save_torrent(new_def)

    #
    # State retrieval
    #
    def set_download_states_callback(self, usercallback, getpeerlist, when=0.0):
        """ Called by any thread """
        for d in self.downloads.values():
            # Arno, 2012-05-23: At Niels' request to get total transferred
            # stats. Causes MOREINFO message to be sent from swift proc
            # for every initiated dl.
            # 2012-07-31: Turn MOREINFO on/off on demand for efficiency.
            # 2013-04-17: Libtorrent now uses set_moreinfo_stats as well.
            d.set_moreinfo_stats(True in getpeerlist or d.get_def().get_infohash() in getpeerlist)

        network_set_download_states_callback_lambda = lambda: self.network_set_download_states_callback(usercallback)
        self.threadpool.add_task(network_set_download_states_callback_lambda, when)

    def network_set_download_states_callback(self, usercallback):
        """ Called by network thread """
        dslist = []
        for d in self.downloads.values():
            try:
                ds = d.network_get_state(None, False)
                dslist.append(ds)
            except:
                # Niels, 2012-10-18: If Swift connection is crashing, it will raise an exception
                # We're catching it here to continue building the downloadstates
                print_exc()

        # Invoke the usercallback function on a separate thread.
        # After the callback is invoked, the return values will be passed to the
        # returncallback for post-callback processing.
        def session_getstate_usercallback_target():
            when, newgetpeerlist = usercallback(dslist)
            if when > 0.0:
                # reschedule
                self.set_download_states_callback(usercallback, newgetpeerlist, when=when)

        self.threadpool.add_task(session_getstate_usercallback_target)

    #
    # Persistence methods
    #
    def load_checkpoint(self, initialdlstatus=None, initialdlstatus_dict={}):
        """ Called by any thread """

        def do_load_checkpoint(initialdlstatus, initialdlstatus_dict):
            with self.sesslock:
                for i, filename in enumerate(iglob(os.path.join(self.session.get_downloads_pstate_dir(), '*.state'))):
                    self.resume_download(filename, initialdlstatus, initialdlstatus_dict, setupDelay=i * 0.1)

        if self.initComplete:
            do_load_checkpoint(initialdlstatus, initialdlstatus_dict)
        else:
            self.register_task("load_checkpoint", reactor.callLater(1, do_load_checkpoint))

    def load_download_pstate_noexc(self, infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            basename = binascii.hexlify(infohash) + '.state'
            filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)
            if os.path.exists(filename):
                return self.load_download_pstate(filename)
            else:
                self._logger.info("%s not found", basename)

        except Exception:
            self._logger.exception("Exception while loading pstate: %s", infohash)

    def resume_download(self, filename, initialdlstatus=None, initialdlstatus_dict={}, setupDelay=0):
        tdef = dscfg = pstate = None

        try:
            pstate = self.load_download_pstate(filename)

            # SWIFTPROC
            metainfo = pstate.get('state', 'metainfo')
            if 'infohash' in metainfo:
                tdef = TorrentDefNoMetainfo(metainfo['infohash'], metainfo['name'], metainfo.get('url', None))
            else:
                tdef = TorrentDef.load_from_dict(metainfo)

            if pstate.has_option('downloadconfig', 'saveas') and \
                    isinstance(pstate.get('downloadconfig', 'saveas'), tuple):
                pstate.set('downloadconfig', 'saveas', pstate.get('downloadconfig', 'saveas')[-1])

            dscfg = DownloadStartupConfig(pstate)

        except:
            # pstate is invalid or non-existing
            _, file = os.path.split(filename)

            infohash = binascii.unhexlify(file[:-6])

            torrent_data = self.torrent_store.get(infohash)
            if torrent_data:
                tdef = TorrentDef.load_from_memory(torrent_data)

                defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                dscfg = defaultDLConfig.copy()

                if self.mypref_db is not None:
                    dest_dir = self.mypref_db.getMyPrefStatsInfohash(infohash)
                    if dest_dir:
                        if os.path.isdir(dest_dir) or dest_dir == '':
                            dscfg.set_dest_dir(dest_dir)

        self._logger.debug("tlm: load_checkpoint: pstate is %s %s",
                           pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))
        if pstate is None or pstate.get('state', 'engineresumedata') is None:
            self._logger.debug("tlm: load_checkpoint: resumedata None")
        else:
            self._logger.debug("tlm: load_checkpoint: resumedata len %d", len(pstate.get('state', 'engineresumedata')))

        if tdef and dscfg:
            if dscfg.get_dest_dir() != '':  # removed torrent ignoring
                try:
                    if not self.download_exists(tdef.get_infohash()):
                        initialdlstatus = initialdlstatus_dict.get(tdef.get_infohash(), initialdlstatus)
                        self.add(tdef, dscfg, pstate, initialdlstatus, setupDelay=setupDelay)
                    else:
                        self._logger.info("tlm: not resuming checkpoint because download has already been added")

                except Exception as e:
                    self._logger.exception("tlm: load check_point: exception while adding download %s", tdef)
            else:
                self._logger.info("tlm: removing checkpoint %s destdir is %s", filename, dscfg.get_dest_dir())
                os.remove(filename)
        else:
            self._logger.info("tlm: could not resume checkpoint %s %s %s", filename, tdef, dscfg)

    def checkpoint(self, stop=False, checkpoint=True, gracetime=2.0):
        """ Called by any thread, assume sesslock already held """
        # Even if the list of Downloads changes in the mean time this is
        # no problem. For removals, dllist will still hold a pointer to the
        # Download, and additions are no problem (just won't be included
        # in list of states returned via callback.
        #
        dllist = self.downloads.values()
        self._logger.debug("tlm: checkpointing %s stopping %s", len(dllist), stop)

        network_checkpoint_callback_lambda = lambda: self.network_checkpoint_callback(dllist, stop, checkpoint,
                                                                                      gracetime)
        self.threadpool.add_task(network_checkpoint_callback_lambda, 0.0)

    def network_checkpoint_callback(self, dllist, stop, checkpoint, gracetime):
        """ Called by network thread """
        if checkpoint:
            for d in dllist:
                try:
                    # Tell all downloads to stop, and save their persistent state
                    # in a infohash -> pstate dict which is then passed to the user
                    # for storage.
                    #
                    if stop:
                        (infohash, pstate) = d.network_stop(False, False)
                    else:
                        (infohash, pstate) = d.network_checkpoint()

                    self._logger.debug("tlm: network checkpointing: %s %s", d.get_def().get_name(), pstate)

                    self.save_download_pstate(infohash, pstate)

                except Exception as e:
                    self._logger.exception("Exception while checkpointing: %s", d.get_def().get_name())

        if stop:
            # Some grace time for early shutdown tasks
            if self.shutdownstarttime is not None:
                now = timemod.time()
                diff = now - self.shutdownstarttime
                if diff < gracetime:
                    self._logger.info("tlm: shutdown: delaying for early shutdown tasks %s", gracetime - diff)
                    delay = gracetime - diff
                    network_shutdown_callback_lambda = lambda: self.network_shutdown()
                    self.threadpool.add_task(network_shutdown_callback_lambda, delay)
                    return

            self.network_shutdown()

    def remove_pstate(self, infohash):
        def do_remove():
            if not self.download_exists(infohash):
                dlpstatedir = self.session.get_downloads_pstate_dir()

                # Remove checkpoint
                hexinfohash = binascii.hexlify(infohash)
                try:
                    basename = hexinfohash + '.state'
                    filename = os.path.join(dlpstatedir, basename)
                    self._logger.debug("remove pstate: removing dlcheckpoint entry %s", filename)
                    if os.access(filename, os.F_OK):
                        os.remove(filename)
                except:
                    # Show must go on
                    self._logger.exception("Could not remove state")
            else:
                self._logger.warning("remove pstate: download is back, restarted? Canceling removal! %s",
                                      repr(infohash))
        self.threadpool.add_task(do_remove)

    @inlineCallbacks
    def early_shutdown(self):
        """ Called as soon as Session shutdown is initiated. Used to start
        shutdown tasks that takes some time and that can run in parallel
        to checkpointing, etc.
        :returns a Deferred that will fire once all dependencies acknowledge they have shutdown.
        """
        self._logger.info("tlm: early_shutdown")

        self.cancel_all_pending_tasks()

        # Note: sesslock not held
        self.shutdownstarttime = timemod.time()
        if self.torrent_checker:
            yield self.torrent_checker.shutdown()
            self.torrent_checker = None
        if self.channel_manager:
            yield self.channel_manager.shutdown()
            self.channel_manager = None
        if self.search_manager:
            yield self.search_manager.shutdown()
            self.search_manager = None
        if self.rtorrent_handler:
            yield self.rtorrent_handler.shutdown()
            self.rtorrent_handler = None
        if self.videoplayer:
            yield self.videoplayer.shutdown()
            self.videoplayer = None

        self.version_check_manager.stop()
        self.version_check_manager = None

        if self.tracker_manager:
            yield self.tracker_manager.shutdown()
            self.tracker_manager = None

        if self.dispersy:
            self._logger.info("lmc: Shutting down Dispersy...")
            now = timemod.time()
            try:
                success = self.dispersy.stop()
            except:
                print_exc()
                success = False

            diff = timemod.time() - now
            if success:
                self._logger.info("lmc: Dispersy successfully shutdown in %.2f seconds", diff)
            else:
                self._logger.info("lmc: Dispersy failed to shutdown in %.2f seconds", diff)

        if self.metadata_store is not None:
            yield self.metadata_store.close()
            self.metadata_store = None

        if self.tftp_handler:
            yield self.tftp_handler.shutdown()
            self.tftp_handler = None

        if self.session.get_megacache():
            yield self.channelcast_db.close()
            yield self.votecast_db.close()
            yield self.mypref_db.close()
            yield self.torrent_db.close()
            yield self.peer_db.close()

            self.channelcast_db = None
            self.votecast_db = None
            self.mypref_db = None
            self.torrent_db = None
            self.peer_db = None

        if self.mainline_dht:
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            yield mainlineDHT.deinit(self.mainline_dht)
            self.mainline_dht = None

        if self.torrent_store is not None:
            yield self.torrent_store.close()
            self.torrent_store = None

        if self.api_manager is not None:
            yield self.api_manager.stop()
            self.api_manager = None

        if self.watch_folder is not None:
            yield self.watch_folder.stop()
            self.watch_folder = None

    def network_shutdown(self):
        try:
            self._logger.info("tlm: network_shutdown")

            ts = enumerate_threads()
            self._logger.info("tlm: Number of threads still running %d", len(ts))
            for t in ts:
                self._logger.info("tlm: Thread still running=%s, daemon=%s, instance=%s", t.getName(), t.isDaemon(), t)
        except:
            print_exc()

        # Stop network thread
        self.sessdoneflag.set()

        # Shutdown libtorrent session after checkpoints have been made
        if self.ltmgr:
            self.ltmgr.shutdown()
            self.ltmgr = None

        if self.threadpool:
            self.threadpool.cancel_all_pending_tasks()
            self.threadpool = None

    def save_download_pstate(self, infohash, pstate):
        """ Called by network thread """

        self.downloads[infohash].pstate_for_restart = pstate

        self.register_task("save_pstate %f" % timemod.clock(),
                           self.downloads[infohash].save_resume_data())

    def load_download_pstate(self, filename):
        """ Called by any thread """
        pstate = CallbackConfigParser()
        pstate.read_file(filename)
        return pstate

    # Events from core meant for API user
    #
    def sessconfig_changed_callback(self, section, name, new_value, old_value):
        value_changed = new_value != old_value
        if section == 'libtorrent' and name == 'utp':
            if self.ltmgr and value_changed:
                self.ltmgr.set_utp(new_value)
        elif section == 'libtorrent' and name == 'lt_proxyauth':
            if self.ltmgr:
                self.ltmgr.set_proxy_settings(None, *self.session.get_libtorrent_proxy_settings())
        # Return True/False, depending on whether or not the config value can be changed at runtime.
        elif (section == 'general' and name in ['nickname', 'mugshot', 'videoanalyserpath']) or \
             (section == 'libtorrent' and name in ['lt_proxytype', 'lt_proxyserver',
                                                   'anon_proxyserver', 'anon_proxytype', 'anon_proxyauth',
                                                   'anon_listen_port']) or \
             (section == 'torrent_collecting' and name in ['stop_collecting_threshold']) or \
             (section == 'watch_folder') or \
             (section == 'tunnel_community' and name in ['socks5_listen_port']):
            return True
        else:
            return False
        return True
