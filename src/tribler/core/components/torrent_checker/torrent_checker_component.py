from tribler.core.components.component import Component
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker = None

    async def run(self):
        await super().run()

        config = self.session.config

        metadata_store_component = await self.require_component(MetadataStoreComponent)
        libtorrent_component = await self.require_component(LibtorrentComponent)
        socks_servers_component = await self.require_component(SocksServersComponent)

        socks_ports = socks_servers_component.socks_ports
        num_hops = config.download_defaults.number_hops
        num_ports = len(socks_ports)
        if num_ports < num_hops:
            self.logger.warning(f"Failed to run TorrentCheckerComponent. "
                                f"Minimum number of socks ports for default number of hops not available. "
                                f'Required hops: {num_hops}. Actual ports: {num_ports}')
            raise RuntimeError("Not enough socks port available for default number of hops.")\

        socks_proxy = ('127.0.0.1', socks_ports[num_hops - 1]) if num_hops > 0 else None
        tracker_manager = TrackerManager(state_dir=config.state_dir, metadata_store=metadata_store_component.mds)
        torrent_checker = TorrentChecker(config=config,
                                         download_manager=libtorrent_component.download_manager,
                                         notifier=self.session.notifier,
                                         tracker_manager=tracker_manager,
                                         socks_proxy=socks_proxy,
                                         metadata_store=metadata_store_component.mds)
        self.torrent_checker = torrent_checker
        await torrent_checker.initialize()

    async def shutdown(self):
        await super().shutdown()
        if self.torrent_checker:
            await self.torrent_checker.shutdown()
