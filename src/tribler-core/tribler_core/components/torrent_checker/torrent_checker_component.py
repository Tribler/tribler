from tribler_common.simpledefs import STATE_START_TORRENT_CHECKER

from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi.restapi_component import RestfulComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager


class TorrentCheckerComponent(RestfulComponent):
    torrent_checker: TorrentChecker = None

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
        await super().shutdown()
        if self.torrent_checker:
            await self.torrent_checker.shutdown()
