from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.utilities.utilities import froze_it


@froze_it
class MetadataStoreComponentImp(MetadataStoreComponent):
    endpoints = ['search', 'metadata', 'remote_query', 'downloads', 'channels', 'collections', 'statistics']
    rest_manager: RESTManager

    async def run(self):
        config = self.session.config

        await self.use(UpgradeComponent)
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager

        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet
        metadata_db_name = 'metadata.db' if not chant_testnet else 'metadata_testnet.db'
        database_path = config.state_dir / 'sqlite' / metadata_db_name

        metadata_store = MetadataStore(
            database_path,
            channels_dir,
            self.session.trustchain_keypair,
            notifier=self.session.notifier,
            disable_sync=config.core_test_mode,
        )
        self.mds = metadata_store
        # self.provide(mediator, metadata_store)

        for endpoint in self._endpoints:
            rest_manager.get_endpoint(endpoint).mds = metadata_store

        if config.core_test_mode:
            generate_test_channels(metadata_store)

    async def shutdown(self):
        # Release endpoints
        for endpoint in self._endpoints:
            self._rest_manager.get_endpoint(endpoint).mds = None
        await self.unuse(RESTComponent)

        await self.unused.wait()
        self.session.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.mds.shutdown()
