from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER
from tribler_core.components.base import Component
from tribler_core.components.implementation.libtorrent import LibtorrentComponent
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.components.implementation.socks_configurator import SocksServersComponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker

    _rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config

        metadata_store_component = await self.use(MetadataStoreComponent)
        metadata_store = metadata_store_component.mds if metadata_store_component else None

        libtorrent_component = await self.use(LibtorrentComponent)
        download_manager = libtorrent_component.download_manager if libtorrent_component else None

        rest_component = await self.use(RESTComponent)
        self._rest_manager = rest_component.rest_manager if rest_component else None

        socks_servers_component = await self.use(SocksServersComponent)
        socks_ports = socks_servers_component.socks_ports if socks_servers_component else None

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_listen_ports=socks_ports,
                                         metadata_store=metadata_store)
        self.torrent_checker = torrent_checker
        if self._rest_manager:
            self._rest_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        await torrent_checker.initialize()
        if self._rest_manager:
            self._rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', torrent_checker,
                                                      skip_missing=True)

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        if self._rest_manager:
            self._rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', None, skip_missing=True)

        await self.release(RESTComponent)

        await self.torrent_checker.shutdown()
