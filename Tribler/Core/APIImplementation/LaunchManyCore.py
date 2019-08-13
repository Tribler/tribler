"""
LaunchManyCore

Author(s): Arno Bakker, Niels Zeilemaker
"""
from __future__ import absolute_import

import logging
import os
import sys
import time
import time as timemod
from binascii import unhexlify
from glob import iglob
from threading import Event, enumerate as enumerate_threads
from traceback import print_exc

from anydex.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from anydex.wallet.tc_wallet import TrustchainWallet

from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import DiscoveryCommunity, PeriodicSimilarity
from ipv8.peerdiscovery.discovery import EdgeWalk, RandomWalk
from ipv8.taskmanager import TaskManager

from ipv8_service import IPv8

from six import text_type

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, succeed
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread
from twisted.python.threadable import isInIOThread

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Modules.gigachannel_manager import GigaChannelManager
from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Core.Modules.resource_monitor import ResourceMonitor
from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.Modules.versioncheck_manager import VersionCheckManager
from Tribler.Core.Modules.watch_folder import WatchFolder
from Tribler.Core.TorrentChecker.torrent_checker import TorrentChecker
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Video.VideoServer import VideoServer
from Tribler.Core.bootstrap import Bootstrap
from Tribler.Core.simpledefs import (DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR, NTFY_ERROR,
                                     NTFY_FINISHED, NTFY_STARTED, NTFY_TORRENT, NTFY_TRIBLER,
                                     STATE_START_API_ENDPOINTS, STATE_START_CREDIT_MINING,
                                     STATE_START_LIBTORRENT, STATE_START_TORRENT_CHECKER, STATE_START_WATCH_FOLDER)


