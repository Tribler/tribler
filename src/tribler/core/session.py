from __future__ import annotations

import asyncio
import logging
import sys
from asyncio import AbstractEventLoop, Event
from os.path import isfile
from traceback import format_exception
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.loader import IPv8CommunityLoader
from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.messaging.interfaces.udp.endpoint import UDPv6Endpoint
from ipv8_rust_tunnels.endpoint import RustEndpoint
from ipv8_service import IPv8

from tribler.core.components import (
    CommunityLauncherWEndpoints,
    ContentDiscoveryComponent,
    DatabaseComponent,
    DHTDiscoveryComponent,
    RecommenderComponent,
    RendezvousComponent,
    RSSComponent,
    TorrentCheckerComponent,
    TunnelComponent,
    VersioningComponent,
    WatchFolderComponent,
)
from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler.core.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler.core.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler.core.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler.core.notifier import Notification, Notifier
from tribler.core.restapi.events_endpoint import EventsEndpoint
from tribler.core.restapi.file_endpoint import FileEndpoint
from tribler.core.restapi.ipv8_endpoint import IPv8RootEndpoint
from tribler.core.restapi.logging_endpoint import LoggingEndpoint
from tribler.core.restapi.rest_manager import RESTManager
from tribler.core.restapi.settings_endpoint import SettingsEndpoint
from tribler.core.restapi.shutdown_endpoint import ShutdownEndpoint
from tribler.core.restapi.statistics_endpoint import StatisticsEndpoint
from tribler.core.restapi.webui_endpoint import WebUIEndpoint

if TYPE_CHECKING:
    from types import TracebackType

    from ipv8.REST.overlays_endpoint import OverlaysEndpoint

    from tribler.core.database.store import MetadataStore
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker
    from tribler.tribler_config import TriblerConfigManager

logger = logging.getLogger(__name__)


async def _is_url_available(url: str, timeout: int=1) -> tuple[bool, bytes | None]:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                return True, await response.read()
        except (TimeoutError, aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientResponseError):
            return False, None


def rescue_keys(config: TriblerConfigManager) -> None:
    """
    Check and rescue private keys if necessary.
    """
    for key_block in config.get("ipv8/keys"):
        if key_block["file"] and isfile(key_block["file"]):
            with open(key_block["file"], "rb") as f:
                key_content = f.read()
            try:
                default_eccrypto.key_from_private_bin(key_content)
                return
            except ValueError:
                with open(key_block["file"], "wb") as f:
                    if len(key_content) == 64:
                        logger.warning("Broken, but recoverable private key detected!")
                        f.write(b"LibNaCLSK:" + key_content)
                    else:
                        logger.warning("Broken private key replaced!")
                        f.write(default_eccrypto.generate_key("curve25519").key_to_bin())


