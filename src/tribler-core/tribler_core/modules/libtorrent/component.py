from tribler_common.simpledefs import STATE_LOAD_CHECKPOINTS, STATE_START_LIBTORRENT, STATE_CHECKPOINTS_LOADED
from tribler_core.awaitable_resources import DOWNLOAD_MANAGER, REST_MANAGER, UPGRADER
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.session import Mediator


class LibtorrentComponent(Component):
    role = DOWNLOAD_MANAGER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._endpoints = ['createtorrent', 'libtorrent', 'torrentinfo', 'downloads', 'channels', 'collections',
                           'settings']
        self._rest_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        await mediator.optional[UPGRADER]._resource_initialized_event.wait()

        config = mediator.config

        # TODO: move rest_manager check after download manager init. Use notifier instead of direct call to endpoint
        rest_manager = self._rest_manager = await self.use(mediator, REST_MANAGER)
        state_endpoint = rest_manager.get_endpoint('state')

        state_endpoint.readable_status = STATE_START_LIBTORRENT
        download_manager = DownloadManager(
            config=config.libtorrent,
            state_dir=config.state_dir,
            notifier=mediator.notifier,
            peer_mid=mediator.trustchain_keypair.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            dummy_mode=config.core_test_mode)
        download_manager.initialize()

        state_endpoint.readable_status = STATE_LOAD_CHECKPOINTS
        await download_manager.load_checkpoints()
        state_endpoint.readable_status = STATE_CHECKPOINTS_LOADED

        self.provide(mediator, download_manager)

        for endpoint in self._endpoints:
            rest_manager.get_endpoint(endpoint).download_manager = download_manager

        if config.core_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await download_manager.start_download_from_uri(uri)

    async def shutdown(self, mediator):
        # Release endpoints
        for endpoint in self._endpoints:
            self._rest_manager.get_endpoint(endpoint).download_manager = None
        self.release_dependency(mediator, REST_MANAGER)

        self._provided_object.stop_download_states_callback()
        await self._provided_object.shutdown()
        await super().shutdown(mediator)