class TriblerLaunchMany(TaskManager):

    def __init__(self):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        super(TriblerLaunchMany, self).__init__()

        self.initComplete = False
        self.ipv8 = None
        self.ipv8_start_time = 0
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

        self.bootstrap = None

        # modules
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

        self.gigachannel_manager = None

        self.video_server = None

        self.ltmgr = None
        self.tracker_manager = None
        self.torrent_checker = None
        self.tunnel_community = None
        self.trustchain_community = None
        self.wallets = {}
        self.popularity_community = None
        self.gigachannel_community = None

        self.startup_deferred = Deferred()

        self.credit_mining_manager = None
        self.market_community = None
        self.dht_community = None
        self.payout_manager = None
        self.mds = None

    def register(self, session, session_lock):
        assert isInIOThread()

        self.session = session
        self.session_lock = session_lock

        self.tracker_manager = TrackerManager(self.session)

        # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
        # certificates provided by the system trust store.
        if sys.platform == 'darwin':
            os.environ['SSL_CERT_FILE'] = os.path.join(get_lib_path(), 'root_certs_mac.pem')

        if self.session.config.get_video_server_enabled():
            self.video_server = VideoServer(self.session.config.get_video_server_port(), self.session)
            self.video_server.start()

        # IPv8
        if self.session.config.get_ipv8_enabled():
            from ipv8.configuration import get_default_configuration
            ipv8_config = get_default_configuration()
            ipv8_config['port'] = self.session.config.get_ipv8_port()
            ipv8_config['address'] = self.session.config.get_ipv8_address()
            ipv8_config['overlays'] = []
            ipv8_config['keys'] = []  # We load the keys ourselves

            if self.session.config.get_ipv8_bootstrap_override():
                import ipv8.community as community_file
                community_file._DEFAULT_ADDRESSES = [self.session.config.get_ipv8_bootstrap_override()]
                community_file._DNS_ADDRESSES = []

            self.ipv8 = IPv8(ipv8_config, enable_statistics=self.session.config.get_ipv8_statistics())

            self.session.config.set_anon_proxy_settings(2, ("127.0.0.1",
                                                            self.session.
                                                            config.get_tunnel_community_socks5_listen_ports()))
        self.init()

    def load_ipv8_overlays(self):
        if self.session.config.get_testnet():
            peer = Peer(self.session.trustchain_testnet_keypair)
        else:
            peer = Peer(self.session.trustchain_keypair)
        discovery_community = DiscoveryCommunity(peer, self.ipv8.endpoint, self.ipv8.network)
        discovery_community.resolve_dns_bootstrap_addresses()
        self.ipv8.overlays.append(discovery_community)
        self.ipv8.strategies.append((RandomChurn(discovery_community), -1))
        self.ipv8.strategies.append((PeriodicSimilarity(discovery_community), -1))
        self.ipv8.strategies.append((RandomWalk(discovery_community), 20))

        # TrustChain Community
        if self.session.config.get_trustchain_enabled():
            from ipv8.attestation.trustchain.community import TrustChainCommunity, \
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
            from ipv8.dht.discovery import DHTDiscoveryCommunity

            self.dht_community = DHTDiscoveryCommunity(peer, self.ipv8.endpoint, self.ipv8.network)
            self.ipv8.overlays.append(self.dht_community)
            self.ipv8.strategies.append((RandomWalk(self.dht_community), 20))

        # Tunnel Community
        if self.session.config.get_tunnel_community_enabled():
            from Tribler.community.triblertunnel.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity
            from Tribler.community.triblertunnel.discovery import GoldenRatioStrategy
            community_cls = TriblerTunnelTestnetCommunity if self.session.config.get_testnet() else \
                TriblerTunnelCommunity

            random_slots = self.session.config.get_tunnel_community_random_slots()
            competing_slots = self.session.config.get_tunnel_community_competing_slots()

            dht_provider = DHTCommunityProvider(self.dht_community, self.session.config.get_ipv8_port())
            settings = TunnelSettings()
            settings.min_circuits = 3
            settings.max_circuits = 10
            self.tunnel_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  tribler_session=self.session,
                                                  dht_provider=dht_provider,
                                                  bandwidth_wallet=self.wallets["MB"],
                                                  random_slots=random_slots,
                                                  competing_slots=competing_slots,
                                                  settings=settings)
            self.ipv8.overlays.append(self.tunnel_community)
            self.ipv8.strategies.append((RandomWalk(self.tunnel_community), 20))
            self.ipv8.strategies.append((GoldenRatioStrategy(self.tunnel_community), -1))

        # Market Community
        if self.session.config.get_market_community_enabled() and self.session.config.get_dht_enabled():
            from anydex.core.community import MarketCommunity, MarketTestnetCommunity

            community_cls = MarketTestnetCommunity if self.session.config.get_testnet() else MarketCommunity
            self.market_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network,
                                                  trustchain=self.trustchain_community,
                                                  dht=self.dht_community,
                                                  wallets=self.wallets,
                                                  working_directory=self.session.config.get_state_dir(),
                                                  record_transactions=self.session.config.get_record_transactions())

            self.ipv8.overlays.append(self.market_community)

            self.ipv8.strategies.append((RandomWalk(self.market_community), 20))

        # Popular Community
        if self.session.config.get_popularity_community_enabled():
            from Tribler.community.popularity.community import PopularityCommunity

            self.popularity_community = PopularityCommunity(peer, self.ipv8.endpoint, self.ipv8.network,
                                                            metadata_store=self.session.lm.mds,
                                                            torrent_checker=self.torrent_checker)

            self.ipv8.overlays.append(self.popularity_community)
            self.ipv8.strategies.append((RandomWalk(self.popularity_community), 20))

        # Gigachannel Community
        if self.session.config.get_chant_enabled():
            from Tribler.community.gigachannel.community import GigaChannelCommunity, GigaChannelTestnetCommunity
            from Tribler.community.gigachannel.sync_strategy import SyncChannels

            community_cls = GigaChannelTestnetCommunity if self.session.config.get_testnet() else GigaChannelCommunity
            self.gigachannel_community = community_cls(peer, self.ipv8.endpoint, self.ipv8.network, self.mds,
                                                       notifier=self.session.notifier)

            self.ipv8.overlays.append(self.gigachannel_community)

            self.ipv8.strategies.append((RandomWalk(self.gigachannel_community), 20))
            self.ipv8.strategies.append((SyncChannels(self.gigachannel_community), 20))

    def enable_ipv8_statistics(self):
        if self.session.config.get_ipv8_statistics():
            for overlay in self.ipv8.overlays:
                self.ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

    def init(self):
        # Wallets
        if self.session.config.get_bitcoinlib_enabled():
            try:
                from anydex.wallet.btc_wallet import BitcoinWallet, BitcoinTestnetWallet
                wallet_path = os.path.join(self.session.config.get_state_dir(), 'wallet')
                btc_wallet = BitcoinWallet(wallet_path)
                btc_testnet_wallet = BitcoinTestnetWallet(wallet_path)
                self.wallets[btc_wallet.get_identifier()] = btc_wallet
                self.wallets[btc_testnet_wallet.get_identifier()] = btc_testnet_wallet
            except Exception as exc:
                self._logger.error("bitcoinlib library cannot be loaded: %s", exc)

        if self.session.config.get_chant_enabled():
            channels_dir = os.path.join(self.session.config.get_chant_channels_dir())
            database_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'metadata.db')
            self.mds = MetadataStore(database_path, channels_dir, self.session.trustchain_keypair)

        if self.session.config.get_dummy_wallets_enabled():
            # For debugging purposes, we create dummy wallets
            dummy_wallet1 = DummyWallet1()
            self.wallets[dummy_wallet1.get_identifier()] = dummy_wallet1

            dummy_wallet2 = DummyWallet2()
            self.wallets[dummy_wallet2.get_identifier()] = dummy_wallet2

        if self.session.config.get_torrent_checking_enabled():
            self.session.readable_status = STATE_START_TORRENT_CHECKER
            self.torrent_checker = TorrentChecker(self.session)
            self.torrent_checker.initialize()

        if self.ipv8:
            self.ipv8_start_time = time.time()
            self.load_ipv8_overlays()
            self.enable_ipv8_statistics()

        tunnel_community_ports = self.session.config.get_tunnel_community_socks5_listen_ports()
        self.session.config.set_anon_proxy_settings(2, ("127.0.0.1", tunnel_community_ports))

        if self.session.config.get_libtorrent_enabled():
            self.session.readable_status = STATE_START_LIBTORRENT
            from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
            self.ltmgr = LibtorrentMgr(self.session)
            self.ltmgr.initialize()
            for port, protocol in self.upnp_ports:
                self.ltmgr.add_upnp_mapping(port, protocol)

        if self.session.config.get_chant_enabled():
            self.gigachannel_manager = GigaChannelManager(self.session)
            # GigaChannel Manager startup routines are started asynchronously by Session
            # after resuming Libtorrent downloads.

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

        if self.session.config.get_version_checker_enabled():
            self.version_check_manager = VersionCheckManager(self.session)
            self.version_check_manager.start()

        self.session.set_download_states_callback(self.sesscb_states_callback)

        if self.session.config.get_ipv8_enabled() and self.session.config.get_trustchain_enabled():
            self.payout_manager = PayoutManager(self.trustchain_community, self.dht_community)

        # Start bootstrap download if not already done
        if not self.session.lm.bootstrap:
            self.session.lm.start_bootstrap_download()

        self.initComplete = True

    def add(self, tdef, config, setupDelay=0, hidden=False,
            share_mode=False, checkpoint_disabled=False):
        """ Called by any thread """
        with self.session_lock:
            infohash = tdef.get_infohash()

            # Create the destination directory if it does not exist yet
            try:
                if not os.path.isdir(config.get_dest_dir()):
                    os.makedirs(config.get_dest_dir())
            except OSError:
                self._logger.error("Unable to create the download destination directory.")

            if config.get_time_added() == 0:
                config.set_time_added(int(timemod.time()))

            hidden_torrent = hidden or config.get_bootstrap_download()
            # Check if running or saved on disk
            if infohash in self.downloads:
                self._logger.info("Torrent already exists in the downloads. Infohash:%s", hexlify(infohash))

            from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
            d = LibtorrentDownloadImpl(self.session, tdef)

            config = config or self.load_download_config_by_infohash(infohash)  # not already resuming

            # Store in list of Downloads, always.
            self.downloads[infohash] = d
            setup_deferred = d.setup(config, wrapperDelay=setupDelay,
                                     share_mode=share_mode, checkpoint_disabled=checkpoint_disabled,
                                     hidden=hidden_torrent)
            setup_deferred.addCallback(self.on_download_handle_created)

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

        return out or succeed(None)

    def get_downloads(self):
        """ Called by any thread """
        with self.session_lock:
            return list(self.downloads.values())  # copy, is mutable

    def get_channel_downloads(self):
        with self.session_lock:
            return [download for download in self.downloads.values() if download.config.get_channel_download()]

    def get_download(self, infohash):
        """ Called by any thread """
        with self.session_lock:
            return self.downloads.get(infohash, None)

    def download_exists(self, infohash):
        with self.session_lock:
            return infohash in self.downloads

    @inlineCallbacks
    def update_download_hops(self, download, new_hops):
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = hexlify(download.tdef.get_infohash())
        self._logger.info("Updating the amount of hops of download %s", infohash)
        download.config.set_engineresumedata((yield download.save_resume_data()))
        yield self.session.remove_download(download)

        # copy the old download_config and change the hop count
        config = download.config.copy()
        config.set_hops(new_hops)
        # If the user wants to change the hop count to 0, don't automatically bump this up to 1 anymore
        config.set_safe_seeding(False)

        self.session.start_download_from_tdef(download.tdef, config)

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
            is_hidden = download.hidden

            if state == DLSTATUS_DOWNLOADING:
                new_active_downloads.append(infohash)
            elif state == DLSTATUS_STOPPED_ON_ERROR:
                self._logger.error("Error during download: %s", repr(ds.get_error()))
                if self.download_exists(infohash):
                    self.get_download(infohash).stop()
                    self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, infohash, repr(ds.get_error()), is_hidden)
            elif state == DLSTATUS_SEEDING:
                seeding_download_list.append({u'infohash': infohash,
                                              u'download': download})

                if self.bootstrap and not self.bootstrap.bootstrap_finished and hexlify(
                        infohash) == self.session.config.get_bootstrap_infohash() and self.trustchain_community:
                    self.bootstrap.bootstrap_finished = True
                    with open(self.bootstrap.bootstrap_file, 'r') as f:
                        sql_dumb = text_type(f.read())
                        self._logger.info("Executing script for trustchain bootstrap")
                        self.trustchain_community.persistence.executescript(sql_dumb)
                        self.trustchain_community.persistence.commit()

                if infohash in self.previous_active_downloads:
                    self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, infohash, safename, is_hidden)
                    do_checkpoint = True
                elif download.config.get_hops() == 0 and download.config.get_safe_seeding():
                    # Re-add the download with anonymity enabled
                    hops = self.session.config.get_default_number_hops()
                    self.update_download_hops(download, hops)

            # Check the peers of this download every five seconds and add them to the payout manager when
            # this peer runs a Tribler instance
            if self.state_cb_count % 5 == 0 and download.config.get_hops() == 0 and self.payout_manager:
                for peer in download.get_peerlist():
                    if peer["extended_version"].startswith('Tribler'):
                        self.payout_manager.update_peer(unhexlify(peer["id"]), infohash, peer["dtotal"])
                        if self.bootstrap and hexlify(infohash) == self.session.config.get_bootstrap_infohash():
                            self.bootstrap.fetch_bootstrap_peers()

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
                for i, filename in enumerate(iglob(os.path.join(self.session.get_downloads_config_dir(), '*.conf'))):
                    self.resume_download(filename, setupDelay=i * 0.1)

        if self.initComplete:
            do_load_checkpoint()
        else:
            self.register_task("load_checkpoint", reactor.callLater(1, do_load_checkpoint))

    def resume_download(self, filename, setupDelay=0):

        try:
            config = self.load_download_config(filename)
            if not config:
                return
        except Exception as e:
            self._logger.exception("tlm: could not open checkpoint file %s", str(filename))
            return

        metainfo = config.get_metainfo()
        if not metainfo:
            self._logger.error("tlm: could not resume checkpoint %s; metainfo not found", filename)
            return
        if not isinstance(metainfo, dict):
            self._logger.error("tlm: could not resume checkpoint %s; metainfo is not dict %s %s",
                               filename, type(metainfo), repr(metainfo))
            return

        try:
            url = metainfo.get(b'url', None)
            url = url.decode('utf-8') if url else url
            tdef = (TorrentDefNoMetainfo(metainfo[b'infohash'], metainfo[b'name'], url)
                    if b'infohash' in metainfo else TorrentDef.load_from_dict(metainfo))
        except ValueError as e:
            self._logger.exception("tlm: could not restore tdef from metainfo dict: %s %s ", e, text_type(metainfo))
            return

        config.state_dir = self.session.config.get_state_dir()

        self._logger.debug("tlm: load_checkpoint: resumedata %s", bool(config.get_engineresumedata()))
        if not (tdef and config):
            self._logger.info("tlm: could not resume checkpoint %s %s %s", filename, tdef, config)
            return

        if config.get_dest_dir() == '':  # removed torrent ignoring
            self._logger.info("tlm: removing checkpoint %s destdir is %s", filename, config.get_dest_dir())
            os.remove(filename)
            return

        try:
            if self.download_exists(tdef.get_infohash()):
                self._logger.info("tlm: not resuming checkpoint because download has already been added")
            elif config.get_credit_mining() and not self.session.config.get_credit_mining_enabled():
                self._logger.info("tlm: not resuming checkpoint since token mining is disabled")
            else:
                self.add(tdef, config, setupDelay=setupDelay)
        except Exception as e:
            self._logger.exception("tlm: load check_point: exception while adding download %s", tdef)

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

    def remove_download_config(self, infohash):
        def do_remove():
            if not self.download_exists(infohash):
                config_dir = self.session.get_downloads_config_dir()

                # Remove checkpoint
                hexinfohash = hexlify(infohash)
                try:
                    basename = hexinfohash + '.conf'
                    filename = os.path.join(config_dir, basename)
                    self._logger.debug("remove download config: removing dlcheckpoint entry %s", filename)
                    if os.access(filename, os.F_OK):
                        os.remove(filename)
                except:
                    # Show must go on
                    self._logger.exception("Could not remove state")
            else:
                self._logger.warning("remove download config: download is back, restarted? Canceling removal! %s",
                                     repr(infohash))

        reactor.callFromThread(do_remove)

    def start_bootstrap_download(self):
        if self.session.config.get_bootstrap_enabled():
            if not self.payout_manager:
                self._logger.warn("Running bootstrap without payout enabled")
            self.bootstrap = Bootstrap(self.session.config.get_state_dir(), dht=self.dht_community)
            if os.path.exists(self.bootstrap.bootstrap_file):
                self.bootstrap.start_initial_seeder(self.session.start_download_from_tdef,
                                                    self.bootstrap.bootstrap_file,
                                                    self.session.config.get_bootstrap_infohash())
            else:
                self.bootstrap.start_by_infohash(self.session.start_download_from_tdef,
                                                 self.session.config.get_bootstrap_infohash())

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
            self.session.notify_shutdown_state("Shutting down Credit Mining...")
            yield self.credit_mining_manager.shutdown()
        self.credit_mining_manager = None

        if self.torrent_checker:
            self.session.notify_shutdown_state("Shutting down Torrent Checker...")
            yield self.torrent_checker.shutdown()
        self.torrent_checker = None

        if self.gigachannel_manager:
            self.session.notify_shutdown_state("Shutting down Gigachannel Manager...")
            yield self.gigachannel_manager.shutdown()
        self.gigachannel_manager = None

        if self.video_server:
            self.session.notify_shutdown_state("Shutting down Video Server...")
            yield self.video_server.shutdown_server()
        self.video_server = None

        if self.version_check_manager:
            self.session.notify_shutdown_state("Shutting down Version Checker...")
            self.version_check_manager.stop()
        self.version_check_manager = None

        if self.resource_monitor:
            self.session.notify_shutdown_state("Shutting down Resource Monitor...")
            self.resource_monitor.stop()
        self.resource_monitor = None

        self.tracker_manager = None

        if self.tunnel_community and self.trustchain_community:
            # We unload these overlays manually since the TrustChain has to be unloaded after the tunnel overlay.
            tunnel_community = self.tunnel_community
            self.tunnel_community = None
            self.session.notify_shutdown_state("Unloading Tunnel Community...")
            yield self.ipv8.unload_overlay(tunnel_community)
            trustchain_community = self.trustchain_community
            self.trustchain_community = None
            self.session.notify_shutdown_state("Shutting down TrustChain Community...")
            yield self.ipv8.unload_overlay(trustchain_community)

        if self.ipv8:
            self.session.notify_shutdown_state("Shutting down IPv8...")
            yield self.ipv8.stop(stop_reactor=False)

        if self.channelcast_db is not None:
            self.session.notify_shutdown_state("Shutting down ChannelCast DB...")
            yield self.channelcast_db.close()
        self.channelcast_db = None

        if self.votecast_db is not None:
            self.session.notify_shutdown_state("Shutting down VoteCast DB...")
            yield self.votecast_db.close()
        self.votecast_db = None

        if self.mypref_db is not None:
            self.session.notify_shutdown_state("Shutting down Preference DB...")
            yield self.mypref_db.close()
        self.mypref_db = None

        if self.torrent_db is not None:
            self.session.notify_shutdown_state("Shutting down Torrent DB...")
            yield self.torrent_db.close()
        self.torrent_db = None

        if self.peer_db is not None:
            self.session.notify_shutdown_state("Shutting down Peer DB...")
            yield self.peer_db.close()
        self.peer_db = None

        if self.watch_folder is not None:
            self.session.notify_shutdown_state("Shutting down Watch Folder...")
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

    def load_download_config(self, filename):
        return DownloadConfig.load(filename)

    def load_download_config_by_infohash(self, infohash):
        try:
            basename = hexlify(infohash) + '.conf'
            filename = os.path.join(self.session.get_downloads_config_dir(), basename)
            if os.path.exists(filename):
                return self.load_download_config(filename)
            else:
                self._logger.info("%s not found", basename)

        except Exception:
            self._logger.exception("Exception while loading config: %s", infohash)
