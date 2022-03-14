from tribler.core.components.base import Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.utilities.rest_utils import path_to_uri


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
            state_dir=config.state_dir,
            notifier=self.session.notifier,
            peer_mid=key_component.primary_key.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            socks_listen_ports=socks_ports,
            dummy_mode=config.gui_test_mode)
        self.download_manager.initialize()

        await self.download_manager.load_checkpoints()

        if config.gui_test_mode:
            from tribler.core.tests.tools.common import TORRENT_WITH_DIRS  # pylint: disable=import-outside-toplevel
            uri = path_to_uri(TORRENT_WITH_DIRS)
            await self.download_manager.start_download_from_uri(uri)

    async def shutdown(self):
        await super().shutdown()
        if self.download_manager:
            self.download_manager.stop_download_states_callback()
            await self.download_manager.shutdown()
