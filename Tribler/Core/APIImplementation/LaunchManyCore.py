"""
LaunchManyCore

Author(s): Arno Bakker, Niels Zeilemaker
"""
import binascii
import logging
import os
import sys
import time as timemod
from glob import iglob
from threading import Event, enumerate as enumerate_threads
from traceback import print_exc

from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.DecentralizedTracking.dht_provider import MainlineDHTProvider
from Tribler.Core.DownloadConfig import DownloadStartupConfig, DefaultDownloadStartupConfig
from Tribler.Core.Modules.resource_monitor import ResourceMonitor
from Tribler.Core.Modules.search_manager import SearchManager
from Tribler.Core.Modules.versioncheck_manager import VersionCheckManager
from Tribler.Core.Modules.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.Core.Modules.wallet.tc_wallet import TrustchainWallet
from Tribler.Core.Modules.watch_folder import WatchFolder
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Video.VideoServer import VideoServer
from Tribler.Core.simpledefs import (NTFY_DISPERSY, NTFY_STARTED, NTFY_TORRENTS, NTFY_UPDATE, NTFY_TRIBLER,
                                     NTFY_FINISHED, DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED_ON_ERROR, NTFY_ERROR,
                                     DLSTATUS_SEEDING, NTFY_TORRENT, STATE_STARTING_DISPERSY, STATE_LOADING_COMMUNITIES,
                                     STATE_INITIALIZE_CHANNEL_MGR, STATE_START_MAINLINE_DHT, STATE_START_LIBTORRENT,
                                     STATE_START_TORRENT_CHECKER, STATE_START_REMOTE_TORRENT_HANDLER,
                                     STATE_START_API_ENDPOINTS, STATE_START_WATCH_FOLDER, STATE_START_CREDIT_MINING)
from Tribler.pyipv8.ipv8.keyvault.private.m2crypto import M2CryptoSK
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.peerdiscovery.churn import RandomChurn
from Tribler.pyipv8.ipv8.peerdiscovery.deprecated.discovery import DiscoveryCommunity
from Tribler.pyipv8.ipv8.peerdiscovery.discovery import EdgeWalk, RandomWalk
from Tribler.pyipv8.ipv8.taskmanager import TaskManager
from Tribler.pyipv8.ipv8.util import blockingCallFromThread, blocking_call_on_reactor_thread
from Tribler.pyipv8.ipv8_service import IPv8
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks, DeferredList, succeed
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread
from twisted.python.threadable import isInIOThread


