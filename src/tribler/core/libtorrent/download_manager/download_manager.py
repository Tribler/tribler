"""
A wrapper around libtorrent.

Author(s): Egbert Bouman
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import time
from asyncio import CancelledError, Future, gather, iscoroutine, shield, sleep, wait_for
from binascii import hexlify, unhexlify
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Callable, cast

import libtorrent as lt
from configobj import ConfigObj
from ipv8.taskmanager import TaskManager
from validate import Validator
from yarl import URL

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.libtorrent.download_manager.download_state import DownloadState, DownloadStatus
from tribler.core.libtorrent.torrentdef import MetainfoDict, TorrentDef, TorrentDefNoMetainfo
from tribler.core.libtorrent.uris import unshorten, url_to_path
from tribler.core.notifier import Notification, Notifier
from tribler.tribler_config import VERSION_SUBDIR

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterable

    from tribler.core.libtorrent.download_manager.dht_health_manager import DHTHealthManager
    from tribler.tribler_config import TriblerConfigManager

SOCKS5_PROXY_DEF = 2

LTSTATE_FILENAME = "lt.state"
METAINFO_CACHE_PERIOD = 5 * 60
DEFAULT_DHT_ROUTERS = [
    ("dht.aelitis.com", 6881),
    ("dht.libtorrent.org", 6881),
    ("dht.libtorrent.org", 25401),
    ("dht.transmissionbt.com", 6881),
    ("router.bitcomet.com", 6881),
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881),
]
DEFAULT_LT_EXTENSIONS = [
    lt.create_ut_metadata_plugin,
    lt.create_ut_pex_plugin,
    lt.create_smart_ban_plugin
]

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MetainfoLookup:
    """
    A metainfo lookup download and the number of times it has been invoked.
    """

    download: Download
    pending: int


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
        self.ltsettings: dict[lt.session, dict] = {}  # Stores a copy of the settings dict for each libtorrent session
        self.ltsessions: dict[int, Future[lt.session]] = {}
        self.dht_health_manager: DHTHealthManager | None = None
        self.listen_ports: dict[int, dict[str, int]] = defaultdict(dict)

        self.socks_listen_ports = config.get("libtorrent/socks_listen_ports")

        self.notifier = notifier

        self.register_task("Set default upload rate limit", self.set_upload_rate_limit, 0)
        self.register_task("Set default download rate limit", self.set_download_rate_limit, 0)

        self.downloads: dict[bytes, Download] = {}

        self.checkpoint_directory = (self.state_dir / "dlcheckpoints")
        self.checkpoints_count = 0
        self.checkpoints_loaded = 0
        self.all_checkpoints_are_loaded = False

        self.metadata_tmpdir: TemporaryDirectory | None = (metadata_tmpdir or
                                                           TemporaryDirectory(suffix="tribler_metainfo_tmpdir"))
        # Dictionary that maps infohashes to download instances. These include only downloads that have
        # been made specifically for fetching metainfo, and will be removed afterwards.
        self.metainfo_requests: dict[bytes, MetainfoLookup] = {}
        self.metainfo_cache: dict[bytes, MetainfoDict] = {}  # Dictionary that maps infohashes to cached metainfo items

        self.default_alert_mask = lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | \
                                  lt.alert.category_t.storage_notification | lt.alert.category_t.performance_warning | \
                                  lt.alert.category_t.tracker_notification | lt.alert.category_t.debug_notification
        self.session_stats_callback: Callable | None = None
        self.state_cb_count = 0
        self.queued_write_bytes = -1

        # Status of libtorrent session to indicate if it can safely close and no pending writes to disk exists.
        self.lt_session_shutdown_ready: dict[int, bool] = {}
        self.dht_ready_task = None
        self.dht_readiness_timeout = config.get("libtorrent/dht_readiness_timeout")
        self._last_states_list: list[DownloadState] = []

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
        while (await self.get_session()).status().dht_nodes < min_dht_peers:
            await asyncio.sleep(1)

    async def initialize(self) -> None:
        """
        Initialize the directory structure, launch the periodic tasks and start libtorrent background processes.
        """
        # Create the checkpoints directory
        self.checkpoint_directory.mkdir(exist_ok=True, parents=True)

        # Register tasks
        self.register_task("process_alerts", self._task_process_alerts, interval=1, ignore=(Exception, ))
        if self.dht_readiness_timeout > 0 and self.config.get("libtorrent/dht"):
            self.dht_ready_task = self.register_task("check_dht_ready", self._check_dht_ready)
        self.register_task("request_torrent_updates", self._request_torrent_updates, interval=1)
        self.register_task("task_cleanup_metacache", self._task_cleanup_metainfo_cache, interval=60, delay=0)

        self.set_download_states_callback(self.sesscb_states_callback)

        # Start upnp
        if self.config.get("libtorrent/upnp"):
            (await self.get_session()).start_upnp()

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
        end_time = time.time() + timeout
        force_quit = end_time - time.time()
        while not self.is_shutdown_ready() and force_quit > 0:
            not_ready = list(self.lt_session_shutdown_ready.values()).count(False)
            self.notify_shutdown_state(
                f"Waiting for {not_ready} downloads to finish."
                + (".." if self.queued_write_bytes == -1 else f" {self.queued_write_bytes} bytes left to write.")
                + f" {force_quit:.2f} seconds left until forced shutdown."
            )
            self.post_session_stats()
            await asyncio.sleep(max(1.0, not_ready * 0.01))  # 10 ms per download, up to 1 second
            force_quit = end_time - time.time()

        logger.info("Awaiting shutdown task manager...")
        await self.shutdown_task_manager()

        if self.dht_health_manager:
            await self.dht_health_manager.shutdown_task_manager()

        # Save libtorrent state
        if self.has_session():
            logger.info("Saving state...")
            self.notify_shutdown_state("Writing session state to disk.")
            session = await self.get_session()
            with open(self.state_dir / LTSTATE_FILENAME, "wb") as ltstate_file:  # noqa: ASYNC230
                ltstate_file.write(lt.bencode(session.save_state()))

        if self.has_session() and self.config.get("libtorrent/upnp"):
            logger.info("Stopping upnp...")
            self.notify_shutdown_state("Stopping UPnP.")
            (await self.get_session()).stop_upnp()

        # Remove metadata temporary directory
        if self.metadata_tmpdir:
            logger.info("Removing temp directory...")
            self.notify_shutdown_state("Removing temporary download files.")
            self.metadata_tmpdir.cleanup()
            self.metadata_tmpdir = None

        logger.info("Shutdown completed")
        self.notify_shutdown_state("Finished shutting down download manager.")

    def is_shutdown_ready(self) -> bool:
        """
        Check if the libtorrent shutdown is complete.
        """
        return all(self.lt_session_shutdown_ready.values())

    def create_session(self, hops: int = 0) -> lt.session:  # noqa: PLR0915
        """
        Construct a libtorrent session for the given number of anonymization hops.
        """
        # Due to a bug in Libtorrent 0.16.18, the outgoing_port and num_outgoing_ports value should be set in
        # the settings dictionary
        logger.info("Creating a session")
        settings: dict[str, str | float] = {
            "outgoing_port": 0,
            "num_outgoing_ports": 1,
            "allow_multiple_connections_per_ip": 0,
            "enable_upnp": int(self.config.get("libtorrent/upnp")),
            "enable_dht": int(self.config.get("libtorrent/dht")),
            "enable_lsd": int(self.config.get("libtorrent/lsd")),
            "enable_natpmp": int(self.config.get("libtorrent/natpmp")),
            "allow_i2p_mixed": 1,
            "announce_to_all_tiers": int(self.config.get("libtorrent/announce_to_all_tiers")),
            "announce_to_all_trackers": int(self.config.get("libtorrent/announce_to_all_trackers")),
            "max_concurrent_http_announces": int(self.config.get("libtorrent/max_concurrent_http_announces"))
        }

        # Copy construct so we don't modify the default list
        extensions = list(DEFAULT_LT_EXTENSIONS)

        logger.info("Hops: %d.", hops)

        # Elric: Strip out the -rcX, -beta, -whatever tail on the version string.
        ltsession = lt.session(lt.fingerprint("TL", 0, 0, 0, 0), flags=0) if hops == 0 else lt.session(flags=0)

        libtorrent_if = self.config.get("libtorrent/listen_interface")
        libtorrent_port = self.config.get("libtorrent/port")
        logger.info("Libtorrent ip+port set to %s:%d", libtorrent_if, libtorrent_port)
        if hops == 0:
            settings["user_agent"] = 'Tribler/' + VERSION_SUBDIR
            enable_utp = self.config.get("libtorrent/utp")
            settings["enable_outgoing_utp"] = enable_utp
            settings["enable_incoming_utp"] = enable_utp
            settings["prefer_rc4"] = True
            settings["listen_interfaces"] = f"{libtorrent_if}:{libtorrent_port or 6881}"
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

    def get_session(self, hops: int = 0) -> Future[lt.session]:
        """
        Get the session for the given number of anonymization hops.
        """
        if hops not in self.ltsessions:
            self.ltsessions[hops] = self.register_executor_task(f"Create session {hops}", self.create_session, hops)

        return self.ltsessions[hops]

    def set_proxy_settings(self, ltsession: lt.session, ptype: int, server: tuple[str, str | int] | None = None,
                           auth: tuple[str, str] | None = None) -> None:
        """
        Apply the proxy settings to a libtorrent session. This mechanism changed significantly in libtorrent 1.1.0.
        """
        settings: dict[str, str | float] = {"proxy_type": ptype, "proxy_hostnames": True,
                                            "proxy_peer_connections": True}
        if server is not None:
            proxy_host = server[0]
            if proxy_host:
                settings["proxy_hostname"] = proxy_host
                settings["proxy_port"] = int(server[1]) if server[1] else 0
        if auth is not None:
            settings["proxy_username"] = auth[0]
            settings["proxy_password"] = auth[1]
        self.set_session_settings(ltsession, settings)

    def set_max_connections(self, conns: int, hops: int | None = None) -> None:
        """
        Set the maximum number of connections for the given hop count.
        """
        self._map_call_on_ltsessions(hops, "set_max_connections", conns)

    async def set_upload_rate_limit(self, rate: int) -> None:
        """
        Set the upload rate limit for the given session.
        """
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        libtorrent_rate = self.convert_rate(rate=rate)

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {"upload_rate_limit": libtorrent_rate, "outgoing_port": 0, "num_outgoing_ports": 1}
        for session in self.ltsessions.values():
            self.set_session_settings(await session, settings_dict)

    async def get_upload_rate_limit(self, hops: int = 0) -> int:
        """
        Get the upload rate limit for the session with the given hop count.
        """
        # Rate conversion due to the fact that we had a different system with Swift
        # and the old python BitTorrent core: unlimited == 0, stop == -1, else rate in kbytes
        session = await self.get_session(hops)
        libtorrent_rate = session.upload_rate_limit()
        return self.reverse_convert_rate(rate=libtorrent_rate)

    async def set_download_rate_limit(self, rate: int) -> None:
        """
        Set the download rate limit for the given session.
        """
        libtorrent_rate = self.convert_rate(rate=rate)

        # Pass outgoing_port and num_outgoing_ports to dict due to bug in libtorrent 0.16.18
        settings_dict = {"download_rate_limit": libtorrent_rate}
        for session in self.ltsessions.values():
            self.set_session_settings(await session, settings_dict)

    async def get_download_rate_limit(self, hops: int = 0) -> int:
        """
        Get the download rate limit for the session with the given hop count.
        """
        session = await self.get_session(hops)
        libtorrent_rate = session.download_rate_limit()
        return self.reverse_convert_rate(rate=libtorrent_rate)

    def process_alert(self, alert: lt.alert, hops: int = 0) -> None:  # noqa: C901, PLR0912
        """
        Process a libtorrent alert.
        """
        alert_type = alert.__class__.__name__

        # Periodically, libtorrent will send us a state_update_alert, which contains the torrent status of
        # all torrents changed since the last time we received this alert.
        if alert_type == "state_update_alert":
            for status in cast(lt.state_update_alert, alert).status:
                infohash = status.info_hash.to_bytes()
                if infohash not in self.downloads:
                    logger.debug("Got state_update for unknown torrent %s", hexlify(infohash))
                    continue
                self.downloads[infohash].update_lt_status(status)

        if alert_type == "state_changed_alert":
            handle = cast(lt.state_changed_alert, alert).handle
            infohash = handle.info_hash().to_bytes()
            if infohash not in self.downloads:
                logger.debug("Got state_change for unknown torrent %s", hexlify(infohash))
            else:
                self.downloads[infohash].update_lt_status(handle.status())

        infohash = (alert.handle.info_hash().to_bytes() if hasattr(alert, "handle") and alert.handle.is_valid()
                    else getattr(alert, "info_hash", b""))
        download = self.downloads.get(infohash)
        if download:
            is_process_alert = (download.handle and download.handle.is_valid()) \
                               or (not download.handle and alert_type == "add_torrent_alert") \
                               or (download.handle and alert_type == "torrent_removed_alert")
            if is_process_alert:
                download.process_alert(cast(lt.torrent_alert, alert), alert_type)
            else:
                logger.debug("Got alert for download without handle %s: %s", infohash, alert)
        elif infohash:
            logger.debug("Got alert for unknown download %s: %s", infohash, alert)

        if alert_type == "listen_succeeded_alert":
            ls_alert = cast(lt.listen_succeeded_alert, alert)
            self.listen_ports[hops][ls_alert.address] = ls_alert.port

        elif alert_type == "peer_disconnected_alert":
            self.notifier.notify(Notification.peer_disconnected,
                                 peer_id=cast(lt.peer_disconnected_alert, alert).pid.to_bytes())

        elif alert_type == "session_stats_alert":
            ss_alert = cast(lt.session_stats_alert, alert)
            queued_disk_jobs = ss_alert.values["disk.queued_disk_jobs"]
            self.queued_write_bytes = ss_alert.values["disk.queued_write_bytes"]
            num_write_jobs = ss_alert.values["disk.num_write_jobs"]
            if queued_disk_jobs == self.queued_write_bytes == num_write_jobs == 0:
                self.lt_session_shutdown_ready[hops] = True

            if self.session_stats_callback:
                self.session_stats_callback(ss_alert)

        elif alert_type == "dht_pkt_alert" and self.dht_health_manager is not None:
            # Unfortunately, the Python bindings don't have a direction attribute.
            # So, we'll have to resort to using the string representation of the alert instead.
            incoming = str(alert).startswith("<==")
            decoded = cast(dict[bytes, Any], lt.bdecode(cast(lt.dht_pkt_alert, alert).pkt_buf))
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

    async def get_metainfo(self, infohash: bytes, timeout: float = 7, hops: int | None = None,  # noqa: C901
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
            download = self.metainfo_requests[infohash].download
            self.metainfo_requests[infohash].pending += 1
        elif infohash in self.downloads:
            download = self.downloads[infohash]
        else:
            tdef = TorrentDefNoMetainfo(infohash, b"metainfo request", url=url)
            dcfg = DownloadConfig.from_defaults(self.config)
            dcfg.set_hops(hops or self.config.get("libtorrent/download_defaults/number_hops"))
            dcfg.set_upload_mode(True)  # Upload mode should prevent libtorrent from creating files
            if self.metadata_tmpdir is not None:
                dcfg.set_dest_dir(self.metadata_tmpdir.name)
            try:
                download = await self.start_download(tdef=tdef, config=dcfg, hidden=True, checkpoint_disabled=True)
            except TypeError as e:
                logger.warning(e)
                if raise_errors:
                    raise
                return None
            self.metainfo_requests[infohash] = MetainfoLookup(download, 1)

        try:
            metainfo = download.tdef.get_metainfo() or await wait_for(shield(download.future_metainfo), timeout)
        except (CancelledError, asyncio.TimeoutError) as e:
            logger.warning("%s: %s (timeout=%f)", type(e).__name__, str(e), timeout)
            logger.info("Failed to retrieve metainfo for %s", infohash_hex)
            if raise_errors:
                raise
            return None

        logger.info("Successfully retrieved metainfo for %s", infohash_hex)
        self.metainfo_cache[infohash] = {"time": time.time(), "meta_info": metainfo}
        self.notifier.notify(Notification.torrent_metadata_added, metadata={
            "infohash": infohash,
            "size": download.tdef.get_length(),
            "title": download.tdef.get_name_utf8(),
            "metadata_type": 300,
            "tracker_info": (list(download.tdef.get_trackers()) or [""])[0]
        })

        seeders, leechers = download.get_state().get_num_seeds_peers()
        metainfo[b"seeders"] = seeders
        metainfo[b"leechers"] = leechers

        if infohash in self.metainfo_requests:
            self.metainfo_requests[infohash].pending -= 1
            if self.metainfo_requests[infohash].pending <= 0:
                await self.remove_download(download, remove_content=True)
                self.metainfo_requests.pop(infohash, None)

        return metainfo

    def _task_cleanup_metainfo_cache(self) -> None:
        oldest_time = time.time() - METAINFO_CACHE_PERIOD

        for info_hash, cache_entry in list(self.metainfo_cache.items()):
            last_time = cache_entry["time"]
            if last_time < oldest_time:
                del self.metainfo_cache[info_hash]

    async def _request_torrent_updates(self) -> None:
        for ltsession in self.ltsessions.values():
            (await ltsession).post_torrent_updates(0xffffffff)

    async def _task_process_alerts(self) -> None:
        for hops, ltsession in list(self.ltsessions.items()):
            for alert in (await ltsession).pop_alerts():
                self.process_alert(alert, hops=hops)

    def _map_call_on_ltsessions(self, hops: int | None, funcname: str, *args: Any, **kwargs) -> None:  # noqa: ANN401
        if hops is None:
            for session in self.ltsessions.values():
                session.add_done_callback(lambda s: getattr(s.result(), funcname)(*args, **kwargs))
        else:
            self.get_session(hops).add_done_callback(lambda s: getattr(s.result(), funcname)(*args, **kwargs))

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
            name = params.name.encode()
            infohash = unhexlify(str(params.info_hash))
            if config:
                config.set_selected_files([i for i in range(len(params.file_priorities))
                                           if params.file_priorities[i] > 0])
            logger.info("Name: %s. Infohash: %s", name, infohash)
            if infohash in self.metainfo_cache:
                logger.info("Metainfo found in cache")
                tdef = TorrentDef.load_from_dict(self.metainfo_cache[infohash]["meta_info"])
            else:
                logger.info("Metainfo not found in cache")
                tdef = TorrentDefNoMetainfo(infohash, name if name else b"Unknown name", url=uri)
            download = await self.start_download(tdef=tdef, config=config)
            async def add_helpers_later() -> None:
                await download.get_handle()
                download.add_trackers([t.encode() for t in params.trackers])
                for peer in params.peers:
                    download.add_peer(peer)
                for url in params.url_seeds:
                    download.add_url_seed(url)
            self.register_anonymous_task(f"Add helpers to {params.info_hash!s}", add_helpers_later)
            return download
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
            config.set_time_added(int(time.time()))

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
        if infohash not in self.metainfo_requests or self.metainfo_requests[infohash].download == download:
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
            try:
                resume_data_dict = cast(dict[bytes, Any], lt.bdecode(resume_data))
                # If the save_path is None or "" win32 SEGFAULTS, see https://github.com/Tribler/tribler/issues/8353
                if not resume_data_dict.get(b"save_path"):
                    resume_data_dict[b"save_path"] = atp.get("save_path", ".").encode()
                atp["resume_data"] = lt.bencode(resume_data_dict)
            except RuntimeError:
                atp.pop("resume_data")
            logger.debug("Download resume data: %s", str(atp["resume_data"]))
        logger.info("Start handle. Download: %s. Atp: %s", str(download), str(atp_resume_data_skipped))

        ltsession = await self.get_session(download.config.get_hops())
        infohash = download.get_def().get_infohash()

        if infohash in self.metainfo_requests and self.metainfo_requests[infohash].download != download:
            logger.info("Cancelling metainfo request(s) for infohash:%s", hexlify(infohash))
            # Leave the checkpoint. Any checkpoint that exists will belong to the download we are currently starting.
            await self.remove_download(self.metainfo_requests.pop(infohash).download,
                                       remove_content=True, remove_checkpoint=False)
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

        if not isinstance(download.tdef, TorrentDefNoMetainfo):
            self.notifier.notify(Notification.torrent_metadata_added, metadata={
                "infohash": infohash,
                "size": download.tdef.get_length(),
                "title": download.tdef.get_name_utf8(),
                "metadata_type": 300,
                "tracker_info": (list(download.tdef.get_trackers()) or [""])[0]
            })

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
            lt_session.apply_settings(new_settings)
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
        rate = DownloadManager.get_libtorrent_max_upload_rate(self.config)
        download_rate = DownloadManager.get_libtorrent_max_download_rate(self.config)
        settings = {"download_rate_limit": download_rate,
                    "upload_rate_limit": rate}
        for lt_session in self.ltsessions.values():
            lt_session.add_done_callback(lambda s: self.set_session_settings(s.result(), settings))

    def post_session_stats(self) -> None:
        """
        Gather statistics and cause a ``session_stats_alert``.
        """
        logger.info("Post session stats")
        for session in self.ltsessions.values():
            session.add_done_callback(lambda s: s.result().post_session_stats())

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
                (await self.get_session(download.config.get_hops())).remove_torrent(handle, int(remove_content))
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

    def get_downloads(self) -> list[Download]:
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

    def update_trackers(self, infohash: bytes, trackers: list[bytes]) -> None:
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

    def set_download_states_callback(self, user_callback: Callable[[list[DownloadState]], Awaitable[None] | None],
                                     interval: float = 1.0) -> None:
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

    async def _invoke_states_cb(self, callback: Callable[[list[DownloadState]], Awaitable[None] | None]) -> None:
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

    async def load_checkpoint(self, filename: Path | str) -> bool:
        """
        Load a checkpoint from a given file name.
        """
        try:
            conf_obj = ConfigObj(str(filename), configspec=DownloadConfig.get_spec_file_name(self.config),
                                 encoding="utf-8")
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
        setting_proxy_server = str(self.config.get("libtorrent/proxy_server")).split(":")
        proxy_server = ((setting_proxy_server[0], setting_proxy_server[1])
                        if setting_proxy_server and len(setting_proxy_server) == 2 else None)

        setting_proxy_auth = str(self.config.get("libtorrent/proxy_auth")).split(":")
        proxy_auth = ((setting_proxy_auth[0], setting_proxy_auth[1])
                      if setting_proxy_auth and len(setting_proxy_auth) == 2  else None)

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
