from tribler_common.simpledefs import STATE_CHECKPOINTS_LOADED, STATE_LOAD_CHECKPOINTS, STATE_START_LIBTORRENT

from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.socks_configurator import SocksServersComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager


class LibtorrentComponent(RestfulComponent):
    download_manager: DownloadManager = None

    async def run(self):
        await super().run()
        await self.get_component(UpgradeComponent)
        socks_servers_component = await self.require_component(SocksServersComponent)
        master_key_component = await self.require_component(MasterKeyComponent)

        config = self.session.config

        await self.set_readable_status(STATE_START_LIBTORRENT)
        self.download_manager = DownloadManager(
            config=config.libtorrent,
            state_dir=config.state_dir,
            notifier=self.session.notifier,
            peer_mid=master_key_component.keypair.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            socks_listen_ports=socks_servers_component.socks_ports,
            dummy_mode=config.gui_test_mode)
        self.download_manager.initialize()

        await self.set_readable_status(STATE_LOAD_CHECKPOINTS)
        await self.download_manager.load_checkpoints()
        await self.set_readable_status(STATE_CHECKPOINTS_LOADED)

        endpoints = ['createtorrent', 'libtorrent', 'torrentinfo', 'downloads', 'channels', 'collections', 'settings']
        await self.init_endpoints(endpoints=endpoints, values={'download_manager': self.download_manager})

        if config.gui_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await self.download_manager.start_download_from_uri(uri)

    async def shutdown(self):
        await super().shutdown()
        if self.download_manager:
            self.download_manager.stop_download_states_callback()
            await self.download_manager.shutdown()
