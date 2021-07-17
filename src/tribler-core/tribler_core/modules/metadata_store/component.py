from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.session import Mediator
from tribler_core.utilities.utilities import froze_it


@froze_it
class MetadataStoreComponent(Component):
    start_async = True
    provided_futures = (MetadataStore,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata_store = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet
        metadata_db_name = 'metadata.db' if not chant_testnet else 'metadata_testnet.db'
        database_path = config.state_dir / 'sqlite' / metadata_db_name

        metadata_store = MetadataStore(
            database_path, channels_dir, mediator.trustchain_keypair,
            notifier=mediator.notifier,
            disable_sync=config.core_test_mode)
        self.metadata_store = metadata_store

        mediator.awaitable_components[MetadataStore].set_result(metadata_store)

        if api_manager := await mediator.awaitable_components.get(RESTManager):
            api_manager.get_endpoint('search').mds = metadata_store
            api_manager.get_endpoint('metadata').mds = metadata_store
            api_manager.get_endpoint('remote_query').mds = metadata_store
            api_manager.get_endpoint('downloads').mds = metadata_store
            api_manager.get_endpoint('channels').mds = metadata_store
            api_manager.get_endpoint('collections').mds = metadata_store
            api_manager.get_endpoint('statistics').mds = metadata_store

        if config.core_test_mode:
            generate_test_channels(metadata_store)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.metadata_store.shutdown()
        await super().shutdown(mediator)
