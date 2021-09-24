from tribler_common.simpledefs import STATE_CHECKPOINTS_LOADED, STATE_LOAD_CHECKPOINTS, STATE_START_LIBTORRENT
from tribler_core.components.base import Component
from tribler_core.components.implementation.masterkey import MasterKeyComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.components.implementation.socks_configurator import SocksServersComponent
from tribler_core.components.implementation.upgrade import UpgradeComponent
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.restapi.rest_manager import RESTManager


class LibtorrentComponent(Component):
    download_manager: DownloadManager

    _endpoints = ['createtorrent', 'libtorrent', 'torrentinfo', 'downloads', 'channels', 'collections', 'settings']
    _rest_manager: RESTManager

    async def run(self):
        await self.use(ReporterComponent)
        await self.use(UpgradeComponent)
        socks_servers_component = await self.use(SocksServersComponent)
        if not socks_servers_component:
            self._missed_dependency(SocksServersComponent.__name__)

        master_key_component = await self.use(MasterKeyComponent)
        if not master_key_component:
            self._missed_dependency(MasterKeyComponent.__name__)

        config = self.session.config

        # TODO: move rest_manager check after download manager init. Use notifier instead of direct call to endpoint
        rest_component = await self.use(RESTComponent)
        if not rest_component:
            self._missed_dependency(RESTComponent.__name__)

        self._rest_manager = rest_component.rest_manager
        state_endpoint = self._rest_manager.get_endpoint('state') if self._rest_manager else None
        if state_endpoint:
            state_endpoint.readable_status = STATE_START_LIBTORRENT

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
        if state_endpoint:
            state_endpoint.readable_status = STATE_LOAD_CHECKPOINTS
        await self.download_manager.load_checkpoints()
        if state_endpoint:
            state_endpoint.readable_status = STATE_CHECKPOINTS_LOADED

        self._rest_manager.set_attr_for_endpoints(self._endpoints, 'download_manager', self.download_manager,
                                                  skip_missing=True)
        if config.gui_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await self.download_manager.start_download_from_uri(uri)

    async def shutdown(self):
        # Release endpoints
        self._rest_manager.set_attr_for_endpoints(self._endpoints, 'download_manager', None, skip_missing=True)

        await self.release(RESTComponent)

        self.download_manager.stop_download_states_callback()
        await self.download_manager.shutdown()
