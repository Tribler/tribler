from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER

from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.socks_configurator import SocksServersComponent
from tribler_core.components.interfaces.torrent_checker import TorrentCheckerComponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager


class TorrentCheckerComponentImp(TorrentCheckerComponent):
    rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent)

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
        # self.provide(mediator, torrent_checker)

        rest_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        await torrent_checker.initialize()
        rest_manager.get_endpoint('metadata').torrent_checker = torrent_checker

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        self.rest_manager.get_endpoint('metadata').torrent_checker = None
        await self.release(RESTComponent)

        await self.torrent_checker.shutdown()
