from __future__ import annotations

import asyncio
import logging
import sys
from asyncio import AbstractEventLoop, Event
from contextlib import contextmanager
from os.path import isfile
from traceback import format_exception
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.loader import IPv8CommunityLoader
from ipv8_service import IPv8

from tribler.core.components import (
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
from tribler.core.socks5.server import Socks5Server

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import TracebackType

    from tribler.core.database.store import MetadataStore
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker
    from tribler.tribler_config import TriblerConfigManager

logger = logging.getLogger(__name__)


@contextmanager
def rust_enhancements(session: Session) -> Generator[None, None, None]:
    """
    Attempt to import the IPv8 Rust anonymization backend.
    """
    use_fallback = session.config.get("statistics")
    if_specs = [ifc for ifc in session.config.get("ipv8/interfaces") if ifc["interface"] == "UDPIPv4"]

    if not use_fallback:
        try:
            from ipv8.messaging.interfaces.dispatcher.endpoint import INTERFACES
            from ipv8_rust_tunnels.endpoint import RustEndpoint
            INTERFACES["UDPIPv4"] = RustEndpoint
            for ifc in if_specs:
                ifc["worker_threads"] = ifc.get("worker_threads", session.config.get("tunnel_community/max_circuits"))
            yield
            if if_specs:
                for server in session.socks_servers:
                    ipv4_endpoint = session.ipv8.endpoint.interfaces["UDPIPv4"]
                    server.rust_endpoint = ipv4_endpoint if isinstance(ipv4_endpoint, RustEndpoint) else None
        except ImportError:
            logger.info("Rust endpoint not found (pip install ipv8-rust-tunnels).")
            use_fallback = True

    if use_fallback:
        # Make sure there are no ``worker_threads`` settings fed into non-Rust endpoints.
        previous_values = [("worker_threads" in ifc, ifc.pop("worker_threads")) for ifc in if_specs]
        yield
        # Restore ``worker_threads`` settings, if they were there.
        for i, (has_previous_value, previous_value) in enumerate(previous_values):
            if has_previous_value:
                if_specs[i]["worker_threads"] = previous_value


async def _is_url_available(url: str, timeout: int=1) -> bool:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=timeout):
                return True
        except (asyncio.TimeoutError, aiohttp.client_exceptions.ClientConnectorError,
                aiohttp.client_exceptions.ClientResponseError):
            return False


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
        self.socks_servers = [Socks5Server(port) for port in self.config.get("libtorrent/socks_listen_ports")]

        # IPv8
        rescue_keys(self.config)
        with rust_enhancements(self):
            self.ipv8 = IPv8(self.config.get("ipv8"), enable_statistics=self.config.get("statistics"))
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
            instance = launcher_class()
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
        self.rest_manager.add_endpoint(SettingsEndpoint(self.config))
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
            cast(EventsEndpoint, self.rest_manager.get_endpoint("/api/events")).on_tribler_exception(value)

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
            cast(EventsEndpoint, self.rest_manager.get_endpoint("/api/events")).on_tribler_exception(exc)
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

        # Libtorrent
        for server in self.socks_servers:
            await server.start()
        self.download_manager.socks_listen_ports = [s.port for s in self.socks_servers]
        await self.download_manager.initialize()
        self.download_manager.start()

        # IPv8
        self.loader.load(self.ipv8, self)
        await self.ipv8.start()

        # REST (2/2)
        self.rest_manager.get_endpoint("/api/ipv8").initialize(self.ipv8)
        self.rest_manager.get_endpoint("/api/statistics").ipv8 = self.ipv8
        if self.config.get("statistics"):
            self.rest_manager.get_endpoint("/api/ipv8").endpoints["/overlays"].enable_overlay_statistics(True, None,
                                                                                                         True)

    async def find_api_server(self) -> str | None:
        """
        Find the API server, if available.
        """
        if port := self.config.get("api/http_port_running"):
            http_url = f'http://{self.config.get("api/http_host")}:{port}'
            if await _is_url_available(http_url):
                return http_url

        if port := self.config.get("api/https_port_running"):
            https_url = f'https://{self.config.get("api/https_host")}:{port}'
            if await _is_url_available(https_url):
                return https_url

        return None

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
        for server in self.socks_servers:
            await server.stop()

        # Stop database activities
        if self.mds:
            self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down metadata database.")
            self.mds.shutdown()

        # Stop communication with the GUI
        self.notifier.notify(Notification.tribler_shutdown_state, state="Shutting down GUI connection. Going dark.")
        await self.rest_manager.stop()