class Session:
    """
    A session manager that manages all components.
    """

    def __init__(self, config: TriblerConfigManager) -> None:
        """
        Create a new session without initializing any components yet.
        """
        self.config = config

        self.shutdown_event = Event()
        self.notifier = Notifier()

        # Libtorrent
        self.download_manager = DownloadManager(self.config, self.notifier)

        # IPv8
        dpep = DispatcherEndpoint([])
        if ipv4ifs := [e for e in self.config.get("ipv8")["interfaces"] if e["interface"] == "UDPIPv4"]:
            dpep.interfaces["UDPIPv4"] = self.rust_endpoint = RustEndpoint(ipv4ifs[0]["port"], ipv4ifs[0]["ip"],
                                                                           ipv4ifs[0].get("worker_threads", 4))
            dpep.interface_order.append("UDPIPv4")
        if ipv6ifs := [e for e in self.config.get("ipv8")["interfaces"] if e["interface"] == "UDPIPv6"]:
            dpep.interfaces["UDPIPv6"] = UDPv6Endpoint(ipv6ifs[0]["port"], ipv6ifs[0]["ip"])
            dpep.interface_order.append("UDPIPv6")

        rescue_keys(self.config)
        self.ipv8 = IPv8(cast("dict[str, Any]", self.config.get("ipv8")), endpoint_override=dpep)
        self.ipv8.endpoint.get_statistics = self.rust_endpoint.get_statistics  # type: ignore[attr-defined]
        self.loader = IPv8CommunityLoader()

        # REST
        self.rest_manager = RESTManager(self.config)

        # Optional globals, set by components:
        self.mds: MetadataStore | None = None
        self.torrent_checker: TorrentChecker | None = None

    def register_launchers(self) -> None:
        """
        Register all IPv8 launchers that allow communities to be loaded.
        """
        for launcher_class in [ContentDiscoveryComponent, DatabaseComponent, DHTDiscoveryComponent,
                               RecommenderComponent, RendezvousComponent, RSSComponent, TorrentCheckerComponent,
                               TunnelComponent, VersioningComponent, WatchFolderComponent]:
            instance: CommunityLauncherWEndpoints = cast("CommunityLauncherWEndpoints", launcher_class())
            for rest_ep in instance.get_endpoints():
                self.rest_manager.add_endpoint(rest_ep)
            self.loader.set_launcher(instance)

    def register_rest_endpoints(self) -> None:
        """
        Register all core REST endpoints without initializing them.
        """
        self.rest_manager.add_endpoint(LoggingEndpoint())  # Do this first to register logging for the other endpoints.
        self.rest_manager.add_endpoint(WebUIEndpoint())
        self.rest_manager.add_endpoint(FileEndpoint())
        self.rest_manager.add_endpoint(CreateTorrentEndpoint(self.download_manager))
        self.rest_manager.add_endpoint(DownloadsEndpoint(self.download_manager))
        self.rest_manager.add_endpoint(EventsEndpoint(self.notifier))
        self.rest_manager.add_endpoint(IPv8RootEndpoint())
        self.rest_manager.add_endpoint(LibTorrentEndpoint(self.download_manager))
        self.rest_manager.add_endpoint(SettingsEndpoint(self.config, self.download_manager))
        self.rest_manager.add_endpoint(ShutdownEndpoint(self.shutdown_event.set))
        self.rest_manager.add_endpoint(StatisticsEndpoint())
        self.rest_manager.add_endpoint(TorrentInfoEndpoint(self.download_manager))

    def _except_hook(self, typ: type[BaseException], value: BaseException, traceback: TracebackType | None) -> None:
        """
        Handle an uncaught exception.

        Note: at this point the REST interface is available.
        Note2: ignored BaseExceptions are BaseExceptionGroup, GeneratorExit, KeyboardInterrupt and SystemExit
        """
        logger.exception("Uncaught exception: %s", "".join(format_exception(typ, value, traceback)))
        if isinstance(value, Exception):
            cast("EventsEndpoint", self.rest_manager.get_endpoint("/api/events")).on_tribler_exception(value)

    def _asyncio_except_hook(self, loop: AbstractEventLoop, context: dict[str, Any]) -> None:
        """
        Handle an uncaught asyncio exception.

        Note: at this point the REST interface is available.
        Note2: ignored BaseExceptions are BaseExceptionGroup, GeneratorExit, KeyboardInterrupt and SystemExit
        """
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError):
            logger.exception("Network unreachable: %s",
                             "".join(format_exception(exc.__class__, exc, exc.__traceback__)))
        elif isinstance(exc, Exception):
            logger.exception("Uncaught async exception: %s",
                             "".join(format_exception(exc.__class__, exc, exc.__traceback__)))
            cast("EventsEndpoint", self.rest_manager.get_endpoint("/api/events")).on_tribler_exception(exc)
            raise exc

    def attach_exception_handler(self) -> None:
        """
        Hook ourselves in as the general exception handler.
        """
        sys.excepthook = self._except_hook
        asyncio.get_running_loop().set_exception_handler(self._asyncio_except_hook)

    async def start(self) -> None:
        """
        Initialize and launch all components and REST endpoints.
        """
        self.register_rest_endpoints()
        self.register_launchers()

        # REST (1/2)
        await self.rest_manager.start()
        self.attach_exception_handler()

        # IPv8
        self.loader.load(self.ipv8, self)
        await self.ipv8.start()

        # Libtorrent
        self.download_manager.socks_listen_ports = [
            self.rust_endpoint.create_socks5_server(port, index+1)   # type: ignore[attr-defined]
            for index, port in enumerate(self.config.get("libtorrent/socks_listen_ports"))
        ]
        await self.download_manager.initialize()
        self.download_manager.start()

        if self.torrent_checker:
            self.torrent_checker.socks_listen_ports = self.download_manager.socks_listen_ports

        # REST (2/2)
        ipv8_root_endpoint = cast("IPv8RootEndpoint", self.rest_manager.get_endpoint("/api/ipv8"))
        ipv8_root_endpoint.initialize(self.ipv8)

        overlays_endpoint = cast("OverlaysEndpoint", ipv8_root_endpoint.endpoints["/overlays"])
        # Enable statistics for IPv8 StatisticsEndpoint
        if overlays_endpoint.statistics_supported:
            overlays_endpoint.enable_overlay_statistics(True, None, True)
        # When using RustEndpoint, statistics are also reported. However, since RustEndpoint
        # does not inherit from StatisticsEndpoint, we need to manually set statistics_supported.
        overlays_endpoint.statistics_supported = True

    async def find_api_server(self) -> tuple[str | None, bytes | None]:
        """
        Find the API server, if available.
        """
        info_route = f'/api/events/info?key={self.config.get("api/key")}'

        if port := self.config.get("api/http_port_running"):
            http_url = f'http://{self.config.get("api/http_host")}:{port}'
            available, response = await _is_url_available(http_url + info_route)
            if available:
                return http_url, response

        if port := self.config.get("api/https_port_running"):
            https_url = f'https://{self.config.get("api/https_host")}:{port}'
            available, response = await _is_url_available(https_url + info_route)
            if available:
                return https_url, response

        return None, None

    async def shutdown(self) -> None:
        """
        Shut down all connections and components.
        """
        # Stop network event generators
        if self.torrent_checker:
            self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down torrent checker.")
            await self.torrent_checker.shutdown()
        if self.ipv8:
            self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down IPv8 peer-to-peer overlays.")
            await self.ipv8.stop()

        # Stop libtorrent managers
        self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down download manager.")
        await self.download_manager.shutdown()
        self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down local SOCKS5 interface.")

        # Stop database activities
        if self.mds:
            self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down metadata database.")
            self.mds.shutdown()

        # Stop communication with the GUI
        self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down GUI connection. Going dark.")
        await self.rest_manager.stop()
