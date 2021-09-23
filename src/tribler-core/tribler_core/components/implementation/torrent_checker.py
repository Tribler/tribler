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
    rest_manager: RESTManager
    torrent_checker: TorrentChecker

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config

        metadata_store = (await self.use(MetadataStoreComponent)).mds
        download_manager = (await self.use(LibtorrentComponent)).download_manager
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager
        socks_ports = (await self.use(SocksServersComponent)).socks_ports

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_listen_ports=socks_ports,
                                         metadata_store=metadata_store)
        self.torrent_checker = torrent_checker

        rest_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        await torrent_checker.initialize()
        rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', torrent_checker, skip_missing=True)

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        self.rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', None, skip_missing=True)

        await self.release(RESTComponent)

        await self.torrent_checker.shutdown()
