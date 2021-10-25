"""
A wrapper around libtorrent

Author(s): Egbert Bouman
"""
import asyncio
import logging
import os
import time as timemod
from asyncio import CancelledError, gather, iscoroutine, shield, sleep, wait_for
from binascii import unhexlify
from copy import deepcopy
from shutil import rmtree
from typing import List, Optional

from ipv8.taskmanager import TaskManager, task

from tribler_common.network_utils import NetworkUtils
from tribler_common.simpledefs import DLSTATUS_SEEDING, MAX_LIBTORRENT_RATE_LIMIT, NTFY, STATEDIR_CHECKPOINT_DIR
from tribler_common.utilities import uri_to_path

from tribler_core.components.libtorrent.download_manager.dht_health_manager import DHTHealthManager
from tribler_core.components.libtorrent.download_manager.download import Download
from tribler_core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler_core.components.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler_core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler_core.components.libtorrent.utils import torrent_utils
from tribler_core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler_core.notifier import Notifier
from tribler_core.utilities import path_util
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import bdecode_compat, has_bep33_support, parse_magnetlink
from tribler_core.version import version_id

SOCKS5_PROXY_DEF = 2

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DEFAULT_DHT_ROUTERS = [
    ("dht.libtorrent.org", 25401),
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881)
]
DEFAULT_LT_EXTENSIONS = [
    lt.create_ut_metadata_plugin,
    lt.create_ut_pex_plugin,
    lt.create_smart_ban_plugin
]


def encode_atp(atp):
    for k, v in atp.items():
        if isinstance(v, str):
            atp[k] = v.encode('utf-8')
        elif isinstance(v, path_util.Path):
            atp[k] = str(v)
    return atp


