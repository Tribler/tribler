from tribler.core.components.component import Component
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker = None

    async def run(self):
        await super().run()

        config = self.session.config

        database_component = await self.require_component(DatabaseComponent)
        libtorrent_component = await self.require_component(LibtorrentComponent)
        socks_servers_component = await self.require_component(SocksServersComponent)

        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=database_component.mds)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=libtorrent_component.download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_listen_ports=socks_servers_component.socks_ports,
                                         metadata_store=database_component.mds)
        self.torrent_checker = torrent_checker
        await torrent_checker.initialize()

    async def shutdown(self):
        await super().shutdown()
        if self.torrent_checker:
            await self.torrent_checker.shutdown()
