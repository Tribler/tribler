from tribler_core.awaitable_resources import METADATA_STORE
from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator


class MetadataStoreComponent(Component):
    resource_label = METADATA_STORE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._endpoints = ['search', 'metadata', 'remote_query', 'downloads', 'channels', 'collections', 'statistics']
        self._api_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet
        metadata_db_name = 'metadata.db' if not chant_testnet else 'metadata_testnet.db'
        database_path = config.state_dir / 'sqlite' / metadata_db_name

        metadata_store = MetadataStore(database_path, channels_dir, mediator.trustchain_keypair,
                                       notifier=mediator.notifier,
                                       disable_sync=config.core_test_mode)
        self.provide(mediator, metadata_store)

        api_manager = self._api_manager = await self.use(mediator, RESTManager)
        for endpoint in self._endpoints:
            api_manager.get(endpoint).mds = metadata_store

        if config.core_test_mode:
            generate_test_channels(metadata_store)

    async def shutdown(self, mediator):
        # Release endpoints
        for endpoint in self._endpoints:
            self._api_manager.get(endpoint).mds = None
        self.release_dependency(mediator, RESTManager)

        await self.unused()
        mediator.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.metadata_store.shutdown()
        await super().shutdown(mediator)
