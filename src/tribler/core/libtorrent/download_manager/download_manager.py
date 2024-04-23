"""
A wrapper around libtorrent.

Author(s): Egbert Bouman
"""
from __future__ import annotations

import asyncio
import logging
import os
import time as timemod
from asyncio import CancelledError, gather, iscoroutine, shield, sleep, wait_for
from binascii import hexlify, unhexlify
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List

import libtorrent as lt
from configobj import ConfigObj
from ipv8.taskmanager import TaskManager
from validate import Validator
from yarl import URL

from tribler.core.libtorrent import torrents
from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.libtorrent.uris import unshorten, url_to_path
from tribler.core.notifier import Notification, Notifier

if TYPE_CHECKING:
    from tribler.core.libtorrent.download_manager.dht_health_manager import DHTHealthManager
    from tribler.core.libtorrent.torrents import TorrentFileResult
    from tribler.tribler_config import TriblerConfigManager

SOCKS5_PROXY_DEF = 2

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DEFAULT_DHT_ROUTERS = [
    ("dht.libtorrent.org", 25401),
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
]
DEFAULT_LT_EXTENSIONS = [
    lt.create_ut_metadata_plugin,
    lt.create_ut_pex_plugin,
    lt.create_smart_ban_plugin
]

logger = logging.getLogger(__name__)


def encode_atp(atp: dict) -> dict:
    """
    Encode the "Add Torrent Params" dictionary to only include bytes, instead of strings and Paths.
    """
    for k, v in atp.items():
        if isinstance(v, str):
            atp[k] = v.encode()
        elif isinstance(v, Path):
            atp[k] = str(v)
    return atp