class TriblerLaunchMany(TaskManager):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        super(TriblerLaunchMany, self).__init__()

        self.initComplete = False
        self.registered = False
        self.dispersy = None
        self.ipv8 = None
        self.state_cb_count = 0
        self.previous_active_downloads = []
        self.download_states_lc = None
        self.get_peer_list = []

        self._logger = logging.getLogger(self.__class__.__name__)

        self.downloads = {}
        self.upnp_ports = []

        self.session = None
        self.session_lock = None
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
        self.resource_monitor = None

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
        self.trustchain_community = None
        self.wallets = {}
        self.popularity_community = None

        self.startup_deferred = Deferred()

        self.credit_mining_manager = None
        self.market_community = None
        self.dht_community = None

    def register(self, session, session_lock):
        assert isInIOThread()
        if not self.registered:
            self.registered = True

            self.session = session
            self.session_lock = session_lock

            # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
            # certificates provided by the system trust store.
            if sys.platform == 'darwin':
                os.environ['SSL_CERT_FILE'] = os.path.join(get_lib_path(), 'root_certs_mac.pem')

            if self.session.config.get_torrent_store_enabled():
                from Tribler.Core.leveldbstore import LevelDbStore
                self.torrent_store = LevelDbStore(self.session.config.get_torrent_store_dir())
                if not self.torrent_store.get_db():
                    raise RuntimeError("Torrent store (leveldb) is None which should not normally happen")

            if self.session.config.get_metadata_enabled():
                from Tribler.Core.leveldbstore import LevelDbStore
                self.metadata_store = LevelDbStore(self.session.config.get_metadata_store_dir())
                if not self.metadata_store.get_db():
                    raise RuntimeError("Metadata store (leveldb) is None which should not normally happen")

            # torrent collecting: RemoteTorrentHandler
            if self.session.config.get_torrent_collecting_enabled():
                from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                self.rtorrent_handler = RemoteTorrentHandler(self.session)

            # TODO(emilon): move this to a megacache component or smth
            if self.session.config.get_megacache_enabled():
                from Tribler.Core.CacheDB.SqliteCacheDBHandler import (PeerDBHandler, TorrentDBHandler,
                                                                       MyPreferenceDBHandler, VoteCastDBHandler,
                                                                       ChannelCastDBHandler)
                from Tribler.Core.Category.Category import Category

                self._logger.debug('tlm: Reading Session state from %s', self.session.config.get_state_dir())

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

            if self.session.config.get_video_server_enabled():
                self.video_server = VideoServer(self.session.config.get_video_server_port(), self.session)
                self.video_server.start()

            # IPv8
            if self.session.config.get_ipv8_enabled():
                from Tribler.pyipv8.ipv8.configuration import get_default_configuration
                ipv8_config = get_default_configuration()
                ipv8_config['port'] = self.session.config.get_dispersy_port()
                ipv8_config['address'] = self.session.config.get_ipv8_address()
                ipv8_config['overlays'] = []
                ipv8_config['keys'] = []  # We load the keys ourselves

                if self.session.config.get_ipv8_bootstrap_override():
                    import Tribler.pyipv8.ipv8.deprecated.community as community_file
                    community_file._DEFAULT_ADDRESSES = [self.session.config.get_ipv8_bootstrap_override()]
                    community_file._DNS_ADDRESSES = []

                self.ipv8 = IPv8(ipv8_config)

                self.session.config.set_anon_proxy_settings(2, ("127.0.0.1",
                                                                self.session.
                                                                config.get_tunnel_community_socks5_listen_ports()))
            # Dispersy
            self.tftp_handler = None
            if self.session.config.get_dispersy_enabled():
                from Tribler.dispersy.dispersy import Dispersy
                from Tribler.dispersy.endpoint import MIMEndpoint
                from Tribler.dispersy.endpoint import IPv8toDispersyAdapter

                # set communication endpoint
                if self.session.config.get_ipv8_enabled():
                    dispersy_endpoint = IPv8toDispersyAdapter(self.ipv8.endpoint)
                else:
                    dispersy_endpoint = MIMEndpoint(self.session.config.get_dispersy_port())

                working_directory = unicode(self.session.config.get_state_dir())
                self.dispersy = Dispersy(dispersy_endpoint, working_directory)
                self.dispersy.statistics.enable_debug_statistics(False)

                # register TFTP service
                from Tribler.Core.TFTP.handler import TftpHandler
                self.tftp_handler = TftpHandler(self.session, dispersy_endpoint, "fffffffd".decode('hex'),
                                                block_size=1024)
                self.tftp_handler.initialize()

            # Torrent search
            if self.session.config.get_torrent_search_enabled() or self.session.config.get_channel_search_enabled():
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
    def load_ipv8_overlays(self):
        # Discovery Community
        with open(self.session.config.get_permid_keypair_filename(), 'r') as key_file:
            content = key_file.read()
        content = content[31:-30].replace('\n', '').decode("BASE64")
        peer = Peer(M2CryptoSK(keystring=content))
        discovery_community = DiscoveryCommunity(peer, self.ipv8.endpoint, self.ipv8.network)
        discovery_community.resolve_dns_bootstrap_addresses()
        self.ipv8.overlays.append(discovery_community)
        self.ipv8.strategies.append((RandomChurn(discovery_community), -1))

        if not self.session.config.get_dispersy_enabled():
            self.ipv8.strategies.append((RandomWalk(discovery_community), 20))

        if self.session.config.get_testnet():
            peer = Peer(self.session.trustchain_keypair)
        else:
            peer = Peer(self.session.trustchain_testnet_keypair)

        # TrustChain Community
        if self.session.config.get_trustchain_enabled():
            from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity, \
                TrustChainTestnetCommunity

            community_cls = TrustChainTestnetCommunity if self.session.config.get_testnet() else TrustChainCommunity
            self.trustchain_community = community_cls(peer, self.ipv8.endpoint,
                                                      self.ipv8.network,
                                                      working_directory=self.session.config.get_state_dir())
            self.ipv8.overlays.append(self.trustchain_community)
            self.ipv8.strategies.append((EdgeWalk(self.trustchain_community), 20))

            tc_wallet = TrustchainWallet(self.trustchain_community)
            self.wallets[tc_wallet.get_identifier()] = tc_wallet

        # DHT Community
        if self.session.config.get_dht_enabled():
            from Tribler.pyipv8.ipv8.dht.discovery import DHTDiscoveryCommunity

            dht_peer = Peer(self.session.trustchain_keypair)
            self.dht_community = DHTDiscoveryCommunity(dht_peer, self.ipv8.endpoint, self.ipv8.network)
            self.ipv8.overlays.append(self.dht_community)
            self.ipv8.strategies.append((RandomWalk(self.dht_community), 20))

        # Tunnel Community
        if self.session.config.get_tunnel_community_enabled():

            from Tribler.community.triblertunnel.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity
            community_cls = TriblerTunnelTestnetCommunity if self.session.config.get_testnet() else \
                TriblerTunnelCommunity
            self.tunnel_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  tribler_session=self.session,
                                                  dht_provider=MainlineDHTProvider(
                                                      self.mainline_dht,
                                                      self.session.config.get_dispersy_port()),
                                                  bandwidth_wallet=self.wallets["MB"])
            self.ipv8.overlays.append(self.tunnel_community)
            self.ipv8.strategies.append((RandomWalk(self.tunnel_community), 20))

        # Market Community
        if self.session.config.get_market_community_enabled():
            from Tribler.community.market.community import MarketCommunity, MarketTestnetCommunity

            community_cls = MarketTestnetCommunity if self.session.config.get_testnet() else MarketCommunity
            self.market_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  tribler_session=self.session,
                                                  trustchain=self.trustchain_community,
                                                  wallets=self.wallets,
                                                  working_directory=self.session.config.get_state_dir())

            self.ipv8.overlays.append(self.market_community)

            self.ipv8.strategies.append((RandomWalk(self.market_community), 20))

        # Popular Community
        if self.session.config.get_popularity_community_enabled():
            from Tribler.community.popularity.community import PopularityCommunity

            self.popularity_community = PopularityCommunity(peer, self.ipv8.endpoint, self.ipv8.network,
                                                            torrent_db=self.session.lm.torrent_db, session=self.session)

            self.ipv8.overlays.append(self.popularity_community)

            self.ipv8.strategies.append((RandomWalk(self.popularity_community), 20))

            self.popularity_community.start()

    @blocking_call_on_reactor_thread
    def load_dispersy_communities(self):
        self._logger.info("tribler: Preparing Dispersy communities...")
        now_time = timemod.time()
        default_kwargs = {'tribler_session': self.session}

        # Search Community
        if self.session.config.get_torrent_search_enabled() and self.dispersy:
            from Tribler.community.search.community import SearchCommunity
            self.dispersy.define_auto_load(SearchCommunity, self.session.dispersy_member, load=True,
                                           kargs=default_kwargs)

        # AllChannel Community
        if self.session.config.get_channel_search_enabled() and self.dispersy:
            from Tribler.community.allchannel.community import AllChannelCommunity
            self.dispersy.define_auto_load(AllChannelCommunity, self.session.dispersy_member, load=True,
                                           kargs=default_kwargs)

        # Channel Community
        if self.session.config.get_channel_community_enabled() and self.dispersy:
            from Tribler.community.channel.community import ChannelCommunity
            self.dispersy.define_auto_load(ChannelCommunity,
                                           self.session.dispersy_member, load=True, kargs=default_kwargs)

        # PreviewChannel Community
        if self.session.config.get_preview_channel_community_enabled() and self.dispersy:
            from Tribler.community.channel.preview import PreviewChannelCommunity
            self.dispersy.define_auto_load(PreviewChannelCommunity,
                                           self.session.dispersy_member, kargs=default_kwargs)

        self._logger.info("tribler: communities are ready in %.2f seconds", timemod.time() - now_time)

    def init(self):
        if self.dispersy:
            from Tribler.dispersy.community import HardKilledCommunity

            self._logger.info("lmc: Starting Dispersy...")

            self.session.readable_status = STATE_STARTING_DISPERSY
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
            private_key = self.dispersy.crypto.key_to_bin(
                M2CryptoSK(filename=self.session.config.get_permid_keypair_filename()))
            self.session.dispersy_member = blockingCallFromThread(reactor, self.dispersy.get_member,
                                                                  private_key=private_key)

            blockingCallFromThread(reactor, self.dispersy.define_auto_load, HardKilledCommunity,
                                   self.session.dispersy_member, load=True)

            if self.session.config.get_megacache_enabled():
                self.dispersy.database.attach_commit_callback(self.session.sqlite_db.commit_now)

            # notify dispersy finished loading
            self.session.notifier.notify(NTFY_DISPERSY, NTFY_STARTED, None)

            self.session.readable_status = STATE_LOADING_COMMUNITIES

        # We should load the mainline DHT before loading the IPv8 overlays since the DHT is used for the tunnel overlay.
        if self.session.config.get_mainline_dht_enabled():
            self.session.readable_status = STATE_START_MAINLINE_DHT
            from Tribler.Core.DecentralizedTracking import mainlineDHT
            self.mainline_dht = mainlineDHT.init(('127.0.0.1', self.session.config.get_mainline_dht_port()),
                                                 self.session.config.get_state_dir())
            self.upnp_ports.append((self.session.config.get_mainline_dht_port(), 'UDP'))

        # Wallets
        try:
            from Tribler.Core.Modules.wallet.btc_wallet import BitcoinWallet, BitcoinTestnetWallet
            wallet_type = BitcoinTestnetWallet if self.session.config.get_btc_testnet() else BitcoinWallet
            btc_wallet = wallet_type(os.path.join(self.session.config.get_state_dir(), 'wallet'))
            self.wallets[btc_wallet.get_identifier()] = btc_wallet
        except ImportError:
            self._logger.error("Electrum wallet cannot be found, Bitcoin wallet not available!")

        if self.session.config.get_dummy_wallets_enabled():
            # For debugging purposes, we create dummy wallets
            dummy_wallet1 = DummyWallet1()
            self.wallets[dummy_wallet1.get_identifier()] = dummy_wallet1

            dummy_wallet2 = DummyWallet2()
            self.wallets[dummy_wallet2.get_identifier()] = dummy_wallet2

        if self.ipv8:
            self.load_ipv8_overlays()

        if self.dispersy:
            self.load_dispersy_communities()

        tunnel_community_ports = self.session.config.get_tunnel_community_socks5_listen_ports()
        self.session.config.set_anon_proxy_settings(2, ("127.0.0.1", tunnel_community_ports))

        if self.session.config.get_channel_search_enabled() and self.session.config.get_dispersy_enabled():
            self.session.readable_status = STATE_INITIALIZE_CHANNEL_MGR
            from Tribler.Core.Modules.channel.channel_manager import ChannelManager
            self.channel_manager = ChannelManager(self.session)
            self.channel_manager.initialize()

        if self.session.config.get_libtorrent_enabled():
            self.session.readable_status = STATE_START_LIBTORRENT
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session)
            self.ltmgr.initialize()
            for port, protocol in self.upnp_ports:
                self.ltmgr.add_upnp_mapping(port, protocol)

        # add task for tracker checking
        if self.session.config.get_torrent_checking_enabled():
            self.session.readable_status = STATE_START_TORRENT_CHECKER
            self.torrent_checker = TorrentChecker(self.session)
            self.torrent_checker.initialize()

        if self.rtorrent_handler and self.session.config.get_dispersy_enabled():
            self.session.readable_status = STATE_START_REMOTE_TORRENT_HANDLER
            self.rtorrent_handler.initialize()

        if self.api_manager:
            self.session.readable_status = STATE_START_API_ENDPOINTS
            self.api_manager.root_endpoint.start_endpoints()

        if self.session.config.get_watch_folder_enabled():
            self.session.readable_status = STATE_START_WATCH_FOLDER
            self.watch_folder = WatchFolder(self.session)
            self.watch_folder.start()

        if self.session.config.get_credit_mining_enabled():
            self.session.readable_status = STATE_START_CREDIT_MINING
            from Tribler.Core.CreditMining.CreditMiningManager import CreditMiningManager
            self.credit_mining_manager = CreditMiningManager(self.session)

        if self.session.config.get_resource_monitor_enabled():
            self.resource_monitor = ResourceMonitor(self.session)
            self.resource_monitor.start()

        self.version_check_manager = VersionCheckManager(self.session)
        self.session.set_download_states_callback(self.sesscb_states_callback)

        self.initComplete = True

    def add(self, tdef, dscfg, pstate=None, setupDelay=0, hidden=False,
            share_mode=False, checkpoint_disabled=False):
        """ Called by any thread """
        d = None
        with self.session_lock:
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
                self._logger.info("Torrent already exists in the downloads. Infohash:%s", infohash.encode('hex'))

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

        if d and not hidden and self.session.config.get_megacache_enabled():
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
        out = None
        with self.session_lock:
            out = d.stop_remove(removestate=removestate, removecontent=removecontent)
            infohash = d.get_def().get_infohash()
            if infohash in self.downloads:
                del self.downloads[infohash]

        if not hidden:
            self.remove_id(infohash)

        if self.tunnel_community:
            self.tunnel_community.on_download_removed(d)

        return out or succeed(None)

    def remove_id(self, infohash):
        @forceDBThread
        def do_db():
            torrent_id = self.torrent_db.getTorrentID(infohash)
            if torrent_id:
                self.mypref_db.deletePreference(torrent_id)

        if self.session.config.get_megacache_enabled():
            do_db()

    def get_downloads(self):
        """ Called by any thread """
        with self.session_lock:
            return self.downloads.values()  # copy, is mutable

    def get_download(self, infohash):
        """ Called by any thread """
        with self.session_lock:
            return self.downloads.get(infohash, None)

    def download_exists(self, infohash):
        with self.session_lock:
            return infohash in self.downloads

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def update_download_hops(self, download, new_hops):
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = binascii.hexlify(download.tdef.get_infohash())
        self._logger.info("Updating the amount of hops of download %s", infohash)
        yield self.session.remove_download(download)

        # copy the old download_config and change the hop count
        dscfg = download.copy()
        dscfg.set_hops(new_hops)
        # If the user wants to change the hop count to 0, don't automatically bump this up to 1 anymore
        dscfg.set_safe_seeding(False)

        self.session.start_download_from_tdef(download.tdef, dscfg)

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

                    if self.session.config.get_megacache_enabled():
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

    def set_download_states_callback(self, user_callback, interval=1.0):
        """
        Set the download state callback. Remove any old callback if it's present.
        """
        self.stop_download_states_callback()
        self._logger.debug("Starting the download state callback with interval %f", interval)
        self.download_states_lc = self.register_task("download_states_lc",
                                                     LoopingCall(self._invoke_states_cb, user_callback))
        self.download_states_lc.start(interval)

    def _invoke_states_cb(self, callback):
        """
        Invoke the download states callback with a list of the download states.
        """
        dslist = []
        for d in self.downloads.values():
            d.set_moreinfo_stats(True in self.get_peer_list or d.get_def().get_infohash() in
                                 self.get_peer_list)
            ds = d.network_get_state(None)
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
            infohash = tdef.get_infohash()

            if state == DLSTATUS_DOWNLOADING:
                new_active_downloads.append(infohash)
            elif state == DLSTATUS_STOPPED_ON_ERROR:
                self._logger.error("Error during download: %s", repr(ds.get_error()))
                if self.download_exists(infohash):
                    self.get_download(infohash).stop()
                    self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, infohash, repr(ds.get_error()))
            elif state == DLSTATUS_SEEDING:
                seeding_download_list.append({u'infohash': infohash,
                                              u'download': download})

                if infohash in self.previous_active_downloads:
                    self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, infohash, safename)
                    do_checkpoint = True
                elif download.get_hops() == 0 and download.get_safe_seeding():
                    # Re-add the download with anonymity enabled
                    hops = self.session.config.get_default_number_hops()
                    self.update_download_hops(download, hops)

        self.previous_active_downloads = new_active_downloads
        if do_checkpoint:
            self.session.checkpoint_downloads()

        if self.state_cb_count % 4 == 0:
            if self.tunnel_community:
                self.tunnel_community.monitor_downloads(states_list)
            if self.credit_mining_manager:
                self.credit_mining_manager.monitor_downloads(states_list)

        return []

    #
    # Persistence methods
    #
    def load_checkpoint(self):
        """ Called by any thread """

        def do_load_checkpoint():
            with self.session_lock:
                for i, filename in enumerate(iglob(os.path.join(self.session.get_downloads_pstate_dir(), '*.state'))):
                    self.resume_download(filename, setupDelay=i * 0.1)

        if self.initComplete:
            do_load_checkpoint()
        else:
            self.register_task("load_checkpoint", reactor.callLater(1, do_load_checkpoint))

    def load_download_pstate_noexc(self, infohash):
        """ Called by any thread, assume session_lock already held """
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

            if pstate.has_option('download_defaults', 'saveas') and \
                    isinstance(pstate.get('download_defaults', 'saveas'), tuple):
                pstate.set('download_defaults', 'saveas', pstate.get('download_defaults', 'saveas')[-1])

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

        self.shutdown_task_manager()

        # Note: session_lock not held
        self.shutdownstarttime = timemod.time()
        if self.credit_mining_manager:
            yield self.credit_mining_manager.shutdown()
        self.credit_mining_manager = None

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

        if self.resource_monitor:
            self.resource_monitor.stop()
        self.resource_monitor = None

        self.tracker_manager = None

        if self.tunnel_community and self.trustchain_community:
            # We unload these overlays manually since the TrustChain has to be unloaded after the tunnel overlay.
            yield self.ipv8.unload_overlay(self.tunnel_community)
            yield self.ipv8.unload_overlay(self.trustchain_community)

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

        if self.ipv8:
            yield self.ipv8.stop(stop_reactor=False)

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

        if self.watch_folder is not None:
            yield self.watch_folder.stop()
        self.watch_folder = None

        # We close the API manager as late as possible during shutdown.
        if self.api_manager is not None:
            yield self.api_manager.stop()
        self.api_manager = None

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
