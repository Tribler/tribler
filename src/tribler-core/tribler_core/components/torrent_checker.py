from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER

from tribler_core.components.base import Component
from tribler_core.components.libtorrent import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.socks_configurator import SocksServersComponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.modules.torrent_checker.tracker_manager import TrackerManager
from tribler_core.restapi.rest_manager import RESTManager


class TorrentCheckerComponent(RestfulComponent):
    torrent_checker: TorrentChecker

    async def run(self):
        await super().run()

        config = self.session.config

        metadata_store_component = await self.require_component(MetadataStoreComponent)
        libtorrent_component = await self.require_component(LibtorrentComponent)
        socks_servers_component = await self.require_component(SocksServersComponent)

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store_component.mds)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=libtorrent_component.download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_listen_ports=socks_servers_component.socks_ports,
                                         metadata_store=metadata_store_component.mds)
        self.torrent_checker = torrent_checker
        await self.set_readable_status(STATE_START_TORRENT_CHECKER)
        await torrent_checker.initialize()
        await self.init_endpoints(endpoints=['metadata'], values={'torrent_checker': torrent_checker})

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Torrent Checker...")
        await super().shutdown()
        await self.torrent_checker.shutdown()
