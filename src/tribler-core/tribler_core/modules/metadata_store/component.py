from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.session import Mediator


class MetadataStoreComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata_store = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config
        trustchain_keypair = mediator.trustchain_keypair
        notifier = mediator.notifier

        api_manager = mediator.optional.get('api_manager', None)

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet
        metadata_db_name = 'metadata.db' if not chant_testnet else 'metadata_testnet.db'
        database_path = config.state_dir / 'sqlite' / metadata_db_name

        metadata_store = MetadataStore(
            database_path, channels_dir, trustchain_keypair,
            notifier=notifier,
            disable_sync=config.core_test_mode)

        if api_manager:
            api_manager.get_endpoint('search').mds = metadata_store
            api_manager.get_endpoint('metadata').mds = metadata_store
            api_manager.get_endpoint('remote_query').mds = metadata_store
            api_manager.get_endpoint('downloads').mds = metadata_store
            api_manager.get_endpoint('channels').mds = metadata_store
            api_manager.get_endpoint('collections').mds = metadata_store

        if config.core_test_mode:
            generate_test_channels(metadata_store)

        mediator.optional['metadata_store'] = metadata_store
        self.metadata_store = metadata_store

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        mediator.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.metadata_store.shutdown()