class DownloadManager(TaskManager):

    def __init__(self,
                 state_dir,
                 notifier: Notifier,
                 peer_mid: bytes,
                 config: LibtorrentSettings = None,
                 download_defaults: DownloadDefaultsSettings = None,
                 bootstrap_infohash=None,
                 socks_listen_ports: Optional[List[int]] = None,
                 dummy_mode: bool = False):
        super().__init__()
        self.dummy_mode = dummy_mode
        self._logger = logging.getLogger(self.__class__.__name__)

        self.state_dir = state_dir
        self.ltsettings = {}  # Stores a copy of the settings dict for each libtorrent session
        self.ltsessions = {}
        self.dht_health_manager = None
        self.listen_ports = {}

        self.socks_listen_ports = socks_listen_ports

        # TODO: Remove the dependency on notifier and refactor it to instead use callbacks injection
        self.notifier = notifier
        self.peer_mid = peer_mid
        self.config = config or LibtorrentSettings()
        self.bootstrap_infohash = bootstrap_infohash
        self.download_defaults = download_defaults or DownloadDefaultsSettings()
        self._libtorrent_port = None

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.downloads = {}

        self.metadata_tmpdir = None
        # Dictionary that maps infohashes to download instances. These include only downloads that have
        # been made specifically for fetching metainfo, and will be removed afterwards.
        self.metainfo_requests = {}
        self.metainfo_cache = {}  # Dictionary that maps infohashes to cached metainfo items

        self.default_alert_mask = lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | \
            lt.alert.category_t.storage_notification | lt.alert.category_t.performance_warning | \
            lt.alert.category_t.tracker_notification | lt.alert.category_t.debug_notification
        self.session_stats_callback = None
        self.state_cb_count = 0

        # Status of libtorrent session to indicate if it can safely close and no pending writes to disk exists.
        self.lt_session_shutdown_ready = {}
        self._dht_ready_task = None
        self.dht_readiness_timeout = self.config.dht_readiness_timeout if not self.dummy_mode else 0
        self._last_states_list = []

    @property
    def libtorrent_port(self):
        return self._libtorrent_port

    async def _check_dht_ready(self, min_dht_peers=60):
        # Checks whether we got enough DHT peers. If the number of DHT peers is low,
        # checking for a bunch of torrents in a short period of time may result in several consecutive requests
        # sent to the same peers. This can trigger those peers' flood protection mechanism,
        # which results in DHT checks stuck for hours.
        # See https://github.com/Tribler/tribler/issues/5319
        while not (self.get_session() and self.get_session().status().dht_nodes > min_dht_peers):
            await asyncio.sleep(1)

    def initialize(self):
        # Create the checkpoints directory
        (self.state_dir / STATEDIR_CHECKPOINT_DIR).mkdir(exist_ok=True)

        # Start upnp
        if self.config.upnp:
            self.get_session().start_upnp()

        if has_bep33_support() and self.download_defaults.number_hops <= len(self.socks_listen_ports or []):
            # Also listen to DHT log notifications - we need the dht_pkt_alert and extract the BEP33 bloom filters
            dht_health_session = self.get_session(self.download_defaults.number_hops)
            dht_health_session.set_alert_mask(self.default_alert_mask | lt.alert.category_t.dht_log_notification)
            self.dht_health_manager = DHTHealthManager(dht_health_session)

        # Make temporary directory for metadata collecting through DHT
        self.metadata_tmpdir = Path.mkdtemp(suffix='tribler_metainfo_tmpdir')

        # Register tasks
        self.register_task("process_alerts", self._task_process_alerts, interval=1)
        if self.dht_readiness_timeout > 0 and self.config.dht:
            self._dht_ready_task = self.register_task("check_dht_ready", self._check_dht_ready)
        self.register_task("request_torrent_updates", self._request_torrent_updates, interval=1)
        self.register_task('task_cleanup_metacache', self._task_cleanup_metainfo_cache, interval=60, delay=0)

        self.set_download_states_callback(self.sesscb_states_callback)

    async def shutdown(self, timeout=30):
        if self.downloads:
            self.notifier.notify_shutdown_state("Checkpointing Downloads...")
            await gather(*[download.stop() for download in self.downloads.values()], return_exceptions=True)
            self.notifier.notify_shutdown_state("Shutting down Downloads...")
            await gather(*[download.shutdown() for download in self.downloads.values()], return_exceptions=True)

        self.notifier.notify_shutdown_state("Shutting down Libtorrent Manager...")
        # If libtorrent session has pending disk io, wait until timeout (default: 30 seconds) to let it finish.
        # In between ask for session stats to check if state is clean for shutdown.
        # In dummy mode, we immediately shut down the download manager.
        while not self.dummy_mode and not self.is_shutdown_ready() and timeout >= 1:
            self.notifier.notify_shutdown_state("Waiting for Libtorrent to finish...")
            self.post_session_stats()
            timeout -= 1
            await asyncio.sleep(1)

        await self.shutdown_task_manager()

        if self.dht_health_manager:
            await self.dht_health_manager.shutdown_task_manager()

        # Save libtorrent state
        if self.has_session():
            with open(self.state_dir / LTSTATE_FILENAME, 'wb') as ltstate_file:
                ltstate_file.write(lt.bencode(self.get_session().save_state()))

        if self.has_session() and self.config.upnp:
            self.get_session().stop_upnp()

        for ltsession in self.ltsessions.values():
            del ltsession
        self.ltsessions = None

        # Remove metadata temporary directory
        if self.metadata_tmpdir:
            rmtree(self.metadata_tmpdir)
            self.metadata_tmpdir = None

    def is_shutdown_ready(self):
        return all(self.lt_session_shutdown_ready.values())

    def create_session(self, hops=0, store_listen_port=True):
        # Due to a bug in Libtorrent 0.16.18, the outgoing_port and num_outgoing_ports value should be set in
        # the settings dictionary
        self._logger.info('Creating a session')
        settings = {'outgoing_port': 0,
                    'num_outgoing_ports': 1,
                    'allow_multiple_connections_per_ip': 0,
                    'enable_upnp': int(self.config.upnp),
                    'enable_dht': int(self.config.dht),
                    'enable_lsd': int(self.config.lsd),
                    'enable_natpmp': int(self.config.natpmp)}

        # Copy construct so we don't modify the default list
        extensions = list(DEFAULT_LT_EXTENSIONS)

        self._logger.info(f'Dummy mode: {self.dummy_mode}. Hops: {hops}.')

        # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
        fingerprint = ['TL'] + [int(x) for x in version_id.split('-')[0].split('.')] + [0]
        if self.dummy_mode:
            from unittest.mock import Mock
            ltsession = Mock()
            ltsession.pop_alerts = lambda: {}
            ltsession.listen_port = lambda: 123
            ltsession.get_settings = lambda: {"peer_fingerprint": "000"}
        else:
            ltsession = lt.session(lt.fingerprint(*fingerprint), flags=0) if hops == 0 else lt.session(flags=0)

        libtorrent_port = self.config.port or NetworkUtils().get_random_free_port()
        self._libtorrent_port = libtorrent_port
        self._logger.info(f'Libtorrent port: {libtorrent_port}')
        if hops == 0:
            settings['user_agent'] = 'Tribler/' + version_id
            enable_utp = self.config.utp
            settings['enable_outgoing_utp'] = enable_utp
            settings['enable_incoming_utp'] = enable_utp

            settings['prefer_rc4'] = True
            settings["listen_interfaces"] = "0.0.0.0:%d" % libtorrent_port

            settings['peer_fingerprint'] = self.peer_mid
            settings['handshake_client_version'] = 'Tribler/' + version_id + '/' + hexlify(self.peer_mid)
        else:
            settings['enable_outgoing_utp'] = True
            settings['enable_incoming_utp'] = True
            settings['enable_outgoing_tcp'] = False
            settings['enable_incoming_tcp'] = False
            settings['anonymous_mode'] = True
            settings['force_proxy'] = True

            # Anon listen port is never used anywhere, so we let Libtorrent set it
            #settings["listen_interfaces"] = "0.0.0.0:%d" % anon_port

            # By default block all IPs except 1.1.1.1 (which is used to ensure libtorrent makes a connection to us)
            self.update_ip_filter(ltsession, ['1.1.1.1'])

        self.set_session_settings(ltsession, settings)
        ltsession.set_alert_mask(self.default_alert_mask)

        if hops == 0:
            proxy_settings = DownloadManager.get_libtorrent_proxy_settings(self.config)
        else:
            proxy_settings = [SOCKS5_PROXY_DEF, ("127.0.0.1", self.socks_listen_ports[hops-1]), None]
        self.set_proxy_settings(ltsession, *proxy_settings)

        for extension in extensions:
            ltsession.add_extension(extension)

        # Set listen port & start the DHT
        if hops == 0:
            ltsession.listen_on(libtorrent_port, libtorrent_port + 10)
            if libtorrent_port != ltsession.listen_port() and store_listen_port:
                self.config.port = ltsession.listen_port()
            try:
                with open(self.state_dir / LTSTATE_FILENAME, 'rb') as fp:
                    lt_state = bdecode_compat(fp.read())
                if lt_state is not None:
                    ltsession.load_state(lt_state)
                else:
                    self._logger.warning("the lt.state appears to be corrupt, writing new data on shutdown")
            except Exception as exc:
                self._logger.info(f"could not load libtorrent state, got exception: {exc!r}. starting from scratch")
        else:
            #ltsession.listen_on(anon_port, anon_port + 20)

            rate = DownloadManager.get_libtorrent_max_upload_rate(self.config)
            download_rate = DownloadManager.get_libtorrent_max_download_rate(self.config)
            settings = {'upload_rate_limit': rate,
                        'download_rate_limit': download_rate}
            self.set_session_settings(ltsession, settings)

        if self.config.dht and not self.dummy_mode:
            ltsession.start_dht()
            for router in DEFAULT_DHT_ROUTERS:
                ltsession.add_dht_router(*router)
            ltsession.start_lsd()

        self._logger.debug("Started libtorrent session for %d hops on port %d", hops, ltsession.listen_port())
        self.lt_session_shutdown_ready[hops] = False

        return ltsession

    def has_session(self, hops=0):
        return hops in self.ltsessions

    def get_session(self, hops=0):
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.create_session(hops)

        return self.ltsessions[hops]

    def set_proxy_settings(self, ltsession, ptype, server=None, auth=None):
        """
        Apply the proxy settings to a libtorrent session. This mechanism changed significantly in libtorrent 1.1.0.
        """
        settings = {}
        settings["proxy_type"] = ptype
        settings["proxy_hostnames"] = True
        settings["proxy_peer_connections"] = True
        if server and server[0] and server[1]:
            settings["proxy_hostname"] = server[0]
            settings["proxy_port"] = int(server[1])
        if auth:
            settings["proxy_username"] = auth[0]
            settings["proxy_password"] = auth[1]
        self.set_session_settings(ltsession, settings)

    def set_max_connections(self, conns, hops=None):
        self._map_call_on_ltsessions(hops, 'set_max_connections', conns)

    def set_upload_rate_limit(self, rate, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'upload_rate_limit': libtorrent_rate, 'outgoing_port': 0, 'num_outgoing_ports': 1}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_upload_rate_limit(self, hops=None):
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.get_session(hops).upload_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def set_download_rate_limit(self, rate, hops=None):
        libtorrent_rate = int(-1 if rate == 0 else (1 if rate == -1 else rate * 1024))

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {'download_rate_limit': libtorrent_rate}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_download_rate_limit(self, hops=0):
        libtorrent_rate = self.get_session(hops).download_rate_limit()
        return 0 if libtorrent_rate == -1 else (-1 if libtorrent_rate == 1 else libtorrent_rate / 1024)

    def process_alert(self, alert, hops=0):
        alert_type = alert.__class__.__name__

        # Periodically, libtorrent will send us a state_update_alert, which contains the torrent status of
        # all torrents changed since the last time we received this alert.
        if alert_type == 'state_update_alert':
            for status in alert.status:
                infohash = unhexlify(str(status.info_hash))
                if infohash not in self.downloads:
                    self._logger.debug("Got state_update for unknown torrent %s", hexlify(infohash))
                    continue
                self.downloads[infohash].update_lt_status(status)

        infohash = unhexlify(str(alert.handle.info_hash() if hasattr(alert, 'handle') and alert.handle.is_valid()
                                 else getattr(alert, 'info_hash', '')))
        download = self.downloads.get(infohash)
        if download:
            is_process_alert = (download.handle and download.handle.is_valid()) \
                or (not download.handle and alert_type == 'add_torrent_alert') \
                or (download.handle and alert_type == 'torrent_removed_alert')
            if is_process_alert:
                download.process_alert(alert, alert_type)
            else:
                self._logger.debug("Got alert for download without handle %s: %s", hexlify(infohash), alert)
        elif infohash:
            self._logger.debug("Got alert for unknown download %s: %s", hexlify(infohash), alert)

        if alert_type == 'listen_succeeded_alert':
            # The ``port`` attribute was added in libtorrent 1.1.14.
            # Older versions (most notably libtorrent 1.1.13 - the default  on Ubuntu 20.04) do not have this attribute.
            # We use the now-deprecated ``endpoint`` attribute for these older versions.
            self.listen_ports[hops] = getattr(alert, "port", alert.endpoint[1])

        elif alert_type == 'peer_disconnected_alert' and self.notifier:
            self.notifier.notify(NTFY.PEER_DISCONNECTED_EVENT, alert.pid.to_bytes())

        elif alert_type == 'session_stats_alert':
            queued_disk_jobs = alert.values['disk.queued_disk_jobs']
            queued_write_bytes = alert.values['disk.queued_write_bytes']
            num_write_jobs = alert.values['disk.num_write_jobs']

            if queued_disk_jobs == queued_write_bytes == num_write_jobs == 0:
                self.lt_session_shutdown_ready[hops] = True

            if self.session_stats_callback:
                self.session_stats_callback(alert)

        elif alert_type == "dht_pkt_alert":
            # Unfortunately, the Python bindings don't have a direction attribute.
            # So, we'll have to resort to using the string representation of the alert instead.
            incoming = str(alert).startswith('<==')
            decoded = bdecode_compat(alert.pkt_buf)
            if not decoded:
                return

            # We are sending a raw DHT message - notify the DHTHealthManager of the outstanding request.
            if not incoming and decoded.get(b'y') == b'q' \
                    and decoded.get(b'q') == b'get_peers' and decoded[b'a'].get(b'scrape') == 1:
                self.dht_health_manager.requesting_bloomfilters(decoded[b't'],
                                                                decoded[b'a'][b'info_hash'])

            # We received a raw DHT message - decode it and check whether it is a BEP33 message.
            if incoming and b'r' in decoded and b'BFsd' in decoded[b'r'] and b'BFpe' in decoded[b'r']:
                self.dht_health_manager.received_bloomfilters(decoded[b't'],
                                                              bytearray(decoded[b'r'][b'BFsd']),
                                                              bytearray(decoded[b'r'][b'BFpe']))

    def update_ip_filter(self, lt_session, ip_addresses):
        self._logger.debug('Updating IP filter %s', ip_addresses)
        ip_filter = lt.ip_filter()
        ip_filter.add_rule('0.0.0.0', '255.255.255.255', 1)
        for ip in ip_addresses:
            ip_filter.add_rule(ip, ip, 0)
        lt_session.set_ip_filter(ip_filter)

    async def get_metainfo(self, infohash, timeout=30, hops=None, url=None):
        """
        Lookup metainfo for a given infohash. The mechanism works by joining the swarm for the infohash connecting
        to a few peers, and downloading the metadata for the torrent.
        :param infohash: The (binary) infohash to lookup metainfo for.
        :param timeout: A timeout in seconds.
        :param hops: the number of tunnel hops to use for this lookup. If None, use config default.
        :param url: Optional URL. Can contain trackers info, etc.
        :return: The metainfo
        """
        infohash_hex = hexlify(infohash)
        if infohash in self.metainfo_cache:
            self._logger.info('Returning metainfo from cache for %s', infohash_hex)
            return self.metainfo_cache[infohash]['meta_info']

        self._logger.info('Trying to fetch metainfo for %s', infohash_hex)
        if infohash in self.metainfo_requests:
            download = self.metainfo_requests[infohash][0]
            self.metainfo_requests[infohash][1] += 1
        elif infohash in self.downloads:
            download = self.downloads[infohash]
        else:
            tdef = TorrentDefNoMetainfo(infohash, 'metainfo request', url=url)
            dcfg = DownloadConfig()
            dcfg.set_hops(hops or self.download_defaults.number_hops)
            dcfg.set_upload_mode(True)  # Upload mode should prevent libtorrent from creating files
            dcfg.set_dest_dir(self.metadata_tmpdir)
            try:
                download = self.start_download(tdef=tdef, config=dcfg, hidden=True, checkpoint_disabled=True)
            except TypeError:
                return
            self.metainfo_requests[infohash] = [download, 1]

        try:
            metainfo = download.tdef.get_metainfo() or await wait_for(shield(download.future_metainfo), timeout)
            self._logger.info('Successfully retrieved metainfo for %s', infohash_hex)
            self.metainfo_cache[infohash] = {'time': timemod.time(), 'meta_info': metainfo}
        except (CancelledError, asyncio.TimeoutError):
            metainfo = None
            self._logger.info('Failed to retrieve metainfo for %s', infohash_hex)

        if infohash in self.metainfo_requests:
            self.metainfo_requests[infohash][1] -= 1
            if self.metainfo_requests[infohash][1] <= 0:
                await self.remove_download(download, remove_content=True)
                self.metainfo_requests.pop(infohash)

        return metainfo

    def _task_cleanup_metainfo_cache(self):
        oldest_time = timemod.time() - METAINFO_CACHE_PERIOD

        for info_hash, cache_entry in list(self.metainfo_cache.items()):
            last_time = cache_entry['time']
            if last_time < oldest_time:
                del self.metainfo_cache[info_hash]

    def _request_torrent_updates(self):
        for ltsession in self.ltsessions.values():
            if ltsession:
                ltsession.post_torrent_updates(0xffffffff)

    def _task_process_alerts(self):
        for hops, ltsession in list(self.ltsessions.items()):
            if ltsession:
                for alert in ltsession.pop_alerts():
                    self.process_alert(alert, hops=hops)

    def _map_call_on_ltsessions(self, hops, funcname, *args, **kwargs):
        if hops is None:
            for session in self.ltsessions.values():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    async def start_download_from_uri(self, uri, config=None):
        if uri.startswith("http"):
            tdef = await TorrentDef.load_from_url(uri)
            return self.start_download(tdef=tdef, config=config)
        if uri.startswith("magnet:"):
            name, infohash, _ = parse_magnetlink(uri)
            if infohash is None:
                raise RuntimeError("Missing infohash")
            if infohash in self.metainfo_cache:
                tdef = TorrentDef.load_from_dict(self.metainfo_cache[infohash]['meta_info'])
            else:
                tdef = TorrentDefNoMetainfo(infohash, "Unknown name" if name is None else name, url=uri)
            return self.start_download(tdef=tdef, config=config)
        if uri.startswith("file:"):
            argument = uri_to_path(uri)
            return self.start_download(torrent_file=argument, config=config)
        raise Exception("invalid uri")

    def start_download(self, torrent_file=None, tdef=None, config=None, checkpoint_disabled=False, hidden=False):
        self._logger.debug("Starting download: filename: %s, torrent def: %s", torrent_file, tdef)

        # the priority of the parameters is: (1) tdef, (2) torrent_file.
        # so if we have tdef, and torrent_file will be ignored, and so on.
        if tdef is None:
            if torrent_file is None:
                raise ValueError("Torrent file must be provided if tdef is not given")
            # try to get the torrent from the given torrent file
            tdef = TorrentDef.load(torrent_file)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        config = config or DownloadConfig()
        infohash = tdef.get_infohash()
        download = self.get_download(infohash)

        if download and infohash not in self.metainfo_requests:
            new_trackers = list(set(tdef.get_trackers_as_single_tuple()) -
                                set(download.get_def().get_trackers_as_single_tuple()))
            if new_trackers:
                self.update_trackers(tdef.get_infohash(), new_trackers)
            return download

        # Create the destination directory if it does not exist yet
        try:
            if not config.get_dest_dir().is_dir():
                os.makedirs(config.get_dest_dir())
        except OSError:
            self._logger.error("Unable to create the download destination directory.")

        if config.get_time_added() == 0:
            config.set_time_added(int(timemod.time()))

        # Create the download
        download = Download(tdef=tdef,
                            config=config,
                            download_defaults=self.download_defaults,
                            checkpoint_disabled=checkpoint_disabled,
                            hidden=hidden or config.get_bootstrap_download(),
                            notifier=self.notifier,
                            state_dir=self.state_dir,
                            download_manager=self,
                            dummy=self.dummy_mode)
        atp = download.get_atp()
        # Keep metainfo downloads in self.downloads for now because we will need to remove it later,
        # and removing the download at this point will stop us from receiving any further alerts.
        if infohash not in self.metainfo_requests or self.metainfo_requests[infohash][0] == download:
            self.downloads[infohash] = download
        if not self.dummy_mode:
            self.start_handle(download, atp)
        return download

    @task
    async def start_handle(self, download, atp):
        self._logger.info(f"Start handle. Download: {download}. Atp: {atp}")

        ltsession = self.get_session(download.config.get_hops())
        infohash = download.get_def().get_infohash()

        if infohash in self.metainfo_requests and self.metainfo_requests[infohash][0] != download:
            self._logger.info("Cancelling metainfo request(s) for infohash:%s", hexlify(infohash))
            metainfo_dl, _ = self.metainfo_requests.pop(infohash)
            # Leave the checkpoint. Any checkpoint that exists will belong to the download we are currently starting.
            await self.remove_download(metainfo_dl, remove_content=True, remove_checkpoint=False)
            self.downloads[infohash] = download

        known = {unhexlify(str(h.info_hash())): h for h in ltsession.get_torrents()}
        existing_handle = known.get(infohash)
        if existing_handle:
            # Reuse existing handle
            self._logger.debug("Reusing handle %s", hexlify(infohash))
            download.post_alert('add_torrent_alert', dict(handle=existing_handle))
        else:
            # Otherwise, add it anew
            self._logger.debug("Adding handle %s", hexlify(infohash))
            # To prevent flooding the DHT with a short burst of queries and triggering
            # flood protection, we postpone adding torrents until we get enough DHT peers.
            # The asynchronous wait should be done as close as possible to the actual
            # Libtorrent calls, so the higher-level download-adding logic does not block.
            # Otherwise, e.g. if added to the Session init sequence, this results in startup
            # time increasing by 10-20 seconds.
            # See https://github.com/Tribler/tribler/issues/5319
            if self.dht_readiness_timeout > 0 and self._dht_ready_task is not None:
                try:
                    await wait_for(shield(self._dht_ready_task), timeout=self.dht_readiness_timeout)
                except asyncio.TimeoutError:
                    self._logger.warning("Timeout waiting for libtorrent DHT getting enough peers")
            ltsession.async_add_torrent(encode_atp(atp))
        return await download.future_added

    def get_libtorrent_version(self):
        try:
            return lt.__version__
        except AttributeError:
            return lt.version

    def set_session_settings(self, lt_session, new_settings):
        """
        Apply/set new sessions in a libtorrent session.
        :param lt_session: The libtorrent session to apply the settings to.
        :param new_settings: The new settings to apply.
        """

        # Keeping a copy of the settings because subsequent calls to get_settings are likely to fail
        # when libtorrent will try to decode peer_fingerprint to unicode.
        if lt_session not in self.ltsettings:
            self.ltsettings[lt_session] = lt_session.get_settings()
        self.ltsettings[lt_session].update(new_settings)

        try:
            if hasattr(lt_session, "apply_settings"):
                lt_session.apply_settings(new_settings)
            else:
                lt_session.set_settings(new_settings)
        except OverflowError:
            raise OverflowError(f"Overflow error when setting libtorrent sessions with settings: {new_settings}")

    def get_session_settings(self, lt_session):
        return deepcopy(self.ltsettings.get(lt_session, {}))

    def update_max_rates_from_config(self):
        """
        Set the maximum download and maximum upload rate limits with the value in the config.

        This is the extra step necessary to apply a new maximum download/upload rate setting.
        :return:
        """
        for lt_session in self.ltsessions.values():
            rate = DownloadManager.get_libtorrent_max_upload_rate(self.config)
            download_rate = DownloadManager.get_libtorrent_max_download_rate(self.config)
            settings = {'download_rate_limit': download_rate,
                        'upload_rate_limit': rate}
            self.set_session_settings(lt_session, settings)

    def post_session_stats(self, hops=None):
        for ltsession in self.ltsessions.values() if hops is None else [self.ltsessions[hops]]:
            if hasattr(ltsession, "post_session_stats"):
                ltsession.post_session_stats()

    async def remove_download(self, download, remove_content=False, remove_checkpoint=True):
        infohash = download.get_def().get_infohash()
        handle = download.handle

        # Note that the following block of code needs to be able to deal with multiple simultaneous
        # calls using the same download object. We need to make sure that we don't return without
        # the removal having finished.
        if handle:
            if handle.is_valid():
                if download.stream is not None:
                    download.stream.disable()
                self._logger.debug("Removing handle %s", hexlify(infohash))
                ltsession = self.get_session(download.config.get_hops())
                ltsession.remove_torrent(handle, int(remove_content))
            # We need to wait even if the handle is invalid. It's important to synchronize
            # here because the upcoming call to shutdown will also cancel future_removed.
            await download.future_removed
        else:
            self._logger.debug("Cannot remove handle %s because it does not exists", hexlify(infohash))
        await download.shutdown()

        if infohash in self.downloads and self.downloads[infohash] == download:
            self.downloads.pop(infohash)
            if remove_checkpoint:
                self.remove_config(infohash)
        else:
            self._logger.debug("Cannot remove unknown download")

    def get_download(self, infohash):
        return self.downloads.get(infohash, None)

    def get_downloads(self):
        return list(self.downloads.values())

    def get_channel_downloads(self):
        return [download for download in self.downloads.values() if download.config.get_channel_download()]

    def download_exists(self, infohash):
        return infohash in self.downloads

    async def update_hops(self, download, new_hops):
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = hexlify(download.tdef.get_infohash())
        self._logger.info("Updating the amount of hops of download %s", infohash)
        await download.save_resume_data()
        await self.remove_download(download)

        # copy the old download_config and change the hop count
        config = download.config.copy()
        config.set_hops(new_hops)
        # If the user wants to change the hop count to 0, don't automatically bump this up to 1 anymore
        config.set_safe_seeding(False)

        self.start_download(tdef=download.tdef, config=config)

    def update_trackers(self, infohash, trackers):
        """ Update the trackers for a download.
        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls.
        """
        download = self.get_download(infohash)
        if download:
            old_def = download.get_def()
            old_trackers = old_def.get_trackers_as_single_tuple()
            new_trackers = list(set(trackers) - set(old_trackers))
            all_trackers = list(old_trackers) + new_trackers

            if new_trackers:
                # Add new trackers to the download
                download.add_trackers(new_trackers)

                # Create a new TorrentDef
                if isinstance(old_def, TorrentDefNoMetainfo):
                    new_def = TorrentDefNoMetainfo(old_def.get_infohash(), old_def.get_name(),
                                                   download.get_magnet_link())
                else:
                    metainfo = old_def.get_metainfo()
                    if len(all_trackers) > 1:
                        metainfo["announce-list"] = [all_trackers]
                    else:
                        metainfo["announce"] = all_trackers[0]
                    new_def = TorrentDef.load_from_dict(metainfo)

                # Set TorrentDef + checkpoint
                download.set_def(new_def)
                download.checkpoint()

    def set_download_states_callback(self, user_callback, interval=1.0):
        """
        Set the download state callback. Remove any old callback if it's present.
        Calls user_callback with a list of
        DownloadStates, one for each Download in the Session as first argument.
        The user_callback must return a tuple (when, getpeerlist) that indicates
        when to invoke the callback again (as a number of seconds from now,
        or < 0.0 if not at all) and whether to also include the details of
        the connected peers in the DownloadStates on that next call.

        :param user_callback: a function adhering to the above spec
        :param interval: time in between the download states callback's
        """
        self._logger.debug("Starting the download state callback with interval %f", interval)
        self.replace_task("download_states_lc", self._invoke_states_cb, user_callback, interval=interval)

    def stop_download_states_callback(self):
        return self.cancel_pending_task("download_states_lc")

    async def _invoke_states_cb(self, callback):
        """
        Invoke the download states callback with a list of the download states.
        """
        result = callback([download.get_state() for download in self.downloads.values()])
        if iscoroutine(result):
            await result

    async def sesscb_states_callback(self, states_list):
        """
        This method is periodically (every second) called with a list of the download states of the active downloads.
        """
        # TODO: refactor this method. It is too long and tightly coupled with higher-level modules.
        self.state_cb_count += 1

        for ds in states_list:
            download = ds.get_download()
            infohash = download.get_def().get_infohash()

            if ds.get_status() == DLSTATUS_SEEDING:
                if download.config.get_hops() == 0 and download.config.get_safe_seeding():
                    # Re-add the download with anonymity enabled
                    hops = self.download_defaults.number_hops
                    await self.update_hops(download, hops)

            # Check the peers of this download every five seconds and add them to the payout manager when
            # this peer runs a Tribler instance
            if self.state_cb_count % 5 == 0 and download.config.get_hops() == 0 and self.notifier:
                for peer in download.get_peerlist():
                    if str(peer["extended_version"]).startswith('Tribler'):
                        self.notifier.notify(NTFY.TRIBLER_TORRENT_PEER_UPDATE,
                                             unhexlify(peer["id"]), infohash, peer["dtotal"])

        if self.state_cb_count % 4 == 0:
            self._last_states_list = states_list

    def get_last_download_states(self):
        return self._last_states_list

    async def load_checkpoints(self):
        for filename in self.get_checkpoint_dir().glob('*.conf'):
            self.load_checkpoint(filename)
            await sleep(.01)

    def load_checkpoint(self, filename):
        try:
            config = DownloadConfig.load(filename)
        except Exception:
            self._logger.exception("Could not open checkpoint file %s", filename)
            return

        metainfo = config.get_metainfo()
        if not metainfo:
            self._logger.error("Could not resume checkpoint %s; metainfo not found", filename)
            return
        if not isinstance(metainfo, dict):
            self._logger.error("Could not resume checkpoint %s; metainfo is not dict %s %s",
                               filename, type(metainfo), repr(metainfo))
            return

        try:
            url = metainfo.get(b'url', None)
            url = url.decode('utf-8') if url else url
            tdef = (TorrentDefNoMetainfo(metainfo[b'infohash'], metainfo[b'name'], url)
                    if b'infohash' in metainfo else TorrentDef.load_from_dict(metainfo))
        except (KeyError, ValueError) as e:
            self._logger.exception("Could not restore tdef from metainfo dict: %s %s ", e, metainfo)
            return

        if config.get_bootstrap_download():
            # In case the download is marked as bootstrap, remove it if its infohash does not
            # match the configured bootstrap infohash
            if hexlify(tdef.get_infohash()) != self.bootstrap_infohash:
                self.remove_config(tdef.get_infohash())
                return

        config.state_dir = self.state_dir
        if config.get_dest_dir() == '':  # removed torrent ignoring
            self._logger.info("Removing checkpoint %s destdir is %s", filename, config.get_dest_dir())
            os.remove(filename)
            return

        try:
            if self.download_exists(tdef.get_infohash()):
                self._logger.info("Not resuming checkpoint because download has already been added")
            else:
                self.start_download(tdef=tdef, config=config)
        except Exception:
            self._logger.exception("Not resume checkpoint due to exception while adding download")

    def remove_config(self, infohash):
        if infohash not in self.downloads:
            try:
                basename = hexlify(infohash) + '.conf'
                filename = self.get_checkpoint_dir() / basename
                self._logger.debug("Removing download checkpoint %s", filename)
                if os.access(filename, os.F_OK):
                    os.remove(filename)
            except:
                # Show must go on
                self._logger.exception("Could not remove state")
        else:
            self._logger.warning("Download is back, restarted? Cancelling removal! %s", hexlify(infohash))

    def get_checkpoint_dir(self):
        """
        Returns the directory in which to checkpoint the Downloads in this Session.
        """
        return self.state_dir / STATEDIR_CHECKPOINT_DIR

    @staticmethod
    async def create_torrent_file(file_path_list, params=None):
        """
        Creates a torrent file.

        :param file_path_list: files to add in torrent file
        :param params: optional parameters for torrent file
        :return: a Deferred that fires when the torrent file has been created
        """
        return await asyncio.get_event_loop().run_in_executor(None, torrent_utils.create_torrent_file,
                                                              file_path_list, params or {})

    def get_downloads_by_name(self, torrent_name, channels_only=False):
        downloads = (self.get_channel_downloads() if channels_only else self.get_downloads())
        return [d for d in downloads if d.get_def().get_name_utf8() == torrent_name]

    @staticmethod
    def set_libtorrent_proxy_settings(config: LibtorrentSettings, proxy_type, server=None, auth=None):
        """
        Set which proxy LibTorrent should use (default = 0).

        :param config: libtorrent config
        :param proxy_type: int (0 = no proxy server,
                                1 = SOCKS4,
                                2 = SOCKS5,
                                3 = SOCKS5 + auth,
                                4 = HTTP,
                                5 = HTTP + auth)
        :param server: (host, port) tuple or None
        :param auth: (username, password) tuple or None
        """
        config.proxy_type = proxy_type
        config.proxy_server = server if proxy_type else ':'
        config.proxy_auth = auth if proxy_type in [3, 5] else ':'

    @staticmethod
    def get_libtorrent_proxy_settings(config: LibtorrentSettings):
        proxy_server = str(config.proxy_server)
        proxy_server = proxy_server.split(':') if proxy_server else ['', '']

        proxy_auth = str(config.proxy_auth)
        proxy_auth = proxy_auth.split(':') if proxy_auth else ['', '']

        return config.proxy_type, proxy_server, proxy_auth

    @staticmethod
    def get_libtorrent_max_upload_rate(config: LibtorrentSettings):
        """
        Gets the maximum upload rate (kB / s).

        :return: the maximum upload rate in kB / s
        """
        return min(config.max_upload_rate, MAX_LIBTORRENT_RATE_LIMIT)

    @staticmethod
    def get_libtorrent_max_download_rate(config: LibtorrentSettings):
        """
        Gets the maximum download rate (kB / s).

        :return: the maximum download rate in kB / s
        """
        return min(config.max_download_rate, MAX_LIBTORRENT_RATE_LIMIT)
