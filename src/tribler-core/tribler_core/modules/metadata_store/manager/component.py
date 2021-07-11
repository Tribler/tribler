from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator


class GigachannelManagerComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        download_manager = await mediator.awaitable_components.get(DownloadManager)
        metadata_store = await mediator.awaitable_components.get(MetadataStore)

        if not metadata_store or not download_manager:
            return

        manager = GigaChannelManager(notifier=notifier,
                                     metadata_store=metadata_store,
                                     download_manager=download_manager)
        if not config.core_test_mode:
            manager.start()

        if api_manager := await mediator.awaitable_components.get(RESTManager):
            api_manager.get_endpoint('channels').gigachannel_manager = manager
            api_manager.get_endpoint('collections').gigachannel_manager = manager

        self.manager = manager

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")
        await self.manager.shutdown()
        await super().shutdown(mediator)
