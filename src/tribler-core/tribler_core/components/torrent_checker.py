from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER
from tribler_core.components.base import Component
from tribler_core.components.libtorrent import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.socks_configurator import SocksServersComponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker

    _rest_manager: RESTManager

    async def run(self):
        await self.get_component(ReporterComponent)

        config = self.session.config

        metadata_store_component = await self.require_component(MetadataStoreComponent)
        libtorrent_component = await self.require_component(LibtorrentComponent)
        rest_component = await self.require_component(RESTComponent)
        self._rest_manager = rest_component.rest_manager

        socks_servers_component = await self.require_component(SocksServersComponent)

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store_component.mds)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=libtorrent_component.download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_listen_ports=socks_servers_component.socks_ports,
                                         metadata_store=metadata_store_component.mds)
        self.torrent_checker = torrent_checker
        self._rest_manager.get_endpoint('state').readable_status = STATE_START_TORRENT_CHECKER

        await torrent_checker.initialize()
        self._rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', torrent_checker,
                                                  skip_missing=True)

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        self._rest_manager.set_attr_for_endpoints(['metadata'], 'torrent_checker', None, skip_missing=True)

        await self.release_component(RESTComponent)

        await self.torrent_checker.shutdown()
