from tribler_common.simpledefs import STATE_CHECKPOINTS_LOADED, STATE_LOAD_CHECKPOINTS, STATE_START_LIBTORRENT

from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.socks_configurator import SocksServersComponent
from tribler_core.components.interfaces.trustchain import TrustchainComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.restapi.rest_manager import RESTManager


class LibtorrentComponentImp(LibtorrentComponent):
    endpoints = ['createtorrent', 'libtorrent', 'torrentinfo', 'downloads', 'channels', 'collections', 'settings']
    rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent)
        await self.use(UpgradeComponent)
        socks_ports = (await self.use(SocksServersComponent)).socks_ports
        trustchain = await self.use(TrustchainComponent)

        config = self.session.config

        # TODO: move rest_manager check after download manager init. Use notifier instead of direct call to endpoint
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager
        state_endpoint = rest_manager.get_endpoint('state')

        state_endpoint.readable_status = STATE_START_LIBTORRENT
        download_manager = DownloadManager(
            config=config.libtorrent,
            state_dir=config.state_dir,
            notifier=self.session.notifier,
            peer_mid=trustchain.keypair.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            socks_listen_ports=socks_ports,
            dummy_mode=config.core_test_mode)
        download_manager.initialize()

        state_endpoint.readable_status = STATE_LOAD_CHECKPOINTS
        await download_manager.load_checkpoints()
        state_endpoint.readable_status = STATE_CHECKPOINTS_LOADED

        self.download_manager = download_manager
        # self.provide(mediator, download_manager)

        for endpoint in self.endpoints:
            rest_manager.get_endpoint(endpoint).download_manager = download_manager

        if config.core_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await download_manager.start_download_from_uri(uri)

    async def shutdown(self):
        # Release endpoints
        for endpoint in self.endpoints:
            self.rest_manager.get_endpoint(endpoint).download_manager = None
        await self.release(RESTComponent)

        self.download_manager.stop_download_states_callback()
        await self.download_manager.shutdown()
