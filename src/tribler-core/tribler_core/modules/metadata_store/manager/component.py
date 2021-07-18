from tribler_core.awaitable_resources import GIGACHANNEL_MANAGER, DOWNLOAD_MANAGER, METADATA_STORE, REST_MANAGER
from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager
from tribler_core.session import Mediator


class GigachannelManagerComponent(Component):
    role = GIGACHANNEL_MANAGER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._api_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        download_manager = await self.use(mediator, DOWNLOAD_MANAGER)
        metadata_store = await self.use(mediator, METADATA_STORE)

        manager = GigaChannelManager(notifier=notifier,
                                     metadata_store=metadata_store,
                                     download_manager=download_manager)
        if not config.core_test_mode:
            manager.start()

        api_manager = self._api_manager = await self.use(mediator, REST_MANAGER)
        api_manager.get_endpoint('channels').gigachannel_manager = manager
        api_manager.get_endpoint('collections').gigachannel_manager = manager

        self.provide(mediator, manager)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")
        self._api_manager.get_endpoint('channels').gigachannel_manager = None
        self._api_manager.get_endpoint('collections').gigachannel_manager = None
        self.release_dependency(mediator, REST_MANAGER)

        await self.manager.shutdown()
        await super().shutdown(mediator)