class DownloadManager(TaskManager):
    """
    The manager of all downloads.
    """

    def __init__(self, config: TriblerConfigManager, notifier: Notifier,
                 metadata_tmpdir: TemporaryDirectory | None = None) -> None:
        """
        Create a new download manager.
        """
        super().__init__()
        self.config = config

        self.state_dir = Path(config.get("state_dir"))
        self.ltsettings = {}  # Stores a copy of the settings dict for each libtorrent session
        self.ltsessions = {}
        self.dht_health_manager: DHTHealthManager | None = None
        self.listen_ports: dict[int, dict[str, int]] = defaultdict(dict)

        self.socks_listen_ports = config.get("libtorrent/socks_listen_ports")

        self.notifier = notifier

        self.set_upload_rate_limit(0)
        self.set_download_rate_limit(0)

        self.downloads: Dict[bytes, Download] = {}

        self.checkpoint_directory = (self.state_dir / "dlcheckpoints")
        self.checkpoints_count = None
        self.checkpoints_loaded = 0
        self.all_checkpoints_are_loaded = False

        self.metadata_tmpdir = metadata_tmpdir or TemporaryDirectory(suffix="tribler_metainfo_tmpdir")
        # Dictionary that maps infohashes to download instances. These include only downloads that have
        # been made specifically for fetching metainfo, and will be removed afterwards.
        self.metainfo_requests = {}
        self.metainfo_cache = {}  # Dictionary that maps infohashes to cached metainfo items

        self.default_alert_mask = lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | \
                                  lt.alert.category_t.storage_notification | lt.alert.category_t.performance_warning | \
                                  lt.alert.category_t.tracker_notification | lt.alert.category_t.debug_notification
        self.session_stats_callback: Callable | None = None
        self.state_cb_count = 0

        # Status of libtorrent session to indicate if it can safely close and no pending writes to disk exists.
        self.lt_session_shutdown_ready = {}
        self.dht_ready_task = None
        self.dht_readiness_timeout = config.get("libtorrent/dht_readiness_timeout")
        self._last_states_list = []

    def is_shutting_down(self) -> bool:
        """
        Whether the download manager is currently shutting down.
        """
        return self._shutdown

    @staticmethod
    def convert_rate(rate: int) -> int:
        """
        Rate conversion due to the fact that we had a different system with Swift
        and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes.
        """
        if rate == 0:
            return -1
        if rate == -1:
            return 1
        return rate * 1024

    @staticmethod
    def reverse_convert_rate(rate: int) -> int:
        """
        Rate conversion due to the fact that we had a different system with Swift
        and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes.
        """
        if rate == -1:
            return 0
        if rate == 1:
            return -1
        return rate // 1024

    async def _check_dht_ready(self, min_dht_peers: int = 60) -> None:
        """
        Checks whether we got enough DHT peers. If the number of DHT peers is low,
        checking for a bunch of torrents in a short period of time may result in several consecutive requests
        sent to the same peers. This can trigger those peers' flood protection mechanism,
        which results in DHT checks stuck for hours.

        See https://github.com/Tribler/tribler/issues/5319
        """
        while not (self.get_session() and self.get_session().status().dht_nodes > min_dht_peers):
            await asyncio.sleep(1)

    def initialize(self) -> None:
        """
        Initialize the directory structure, launch the periodic tasks and start libtorrent background processes.
        """
        # Create the checkpoints directory
        self.checkpoint_directory.mkdir(exist_ok=True)

        # Start upnp
        if self.config.get("libtorrent/upnp"):
            self.get_session().start_upnp()

        # Register tasks
        self.register_task("process_alerts", self._task_process_alerts, interval=1, ignore=(Exception, ))
        if self.dht_readiness_timeout > 0 and self.config.get("libtorrent/dht"):
            self.dht_ready_task = self.register_task("check_dht_ready", self._check_dht_ready)
        self.register_task("request_torrent_updates", self._request_torrent_updates, interval=1)
        self.register_task("task_cleanup_metacache", self._task_cleanup_metainfo_cache, interval=60, delay=0)

        self.set_download_states_callback(self.sesscb_states_callback)

    def start(self) -> None:
        """
        Start loading the checkpoints from disk.
        """
        self.register_task("start", self.load_checkpoints)

    def notify_shutdown_state(self, state: str) -> None:
        """
        Call the notifier to signal a shutdown state update.
        """
        logger.info("Notify shutdown state: %s", state)
        self.notifier.notify(Notification.tribler_shutdown_state, state=state)

    async def shutdown(self, timeout: int = 30) -> None:
        """
        Shut down all pending tasks and background tasks.
        """
        logger.info("Shutting down...")
        self.cancel_pending_task("start")
        self.cancel_pending_task("download_states_lc")
        if self.downloads:
            logger.info("Stopping downloads...")

            self.notify_shutdown_state("Checkpointing Downloads...")
            await gather(*[download.stop() for download in self.downloads.values()], return_exceptions=True)
            self.notify_shutdown_state("Shutting down Downloads...")
            await gather(*[download.shutdown() for download in self.downloads.values()], return_exceptions=True)

        self.notify_shutdown_state("Shutting down LibTorrent Manager...")
        # If libtorrent session has pending disk io, wait until timeout (default: 30 seconds) to let it finish.
        # In between ask for session stats to check if state is clean for shutdown.
        while not self.is_shutdown_ready() and timeout >= 1:
            self.notify_shutdown_state("Waiting for LibTorrent to finish...")
            self.post_session_stats()
            timeout -= 1
            await asyncio.sleep(1)

        logger.info("Awaiting shutdown task manager...")
        await self.shutdown_task_manager()

        if self.dht_health_manager:
            await self.dht_health_manager.shutdown_task_manager()

        # Save libtorrent state
        if self.has_session():
            logger.info("Saving state...")
            with open(self.state_dir / LTSTATE_FILENAME, "wb") as ltstate_file:  # noqa: ASYNC101
                ltstate_file.write(lt.bencode(self.get_session().save_state()))

        if self.has_session() and self.config.get("libtorrent/upnp"):
            logger.info("Stopping upnp...")
            self.get_session().stop_upnp()

        # Remove metadata temporary directory
        if self.metadata_tmpdir:
            logger.info("Removing temp directory...")
            self.metadata_tmpdir.cleanup()
            self.metadata_tmpdir = None
        logger.info("Shutdown completed")

    def is_shutdown_ready(self) -> bool:
        """
        Check if the libtorrent shutdown is complete.
        """
        return all(self.lt_session_shutdown_ready.values())

    def create_session(self, hops: int = 0) -> lt.session:  # noqa: PLR0912, PLR0915
        """
        Construct a libtorrent session for the given number of anonymization hops.
        """
        # Due to a bug in Libtorrent 0.16.18, the outgoing_port and num_outgoing_ports value should be set in
        # the settings dictionary
        logger.info("Creating a session")
        settings = {"outgoing_port": 0,
                    "num_outgoing_ports": 1,
                    "allow_multiple_connections_per_ip": 0,
                    "enable_upnp": int(self.config.get("libtorrent/upnp")),
                    "enable_dht": int(self.config.get("libtorrent/dht")),
                    "enable_lsd": int(self.config.get("libtorrent/lsd")),
                    "enable_natpmp": int(self.config.get("libtorrent/natpmp"))}

        # Copy construct so we don't modify the default list
        extensions = list(DEFAULT_LT_EXTENSIONS)

        logger.info("Hops: %d.", hops)

        # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
        fingerprint = ["TL", 0, 0, 0, 0]
        ltsession = lt.session(lt.fingerprint(*fingerprint), flags=0) if hops == 0 else lt.session(flags=0)

        libtorrent_port = self.config.get("libtorrent/port")
        logger.info("Libtorrent port: %d", libtorrent_port)
        if hops == 0:
            settings["user_agent"] = "Tribler/Experimental"
            enable_utp = self.config.get("libtorrent/utp")
            settings["enable_outgoing_utp"] = enable_utp
            settings["enable_incoming_utp"] = enable_utp
            settings["prefer_rc4"] = True
            settings["listen_interfaces"] = f"0.0.0.0:{libtorrent_port or 6881}"
            settings["handshake_client_version"] = "Tribler/Experimental"
        else:
            settings["enable_outgoing_utp"] = True
            settings["enable_incoming_utp"] = True
            settings["enable_outgoing_tcp"] = False
            settings["enable_incoming_tcp"] = False
            settings["anonymous_mode"] = True
            settings["force_proxy"] = True

        self.set_session_settings(ltsession, settings)
        ltsession.set_alert_mask(self.default_alert_mask)

        if hops == 0:
            self.set_proxy_settings(ltsession, *self.get_libtorrent_proxy_settings())
        else:
            self.set_proxy_settings(ltsession, SOCKS5_PROXY_DEF, ("127.0.0.1", self.socks_listen_ports[hops - 1]))

        for extension in extensions:
            ltsession.add_extension(extension)

        # Set listen port & start the DHT
        if hops == 0:
            ltsession.listen_on(libtorrent_port, libtorrent_port + 10)
            try:
                with open(self.state_dir / LTSTATE_FILENAME, "rb") as fp:
                    lt_state = lt.bdecode(fp.read())
                if lt_state is not None:
                    ltsession.load_state(lt_state)
                else:
                    logger.warning("the lt.state appears to be corrupt, writing new data on shutdown")
            except Exception as exc:
                logger.info("could not load libtorrent state, got exception: %s. starting from scratch", repr(exc))
        else:
            rate = DownloadManager.get_libtorrent_max_upload_rate(self.config)
            download_rate = DownloadManager.get_libtorrent_max_download_rate(self.config)
            settings = {"upload_rate_limit": rate,
                        "download_rate_limit": download_rate}
            self.set_session_settings(ltsession, settings)

        if self.config.get("libtorrent/dht"):
            ltsession.start_dht()
            for router in DEFAULT_DHT_ROUTERS:
                ltsession.add_dht_router(*router)
            ltsession.start_lsd()

        logger.info("Started libtorrent session for %d hops on port %d", hops, ltsession.listen_port())
        self.lt_session_shutdown_ready[hops] = False

        return ltsession

    def has_session(self, hops: int = 0) -> bool:
        """
        Check if we have a session for the given number of anonymization hops.
        """
        return hops in self.ltsessions

    def get_session(self, hops: int = 0) -> lt.session:
        """
        Get the session for the given number of anonymization hops.
        """
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.create_session(hops)

        return self.ltsessions[hops]

    def set_proxy_settings(self, ltsession: lt.session, ptype: int, server: tuple[str, str | int] | None = None,
                           auth: tuple[str, str] | None = None) -> None:
        """
        Apply the proxy settings to a libtorrent session. This mechanism changed significantly in libtorrent 1.1.0.
        """
        settings = {}
        settings["proxy_type"] = ptype
        settings["proxy_hostnames"] = True
        settings["proxy_peer_connections"] = True
        if server is not None:
            settings["proxy_hostname"] = server[0]
            settings["proxy_port"] = int(server[1])
        if auth is not None:
            settings["proxy_username"] = auth[0]
            settings["proxy_password"] = auth[1]
        self.set_session_settings(ltsession, settings)

    def set_max_connections(self, conns: int, hops: int | None = None) -> None:
        """
        Set the maximum number of connections for the given hop count.
        """
        self._map_call_on_ltsessions(hops, "set_max_connections", conns)

    def set_upload_rate_limit(self, rate: int) -> None:
        """
        Set the upload rate limit for the given session.
        """
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.convert_rate(rate=rate)

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {"upload_rate_limit": libtorrent_rate, "outgoing_port": 0, "num_outgoing_ports": 1}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_upload_rate_limit(self, hops: int = 0) -> int:
        """
        Get the upload rate limit for the session with the given hop count.
        """
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.get_session(hops).upload_rate_limit()
        return self.reverse_convert_rate(rate=libtorrent_rate)

    def set_download_rate_limit(self, rate: int) -> None:
        """
        Set the download rate limit for the given session.
        """
        libtorrent_rate = self.convert_rate(rate=rate)

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {"download_rate_limit": libtorrent_rate}
        for session in self.ltsessions.values():
            self.set_session_settings(session, settings_dict)

    def get_download_rate_limit(self, hops: int = 0) -> int:
        """
        Get the download rate limit for the session with the given hop count.
        """
        libtorrent_rate = self.get_session(hops=hops).download_rate_limit()
        return self.reverse_convert_rate(rate=libtorrent_rate)

    def process_alert(self, alert, hops: int = 0) -> None:  # noqa: C901, PLR0912
        """
        Process a libtorrent alert.
        """
        alert_type = alert.__class__.__name__

        # Periodically, libtorrent will send us a state_update_alert, which contains the torrent status of
        # all torrents changed since the last time we received this alert.
        if alert_type == "state_update_alert":
            for status in alert.status:
                infohash = status.info_hash.to_bytes()
                if infohash not in self.downloads:
                    logger.debug("Got state_update for unknown torrent %s", hexlify(infohash))
                    continue
                self.downloads[infohash].update_lt_status(status)

        if alert_type == "state_changed_alert":
            infohash = alert.handle.info_hash().to_bytes()
            if infohash not in self.downloads:
                logger.debug("Got state_change for unknown torrent %s", hexlify(infohash))
            else:
                self.downloads[infohash].update_lt_status(alert.handle.status())

        infohash = (alert.handle.info_hash().to_bytes() if hasattr(alert, "handle") and alert.handle.is_valid()
                    else getattr(alert, "info_hash", b""))
        download = self.downloads.get(infohash)
        if download:
            is_process_alert = (download.handle and download.handle.is_valid()) \
                               or (not download.handle and alert_type == "add_torrent_alert") \
                               or (download.handle and alert_type == "torrent_removed_alert")
            if is_process_alert:
                download.process_alert(alert, alert_type)
            else:
                logger.debug("Got alert for download without handle %s: %s", infohash, alert)
        elif infohash:
            logger.debug("Got alert for unknown download %s: %s", infohash, alert)

        if alert_type == "listen_succeeded_alert":
            self.listen_ports[hops][alert.address] = alert.port

        elif alert_type == "peer_disconnected_alert":
            self.notifier.notify(Notification.peer_disconnected, peer_id=alert.pid.to_bytes())

        elif alert_type == "session_stats_alert":
            queued_disk_jobs = alert.values["disk.queued_disk_jobs"]
            queued_write_bytes = alert.values["disk.queued_write_bytes"]
            num_write_jobs = alert.values["disk.num_write_jobs"]
            if queued_disk_jobs == queued_write_bytes == num_write_jobs == 0:
                self.lt_session_shutdown_ready[hops] = True

            if self.session_stats_callback:
                self.session_stats_callback(alert)

        elif alert_type == "dht_pkt_alert":
            # Unfortunately, the Python bindings don't have a direction attribute.
            # So, we'll have to resort to using the string representation of the alert instead.
            incoming = str(alert).startswith("<==")
            decoded = lt.bdecode(alert.pkt_buf)
            if not decoded:
                return

            # We are sending a raw DHT message - notify the DHTHealthManager of the outstanding request.
            if not incoming and decoded.get(b"y") == b"q" \
                    and decoded.get(b"q") == b"get_peers" and decoded[b"a"].get(b"scrape") == 1:
                self.dht_health_manager.requesting_bloomfilters(decoded[b"t"],
                                                                decoded[b"a"][b"info_hash"])

            # We received a raw DHT message - decode it and check whether it is a BEP33 message.
            if incoming and b"r" in decoded and b"BFsd" in decoded[b"r"] and b"BFpe" in decoded[b"r"]:
                self.dht_health_manager.received_bloomfilters(decoded[b"t"],
                                                              bytearray(decoded[b"r"][b"BFsd"]),
                                                              bytearray(decoded[b"r"][b"BFpe"]))

    def update_ip_filter(self, lt_session: lt.session, ip_addresses: Iterable[str]) -> None:
        """
        Add illegal IPs to libtorrent.
        """
        logger.debug("Updating IP filter %s", ip_addresses)
        ip_filter = lt.ip_filter()
        ip_filter.add_rule("0.0.0.0", "255.255.255.255", 1)
        for ip in ip_addresses:
            ip_filter.add_rule(ip, ip, 0)
        lt_session.set_ip_filter(ip_filter)

    async def get_metainfo(self, infohash: bytes, timeout: float = 7, hops: int | None = None,
                           url: str | None = None, raise_errors: bool = False) -> dict | None:
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
            logger.info("Returning metainfo from cache for %s", infohash_hex)
            return self.metainfo_cache[infohash]["meta_info"]

        logger.info("Trying to fetch metainfo for %s", infohash_hex)
        if infohash in self.metainfo_requests:
            download = self.metainfo_requests[infohash][0]
            self.metainfo_requests[infohash][1] += 1
        elif infohash in self.downloads:
            download = self.downloads[infohash]
        else:
            tdef = TorrentDefNoMetainfo(infohash, b"metainfo request", url=url)
            dcfg = DownloadConfig.from_defaults(self.config)
            dcfg.set_hops(hops or self.config.get("libtorrent/download_defaults/number_hops"))
            dcfg.set_upload_mode(True)  # Upload mode should prevent libtorrent from creating files
            dcfg.set_dest_dir(self.metadata_tmpdir.name)
            try:
                download = await self.start_download(tdef=tdef, config=dcfg, hidden=True, checkpoint_disabled=True)
            except TypeError as e:
                logger.warning(e)
                if raise_errors:
                    raise
                return None
            self.metainfo_requests[infohash] = [download, 1]

        try:
            metainfo = download.tdef.get_metainfo() or await wait_for(shield(download.future_metainfo), timeout)
        except (CancelledError, asyncio.TimeoutError) as e:
            logger.warning("%s: %s (timeout=%f)", type(e).__name__, str(e), timeout)
            logger.info("Failed to retrieve metainfo for %s", infohash_hex)
            if raise_errors:
                raise
            return None

        logger.info("Successfully retrieved metainfo for %s", infohash_hex)
        self.metainfo_cache[infohash] = {"time": timemod.time(), "meta_info": metainfo}

        if infohash in self.metainfo_requests:
            self.metainfo_requests[infohash][1] -= 1
            if self.metainfo_requests[infohash][1] <= 0:
                await self.remove_download(download, remove_content=True)
                self.metainfo_requests.pop(infohash, None)

        return metainfo

    def _task_cleanup_metainfo_cache(self) -> None:
        oldest_time = timemod.time() - METAINFO_CACHE_PERIOD

        for info_hash, cache_entry in list(self.metainfo_cache.items()):
            last_time = cache_entry["time"]
            if last_time < oldest_time:
                del self.metainfo_cache[info_hash]

    def _request_torrent_updates(self) -> None:
        for ltsession in self.ltsessions.values():
            if ltsession:
                ltsession.post_torrent_updates(0xffffffff)

    def _task_process_alerts(self) -> None:
        for hops, ltsession in list(self.ltsessions.items()):
            if ltsession:
                for alert in ltsession.pop_alerts():
                    self.process_alert(alert, hops=hops)

    def _map_call_on_ltsessions(self, hops: int | None, funcname: str, *args: Any, **kwargs) -> None:  # noqa: ANN401
        if hops is None:
            for session in self.ltsessions.values():
                getattr(session, funcname)(*args, **kwargs)
        else:
            getattr(self.get_session(hops), funcname)(*args, **kwargs)

    async def start_download_from_uri(self, uri: str, config: DownloadConfig | None = None) -> Download:
        """
        Start a download from the given uri.
        """
        logger.info("Start download from URI: %s", uri)

        uri = await unshorten(uri)
        scheme = URL(uri).scheme

        if scheme in ("http", "https"):
            logger.info("Http(s) scheme detected")
            tdef = await TorrentDef.load_from_url(uri)
            return await self.start_download(tdef=tdef, config=config)
        if scheme == "magnet":
            logger.info("Magnet scheme detected")
            params = lt.parse_magnet_uri(uri)
            try:
                # libtorrent 1.2.19
                name, infohash = params["name"].encode(), params["info_hash"]
            except TypeError:
                # libtorrent 2.0.9
                name = params.name.encode()
                infohash = unhexlify(str(params.info_hash))
            logger.info("Name: %s. Infohash: %s", name, infohash)
            if infohash in self.metainfo_cache:
                logger.info("Metainfo found in cache")
                tdef = TorrentDef.load_from_dict(self.metainfo_cache[infohash]["meta_info"])
            else:
                logger.info("Metainfo not found in cache")
                tdef = TorrentDefNoMetainfo(infohash, name if name else b"Unknown name", url=uri)
            return await self.start_download(tdef=tdef, config=config)
        if scheme == "file":
            logger.info("File scheme detected")
            file = url_to_path(uri)
            return await self.start_download(torrent_file=file, config=config)
        msg = "invalid uri"
        raise Exception(msg)

    async def start_download(self, torrent_file: str | None = None, tdef: TorrentDef | None = None,
                             config: DownloadConfig | None = None,
                             checkpoint_disabled: bool = False, hidden: bool = False) -> Download:
        """
        Start a download from the given information.
        """
        logger.info("Starting download: filename: %s, torrent def: %s", str(torrent_file), str(tdef))
        if config is None:
            config = DownloadConfig.from_defaults(self.config)
            logger.info("Use a default config.")

        # the priority of the parameters is: (1) tdef, (2) torrent_file.
        # so if we have tdef, and torrent_file will be ignored, and so on.
        if tdef is None:
            logger.info("Torrent def is None. Trying to load it from torrent file.")
            if torrent_file is None:
                msg = "Torrent file must be provided if tdef is not given"
                raise ValueError(msg)
            # try to get the torrent from the given torrent file
            tdef = await TorrentDef.load(torrent_file)

        assert tdef is not None, "tdef MUST not be None after loading torrent"

        infohash = tdef.get_infohash()
        download = self.get_download(infohash)

        if download and infohash not in self.metainfo_requests:
            logger.info("Download exists and metainfo is not requested.")
            new_trackers = list(tdef.get_trackers() - download.get_def().get_trackers())
            if new_trackers:
                logger.info("New trackers: %s", str(new_trackers))
                self.update_trackers(tdef.get_infohash(), new_trackers)
            return download

        # Create the destination directory if it does not exist yet
        try:
            destination_directory = config.get_dest_dir()
            if not destination_directory.is_dir():
                logger.info("Destination directory does not exist. Creating it: %s", str(destination_directory))
                os.makedirs(destination_directory)
        except OSError:
            logger.exception("Unable to create the download destination directory.")

        if config.get_time_added() == 0:
            config.set_time_added(int(timemod.time()))

        # Create the download
        download = Download(tdef=tdef,
                            config=config,
                            checkpoint_disabled=checkpoint_disabled,
                            hidden=hidden or config.get_bootstrap_download(),
                            notifier=self.notifier,
                            state_dir=self.state_dir,
                            download_manager=self)
        logger.info("Download created: %s", str(download))
        atp = download.get_atp()
        logger.info("ATP: %s", str({k: v for k, v in atp.items() if k not in ["resume_data"]}))
        # Keep metainfo downloads in self.downloads for now because we will need to remove it later,
        # and removing the download at this point will stop us from receiving any further alerts.
        if infohash not in self.metainfo_requests or self.metainfo_requests[infohash][0] == download:
            logger.info("Metainfo is not requested or download is the first in the queue.")
            self.downloads[infohash] = download
        logger.info("Starting handle.")
        await self.start_handle(download, atp)
        return download

    async def start_handle(self, download: Download, atp: dict) -> None:
        """
        Create and start the libtorrent handle for the given download.
        """
        atp_resume_data_skipped = atp.copy()
        resume_data = atp.get("resume_data")
        if resume_data:
            atp_resume_data_skipped["resume_data"] = "<skipped in log>"
        logger.info("Start handle. Download: %s. Atp: %s", str(download), str(atp_resume_data_skipped))
        if resume_data:
            logger.debug("Download resume data: %s", str(atp["resume_data"]))

        ltsession = self.get_session(download.config.get_hops())
        infohash = download.get_def().get_infohash()

        if infohash in self.metainfo_requests and self.metainfo_requests[infohash][0] != download:
            logger.info("Cancelling metainfo request(s) for infohash:%s", hexlify(infohash))
            metainfo_dl, _ = self.metainfo_requests.pop(infohash)
            # Leave the checkpoint. Any checkpoint that exists will belong to the download we are currently starting.
            await self.remove_download(metainfo_dl, remove_content=True, remove_checkpoint=False)
            self.downloads[infohash] = download

        known = {h.info_hash().to_bytes(): h for h in ltsession.get_torrents()}
        existing_handle = known.get(infohash)
        if existing_handle:
            # Reuse existing handle
            logger.debug("Reusing handle %s", hexlify(infohash))
            download.post_alert("add_torrent_alert", {"handle": existing_handle})
        else:
            # Otherwise, add it anew
            _ = self.replace_task(f"AddTorrent{infohash}", self._async_add_torrent, ltsession, infohash, atp,
                                  ignore=(Exception,))

    async def _async_add_torrent(self, ltsession: lt.session, infohash: bytes , atp: dict) -> None:
        self._logger.debug("Adding handle %s", hexlify(infohash))
        # To prevent flooding the DHT with a short burst of queries and triggering
        # flood protection, we postpone adding torrents until we get enough DHT peers.
        # The asynchronous wait should be done as close as possible to the actual
        # Libtorrent calls, so the higher-level download-adding logic does not block.
        # Otherwise, e.g. if added to the Session init sequence, this results in startup
        # time increasing by 10-20 seconds.
        # See https://github.com/Tribler/tribler/issues/5319
        if self.dht_readiness_timeout > 0 and self.dht_ready_task is not None:
            try:
                await wait_for(shield(self.dht_ready_task), timeout=self.dht_readiness_timeout)
            except asyncio.TimeoutError:
                self._logger.warning("Timeout waiting for libtorrent DHT getting enough peers")
        ltsession.async_add_torrent(encode_atp(atp))

    def get_libtorrent_version(self) -> str:
        """
        Get the libtorrent version.
        """
        try:
            return lt.__version__
        except AttributeError:
            return lt.version

    def set_session_settings(self, lt_session: lt.session, new_settings: dict) -> None:
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
        except OverflowError as e:
            msg = f"Overflow error when setting libtorrent sessions with settings: {new_settings}"
            raise OverflowError(msg) from e

    def get_session_settings(self, lt_session: lt.session) -> dict:
        """
        Get a copy of the libtorrent settings for the given session.
        """
        return deepcopy(self.ltsettings.get(lt_session, {}))

    def update_max_rates_from_config(self) -> None:
        """
        Set the maximum download and maximum upload rate limits with the value in the config.

        This is the extra step necessary to apply a new maximum download/upload rate setting.
        :return:
        """
        for lt_session in self.ltsessions.values():
            rate = DownloadManager.get_libtorrent_max_upload_rate(self.config)
            download_rate = DownloadManager.get_libtorrent_max_download_rate(self.config)
            settings = {"download_rate_limit": download_rate,
                        "upload_rate_limit": rate}
            self.set_session_settings(lt_session, settings)

    def post_session_stats(self) -> None:
        """
        Gather statistics and cause a ``session_stats_alert``.
        """
        logger.info("Post session stats")
        for session in self.ltsessions.values():
            session.post_session_stats()

    async def remove_download(self, download: Download, remove_content: bool = False,
                              remove_checkpoint: bool = True) -> None:
        """
        Remove a download and optionally also remove the downloaded file(s) and checkpoint.
        """
        infohash = download.get_def().get_infohash()
        handle = download.handle

        # Note that the following block of code needs to be able to deal with multiple simultaneous
        # calls using the same download object. We need to make sure that we don't return without
        # the removal having finished.
        if handle:
            if handle.is_valid():
                if download.stream is not None:
                    download.stream.disable()
                logger.debug("Removing handle %s", hexlify(infohash))
                ltsession = self.get_session(download.config.get_hops())
                ltsession.remove_torrent(handle, int(remove_content))
        else:
            logger.debug("Cannot remove handle %s because it does not exists", hexlify(infohash))
        await download.shutdown()

        if infohash in self.downloads and self.downloads[infohash] == download:
            self.downloads.pop(infohash)
            if remove_checkpoint:
                self.remove_config(infohash)
        else:
            logger.debug("Cannot remove unknown download")

    def get_download(self, infohash: bytes) -> Download | None:
        """
        Get the download belonging to a given infohash.
        """
        return self.downloads.get(infohash, None)

    def get_downloads(self) -> List[Download]:
        """
        Get a list of all known downloads.
        """
        return list(self.downloads.values())

    def download_exists(self, infohash: bytes) -> bool:
        """
        Check if there is a download with a given infohash.
        """
        return infohash in self.downloads

    async def update_hops(self, download: Download, new_hops: int) -> None:
        """
        Update the amount of hops for a specified download. This can be done on runtime.
        """
        infohash = hexlify(download.tdef.get_infohash())
        logger.info("Updating the amount of hops of download %s", infohash)
        await download.save_resume_data()
        await self.remove_download(download)

        # copy the old download_config and change the hop count
        config = download.config.copy()
        config.set_hops(new_hops)
        # If the user wants to change the hop count to 0, don't automatically bump this up to 1 anymore
        config.set_safe_seeding(False)

        await self.start_download(tdef=download.tdef, config=config)

    def update_trackers(self, infohash: bytes, trackers: list[str]) -> None:
        """
        Update the trackers for a download.

        :param infohash: infohash of the torrent that needs to be updated
        :param trackers: A list of tracker urls.
        """
        download = self.get_download(infohash)
        if download:
            old_def = download.get_def()
            old_trackers = old_def.get_trackers()
            new_trackers = list(set(trackers) - old_trackers)
            all_trackers = [*old_trackers, *new_trackers]

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
                        metainfo[b"announce-list"] = [[tracker] for tracker in all_trackers]
                        metainfo.pop(b"announce", None)
                    else:
                        metainfo[b"announce"] = all_trackers[0]
                    new_def = TorrentDef.load_from_dict(metainfo)

                # Set TorrentDef + checkpoint
                download.set_def(new_def)
                download.checkpoint()

    def set_download_states_callback(self, user_callback, interval: float = 1.0) -> None:
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
        logger.debug("Starting the download state callback with interval %f", interval)
        self.replace_task("download_states_lc", self._invoke_states_cb, user_callback, interval=interval)

    async def _invoke_states_cb(self, callback) -> None:
        """
        Invoke the download states callback with a list of the download states.
        """
        result = callback([download.get_state() for download in self.downloads.values()])
        if iscoroutine(result):
            await result

    async def sesscb_states_callback(self, states_list: list[DownloadState]) -> None:
        """
        This method is periodically (every second) called with a list of the download states of the active downloads.
        """
        self.state_cb_count += 1

        for ds in states_list:
            download = ds.get_download()
            infohash = download.get_def().get_infohash()

            if (ds.get_status() == DownloadStatus.SEEDING and download.config.get_hops() == 0
                    and download.config.get_safe_seeding()):
                # Re-add the download with anonymity enabled
                hops = self.config.get("libtorrent/download_defaults/number_hops")
                await self.update_hops(download, hops)

            # Check the peers of this download every five seconds and add them to the payout manager when
            # this peer runs a Tribler instance
            if self.state_cb_count % 5 == 0 and download.config.get_hops() == 0 and self.notifier:
                for peer in download.get_peer_list():
                    if str(peer["extended_version"]).startswith("Tribler"):
                        self.notifier.notify(Notification.tribler_torrent_peer_update,
                                             peer_id=unhexlify(peer["id"]), infohash=infohash, balance=peer["dtotal"])

        if self.state_cb_count % 4 == 0:
            self._last_states_list = states_list

    def get_last_download_states(self) -> list[DownloadState]:
        """
        Get the last download states.
        """
        return self._last_states_list

    async def load_checkpoints(self) -> None:
        """
        Load the checkpoint files in the checkpoint directory.
        """
        self._logger.info("Load checkpoints...")
        checkpoint_filenames = list(self.get_checkpoint_dir().glob("*.conf"))
        self.checkpoints_count = len(checkpoint_filenames)
        for i, filename in enumerate(checkpoint_filenames, start=1):
            await self.load_checkpoint(filename)
            self.checkpoints_loaded = i
            await sleep(0)
        self.all_checkpoints_are_loaded = True
        self._logger.info("Checkpoints are loaded")

    async def load_checkpoint(self, filename: str) -> bool:
        """
        Load a checkpoint from a given file name.
        """
        try:
            conf_obj = ConfigObj(str(filename), configspec=DownloadConfig.get_spec_file_name(self.config))
            conf_obj.validate(Validator())
            config = DownloadConfig(conf_obj)
        except Exception:
            self._logger.exception("Could not open checkpoint file %s", filename)
            return False

        metainfo = config.get_metainfo()
        if not metainfo:
            self._logger.error("Could not resume checkpoint %s; metainfo not found", filename)
            return False
        if not isinstance(metainfo, dict):
            self._logger.error("Could not resume checkpoint %s; metainfo is not dict %s %s",
                               filename, type(metainfo), repr(metainfo))
            return False

        try:
            url = metainfo.get(b"url")
            url = url.decode() if url is not None else url
            tdef = (TorrentDefNoMetainfo(metainfo[b"infohash"], metainfo[b"name"], url)
                    if b"infohash" in metainfo else TorrentDef.load_from_dict(metainfo))
        except (KeyError, ValueError) as e:
            self._logger.exception("Could not restore tdef from metainfo dict: %s %s ", e, metainfo)
            return False

        config.state_dir = self.state_dir
        if config.get_dest_dir() == "":  # removed torrent ignoring
            self._logger.info("Removing checkpoint %s destdir is %s", filename, config.get_dest_dir())
            os.remove(filename)
            return False

        try:
            if self.download_exists(tdef.get_infohash()):
                self._logger.info("Not resuming checkpoint because download has already been added")
            else:
                await self.start_download(tdef=tdef, config=config)
                return True
        except Exception:
            self._logger.exception("Not resuming checkpoint due to exception while adding download")
        return False

    def remove_config(self, infohash: bytes) -> None:
        """
        Remove the configuration for the download belonging to the given infohash.
        """
        if infohash not in self.downloads:
            try:
                basename = hexlify(infohash).decode() + ".conf"
                filename = self.get_checkpoint_dir() / basename
                self._logger.debug("Removing download checkpoint %s", filename)
                if os.access(filename, os.F_OK):
                    os.remove(filename)
            except:
                # Show must go on
                self._logger.exception("Could not remove state")
        else:
            self._logger.warning("Download is back, restarted? Cancelling removal! %s", hexlify(infohash))

    def get_checkpoint_dir(self) -> Path:
        """
        Returns the directory in which to checkpoint the Downloads in this Session.
        """
        return self.state_dir / "dlcheckpoints"

    @staticmethod
    async def create_torrent_file(file_path_list: list[str], params: dict | None = None) -> TorrentFileResult:
        """
        Creates a torrent file.

        :param file_path_list: files to add in torrent file
        :param params: optional parameters for torrent file
        """
        return await asyncio.get_event_loop().run_in_executor(None, torrents.create_torrent_file,
                                                              file_path_list, params or {})

    def get_downloads_by_name(self, torrent_name: str) -> list[Download]:
        """
        Get all downloads for which the UTF-8 name equals the given string.
        """
        downloads = self.get_downloads()
        return [d for d in downloads if d.get_def().get_name_utf8() == torrent_name]

    @staticmethod
    def set_libtorrent_proxy_settings(config: TriblerConfigManager, proxy_type: int,
                                      server: tuple[str, int] | None = None,
                                      auth: tuple[str, str] | None = None) -> None:
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
        config.set("libtorrent/proxy_type", proxy_type)
        config.set("libtorrent/proxy_server", server if proxy_type else ":")
        config.set("libtorrent/proxy_auth", auth if proxy_type in [3, 5] else ":")

    def get_libtorrent_proxy_settings(self) -> tuple[int, tuple[str, str] | None, tuple[str, str] | None]:
        """
        Get the settings for the libtorrent proxy.
        """
        proxy_server = str(self.config.get("libtorrent/proxy_server"))
        proxy_server = proxy_server.split(":") if proxy_server else None

        proxy_auth = str(self.config.get("libtorrent/proxy_auth"))
        proxy_auth = proxy_auth.split(":") if proxy_auth else None

        return self.config.get("libtorrent/proxy_type"), proxy_server, proxy_auth

    @staticmethod
    def get_libtorrent_max_upload_rate(config: TriblerConfigManager) -> float:
        """
        Gets the maximum upload rate (kB / s).

        :return: the maximum upload rate in kB / s
        """
        return min(config.get("libtorrent/max_upload_rate"), 2147483647)

    @staticmethod
    def get_libtorrent_max_download_rate(config: TriblerConfigManager) -> float:
        """
        Gets the maximum download rate (kB / s).

        :return: the maximum download rate in kB / s
        """
        return min(config.get("libtorrent/max_download_rate"), 2147483647)
