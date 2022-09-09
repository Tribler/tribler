from tribler.core.components.component import Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent


class LibtorrentComponent(Component):
    download_manager: DownloadManager = None

    async def run(self):
        await super().run()
        config = self.session.config

        key_component = await self.require_component(KeyComponent)

        socks_ports = []
        if not config.gui_test_mode:
            socks_servers_component = await self.require_component(SocksServersComponent)
            socks_ports = socks_servers_component.socks_ports

        self.download_manager = DownloadManager(
            config=config.libtorrent,
            gui_test_mode=config.gui_test_mode,
            state_dir=config.state_dir,
            notifier=self.session.notifier,
            peer_mid=key_component.primary_key.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            socks_listen_ports=socks_ports,
            dummy_mode=config.gui_test_mode)
        self.download_manager.initialize()

        # load checkpoints in a background task to not delay initialization of dependent components (e.g. RESTComponent)
        self.download_manager.start()

    async def shutdown(self):
        await super().shutdown()
        if self.download_manager:
            await self.download_manager.shutdown()
