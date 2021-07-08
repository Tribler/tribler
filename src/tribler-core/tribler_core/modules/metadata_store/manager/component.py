from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager
from tribler_core.session import Mediator


class GigachannelManagerComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        metadata_store = mediator.optional.get('metadata_store', None)
        download_manager = mediator.optional.get('download_manager', None)
        api_manager = mediator.optional.get('api_manager', None)

        if not metadata_store or not download_manager:
            return

        manager = GigaChannelManager(notifier=notifier,
                                     metadata_store=metadata_store,
                                     download_manager=download_manager)
        if not config.core_test_mode:
            manager.start()

        if api_manager:
            api_manager.get_endpoint('channels').gigachannel_manager = manager
            api_manager.get_endpoint('collections').gigachannel_manager = manager

        self.manager = manager

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        mediator.notifier.notify_shutdown_state("Shutting down Gigachannel Manager...")
        await self.manager.shutdown()
