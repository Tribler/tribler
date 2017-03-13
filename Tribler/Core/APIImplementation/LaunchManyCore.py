import binascii
import logging
import os
import time as timemod
from glob import iglob
from threading import Event, enumerate as enumerate_threads
from traceback import print_exc

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks, DeferredList
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread
from twisted.python.threadable import isInIOThread

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.DownloadConfig import DownloadStartupConfig, DefaultDownloadStartupConfig
from Tribler.Core.Modules.search_manager import SearchManager
from Tribler.Core.Modules.versioncheck_manager import VersionCheckManager
from Tribler.Core.Modules.watch_folder import WatchFolder
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Video.VideoServer import VideoServer
from Tribler.Core.defaults import tribler_defaults
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.simpledefs import (NTFY_DISPERSY, NTFY_STARTED, NTFY_TORRENTS, NTFY_UPDATE, NTFY_TRIBLER,
                                     NTFY_FINISHED, DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED_ON_ERROR, NTFY_ERROR,
                                     DLSTATUS_SEEDING, NTFY_TORRENT)
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blockingCallFromThread, blocking_call_on_reactor_thread

try:
    import prctl
except ImportError:
    pass


# Internal classes
#


class TriblerLaunchMany(TaskManager):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        super(TriblerLaunchMany, self).__init__()

        self.initComplete = False
        self.registered = False
        self.dispersy = None
        self.state_cb_count = 0
        self.previous_active_downloads = []
        self.download_states_lc = None
        self.get_peer_list = []

        self._logger = logging.getLogger(self.__class__.__name__)

        self.downloads = {}
        self.upnp_ports = []

        self.session = None
        self.sesslock = None
        self.sessdoneflag = Event()

        self.shutdownstarttime = None

        # modules
        self.torrent_store = None
        self.metadata_store = None
        self.rtorrent_handler = None
        self.tftp_handler = None
        self.api_manager = None
        self.watch_folder = None
        self.version_check_manager = None

        self.category = None
        self.peer_db = None
        self.torrent_db = None
        self.mypref_db = None
        self.votecast_db = None
        self.channelcast_db = None

        self.search_manager = None
        self.channel_manager = None

        self.video_server = None

        self.mainline_dht = None
        self.ltmgr = None
        self.tracker_manager = None
        self.torrent_checker = None
        self.tunnel_community = None

        self.startup_deferred = Deferred()

        self.boosting_manager = None

    def register(self, session, sesslock):
        assert isInIOThread()
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
                from Tribler.Core.Category.Category import Category

                self._logger.debug('tlm: Reading Session state from %s', self.session.get_state_dir())

                self.category = Category()

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

            if self.session.get_videoserver_enabled():
                self.video_server = VideoServer(self.session.get_videoserver_port(), self.session)
                self.video_server.start()

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
        reactor.callFromThread(self.startup_deferred.callback, None)

    @blocking_call_on_reactor_thread
    def load_communities(self):
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
                multichain_kwargs = {'tribler_session': self.session}

                # If the multichain is enabled, we use the permanent multichain keypair
                # for both the multichain and the tunnel community
                keypair = self.session.multichain_keypair
                dispersy_member = self.dispersy.get_member(private_key=keypair.key_to_bin())

                from Tribler.community.multichain.community import MultiChainCommunity
                self.dispersy.define_auto_load(MultiChainCommunity,
                                               dispersy_member,
                                               load=True,
                                               kargs=multichain_kwargs)

            else:
                keypair = self.dispersy.crypto.generate_key(u"curve25519")
                dispersy_member = self.dispersy.get_member(private_key=self.dispersy.crypto.key_to_bin(keypair))

            from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
            self.tunnel_community = self.dispersy.define_auto_load(HiddenTunnelCommunity, dispersy_member,
                                                                   load=True, kargs=tunnel_kwargs)[0]

        self.session.set_anon_proxy_settings(2, ("127.0.0.1",
                                                 self.session.get_tunnel_community_socks5_listen_ports()))

        self._logger.info("tribler: communities are ready in %.2f seconds", timemod.time() - now_time)

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

            self.load_communities()

            if self.session.get_enable_channel_search():
                from Tribler.Core.Modules.channel.channel_manager import ChannelManager
                self.channel_manager = ChannelManager(self.session)
                self.channel_manager.initialize()

        if self.session.get_mainline_dht():
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            self.mainline_dht = mainlineDHT.init(('127.0.0.1', self.session.get_mainline_dht_listen_port()),
                                                 self.session.get_state_dir())
            self.upnp_ports.append((self.session.get_mainline_dht_listen_port(), 'UDP'))

        if self.session.get_libtorrent():
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session)
            self.ltmgr.initialize()
            for port, protocol in self.upnp_ports:
                self.ltmgr.add_upnp_mapping(port, protocol)

        # add task for tracker checking
        if self.session.get_torrent_checking():
            self.torrent_checker = TorrentChecker(self.session)
            self.torrent_checker.initialize()

        if self.rtorrent_handler:
            self.rtorrent_handler.initialize()

        if self.api_manager:
            self.api_manager.root_endpoint.start_endpoints()

        if self.session.get_watch_folder_enabled():
            self.watch_folder = WatchFolder(self.session)
            self.watch_folder.start()

        if self.session.get_creditmining_enable():
            from Tribler.Core.CreditMining.BoostingManager import BoostingManager
            self.boosting_manager = BoostingManager(self.session)

        self.version_check_manager = VersionCheckManager(self.session)
        self.session.set_download_states_callback(self.sesscb_states_callback)

        self.initComplete = True

    def add(self, tdef, dscfg, pstate=None, setupDelay=0, hidden=False,
            share_mode=False, checkpoint_disabled=False):
        """ Called by any thread """
        d = None
        with self.sesslock:
            if not isinstance(tdef, TorrentDefNoMetainfo) and not tdef.is_finalized():
                raise ValueError("TorrentDef not finalized")

            infohash = tdef.get_infohash()

            # Create the destination directory if it does not exist yet
            try:
                if not os.path.isdir(dscfg.get_dest_dir()):
                    os.makedirs(dscfg.get_dest_dir())
            except OSError:
                self._logger.error("Unable to create the download destination directory.")

            if dscfg.get_time_added() == 0:
                dscfg.set_time_added(int(timemod.time()))

            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException("This download already exists.")

            from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
            d = LibtorrentDownloadImpl(self.session, tdef)

            if pstate is None:  # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    self._logger.debug("tlm: add: pstate is %s %s",
                                       pstate.get('dlstate', 'status'), pstate.get('dlstate', 'progress'))

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            setup_deferred = d.setup(dscfg, pstate, wrapperDelay=setupDelay,
                                     share_mode=share_mode, checkpoint_disabled=checkpoint_disabled)
            setup_deferred.addCallback(self.on_download_handle_created)

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

    def on_download_handle_created(self, download):
        """
        This method is called when the download handle has been created.
        Immediately checkpoint the download and write the resume data.
        """
        return download.checkpoint()

    def remove(self, d, removecontent=False, removestate=True, hidden=False):
        """ Called by any thread """
        with self.sesslock:
            d.stop_remove(removestate=removestate, removecontent=removecontent)
            infohash = d.get_def().get_infohash()
            if infohash in self.downloads:
                del self.downloads[infohash]

        if not hidden:
            self.remove_id(infohash)

        if self.tunnel_community:
            self.tunnel_community.on_download_removed(d)

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

    def update_download_hops(self, download, new_hops):
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = binascii.hexlify(download.tdef.get_infohash())
        self._logger.info("Updating the amount of hops of download %s", infohash)
        self.session.remove_download(download)

        # copy the old download_config and change the hop count
        dscfg = download.copy()
        dscfg.set_hops(new_hops)

        self.register_task("reschedule_download_%s" % infohash,
                           reactor.callLater(3, self.session.start_download_from_tdef, download.tdef, dscfg))

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
    def stop_download_states_callback(self):
        """
        Stop any download states callback if present.
        """
        if self.is_pending_task_active("download_states_lc"):
            self.cancel_pending_task("download_states_lc")

    def set_download_states_callback(self, usercallback, interval=1.0):
        """
        Set the download state callback. Remove any old callback if it's present.
        """
        self.stop_download_states_callback()
        self._logger.debug("Starting the download state callback with interval %f", interval)
        self.download_states_lc = self.register_task("download_states_lc",
                                                     LoopingCall(self._invoke_states_cb, usercallback))
        self.download_states_lc.start(interval)

    def _invoke_states_cb(self, callback):
        """
        Invoke the download states callback with a list of the download states.
        """
        dslist = []
        for d in self.downloads.values():
            d.set_moreinfo_stats(True in self.get_peer_list or d.get_def().get_infohash() in
                                 self.get_peer_list)
            ds = d.network_get_state(None, False)
            dslist.append(ds)

        def on_cb_done(new_get_peer_list):
            self.get_peer_list = new_get_peer_list

        return deferToThread(callback, dslist).addCallback(on_cb_done)

    def sesscb_states_callback(self, states_list):
        """
        This method is periodically (every second) called with a list of the download states of the active downloads.
        """
        self.state_cb_count += 1

        # Check to see if a download has finished
        new_active_downloads = []
        do_checkpoint = False
        seeding_download_list = []

        for ds in states_list:
            state = ds.get_status()
            download = ds.get_download()
            tdef = download.get_def()
            safename = tdef.get_name_as_unicode()

            if state == DLSTATUS_DOWNLOADING:
                new_active_downloads.append(safename)
            elif state == DLSTATUS_STOPPED_ON_ERROR:
                self._logger.error("Error during download: %s", repr(ds.get_error()))
                self.downloads.get(tdef.get_infohash()).stop()
                self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, tdef.get_infohash(), repr(ds.get_error()))
            elif state == DLSTATUS_SEEDING:
                seeding_download_list.append({u'infohash': tdef.get_infohash(),
                                              u'download': download})

                if safename in self.previous_active_downloads:
                    self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, tdef.get_infohash(), safename)
                    do_checkpoint = True

                elif download.get_hops() == 0 and download.get_safe_seeding():
                    hops = tribler_defaults.get('Tribler', {}).get('default_number_hops', 1)
                    self._logger.info("Moving completed torrent to tunneled session %d for hidden seeding %r",
                                      hops, download)
                    self.session.remove_download(download)

                    # copy the old download_config and change the hop count
                    dscfg = download.copy()
                    dscfg.set_hops(hops)

                    # TODO(emilon): That's a hack to work around the fact that removing a torrent is racy.
                    self.register_task("reschedule_download",
                                       reactor.callLater(5, self.session.start_download_from_tdef, tdef, dscfg))

        self.previous_active_downloads = new_active_downloads
        if do_checkpoint:
            self.session.checkpoint_downloads()

        if self.state_cb_count % 4 == 0 and self.tunnel_community:
            self.tunnel_community.monitor_downloads(states_list)

        return []

    #
    # Persistence methods
    #
    def load_checkpoint(self):
        """ Called by any thread """

        def do_load_checkpoint():
            with self.sesslock:
                for i, filename in enumerate(iglob(os.path.join(self.session.get_downloads_pstate_dir(), '*.state'))):
                    self.resume_download(filename, setupDelay=i * 0.1)

        if self.initComplete:
            do_load_checkpoint()
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

    def resume_download(self, filename, setupDelay=0):
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
                try:
                    tdef = TorrentDef.load_from_memory(torrent_data)
                    defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                    dscfg = defaultDLConfig.copy()

                    if self.mypref_db is not None:
                        dest_dir = self.mypref_db.getMyPrefStatsInfohash(infohash)
                        if dest_dir and os.path.isdir(dest_dir):
                            dscfg.set_dest_dir(dest_dir)
                except ValueError:
                    self._logger.warning("tlm: torrent data invalid")

        if pstate is not None:
            has_resume_data = pstate.get('state', 'engineresumedata') is not None
            self._logger.debug("tlm: load_checkpoint: resumedata %s",
                               'len %s ' % len(pstate.get('state', 'engineresumedata')) if has_resume_data else 'None')

        if tdef and dscfg:
            if dscfg.get_dest_dir() != '':  # removed torrent ignoring
                try:
                    if not self.download_exists(tdef.get_infohash()):
                        self.add(tdef, dscfg, pstate, setupDelay=setupDelay)
                    else:
                        self._logger.info("tlm: not resuming checkpoint because download has already been added")

                except Exception as e:
                    self._logger.exception("tlm: load check_point: exception while adding download %s", tdef)
            else:
                self._logger.info("tlm: removing checkpoint %s destdir is %s", filename, dscfg.get_dest_dir())
                os.remove(filename)
        else:
            self._logger.info("tlm: could not resume checkpoint %s %s %s", filename, tdef, dscfg)

    def checkpoint_downloads(self):
        """
        Checkpoints all running downloads in Tribler.
        Even if the list of Downloads changes in the mean time this is no problem.
        For removals, dllist will still hold a pointer to the download, and additions are no problem
        (just won't be included in list of states returned via callback).
        """
        downloads = self.downloads.values()
        deferred_list = []
        self._logger.debug("tlm: checkpointing %s downloads", len(downloads))
        for download in downloads:
            deferred_list.append(download.checkpoint())

        return DeferredList(deferred_list)

    def shutdown_downloads(self):
        """
        Shutdown all downloads in Tribler.
        """
        for download in self.downloads.values():
            download.stop()

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
        reactor.callFromThread(do_remove)

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
        if self.boosting_manager:
            yield self.boosting_manager.shutdown()
        self.boosting_manager = None

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

        if self.video_server:
            yield self.video_server.shutdown_server()
        self.video_server = None

        if self.version_check_manager:
            self.version_check_manager.stop()
        self.version_check_manager = None

        if self.tracker_manager:
            yield self.tracker_manager.shutdown()
        self.tracker_manager = None

        if self.dispersy:
            self._logger.info("lmc: Shutting down Dispersy...")
            now = timemod.time()
            try:
                success = yield self.dispersy.stop()
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

        if self.tftp_handler is not None:
            yield self.tftp_handler.shutdown()
        self.tftp_handler = None

        if self.channelcast_db is not None:
            yield self.channelcast_db.close()
        self.channelcast_db = None

        if self.votecast_db is not None:
            yield self.votecast_db.close()
        self.votecast_db = None

        if self.mypref_db is not None:
            yield self.mypref_db.close()
        self.mypref_db = None

        if self.torrent_db is not None:
            yield self.torrent_db.close()
        self.torrent_db = None

        if self.peer_db is not None:
            yield self.peer_db.close()
        self.peer_db = None

        if self.mainline_dht is not None:
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
        if self.ltmgr is not None:
            self.ltmgr.shutdown()
            self.ltmgr = None

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
             (section == 'tunnel_community' and name in ['socks5_listen_port']) or \
             (section == 'credit_mining' and name in ['max_torrents_per_source', 'max_torrents_active',
                                                      'source_interval', 'swarm_interval', 'boosting_sources',
                                                      'boosting_enabled', 'boosting_disabled', 'archive_sources']):
            return True
        else:
            return False
        return True
