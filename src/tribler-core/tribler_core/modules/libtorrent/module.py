from asyncio import get_event_loop

from tribler_common.simpledefs import STATE_LOAD_CHECKPOINTS, STATE_START_LIBTORRENT, STATE_CHECKPOINTS_LOADED
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator


class LibtorrentComponent(Component):
    start_async = True
    provided_futures = (DownloadManager, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.download_manager = None

    def prepare_futures(self, mediator):
        mediator.awaitable_components[DownloadManager] = get_event_loop().create_future()

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config

        api_manager = await mediator.awaitable_components.get(RESTManager)

        def set_state(state):
            api_manager.get_endpoint('state').readable_status = state

        set_state(STATE_START_LIBTORRENT)
        self.download_manager = download_manager = DownloadManager(
            config=config.libtorrent,
            state_dir=config.state_dir,
            notifier=mediator.notifier,
            peer_mid=mediator.trustchain_keypair.key_to_hash(),
            download_defaults=config.download_defaults,
            bootstrap_infohash=config.bootstrap.infohash,
            dummy_mode=config.core_test_mode)

        mediator.awaitable_components[DownloadManager].set_result(download_manager)

        download_manager.initialize()

        set_state(STATE_LOAD_CHECKPOINTS)
        await download_manager.load_checkpoints()
        set_state(STATE_CHECKPOINTS_LOADED)

        if api_manager:
            api_manager.get_endpoint('createtorrent').download_manager = download_manager
            api_manager.get_endpoint('libtorrent').download_manager = download_manager
            api_manager.get_endpoint('torrentinfo').download_manager = download_manager
            api_manager.get_endpoint('downloads').download_manager = download_manager
            api_manager.get_endpoint('channels').download_manager = download_manager
            api_manager.get_endpoint('collections').download_manager = download_manager
            api_manager.get_endpoint('settings').download_manager = download_manager

        if config.core_test_mode:
            uri = "magnet:?xt=urn:btih:0000000000000000000000000000000000000000"
            await download_manager.start_download_from_uri(uri)

    async def shutdown(self, mediator):
        await super().shutdown(mediator)

        self.download_manager.stop_download_states_callback()
        await self.download_manager.shutdown()
