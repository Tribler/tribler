from tribler_common.simpledefs import NTFY, STATEDIR_DB_DIR

from tribler_core.components.interfaces.masterkey import MasterKeyComponent
from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.utils import generate_test_channels
from tribler_core.restapi.rest_manager import RESTManager


class MetadataStoreComponent(Component):
    mds: MetadataStore

    _rest_manager: RESTManager
    _endpoints = ['search', 'metadata', 'remote_query', 'downloads', 'channels', 'collections', 'statistics']

    async def run(self):
        await self.use(ReporterComponent, required=False)
        await self.use(UpgradeComponent, required=False)

        rest_component = await self.use(RESTComponent)
        self._rest_manager = rest_component.rest_manager if rest_component else None

        config = self.session.config
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)
        chant_testnet = config.general.testnet or config.chant.testnet

        metadata_db_name = 'metadata.db'
        if chant_testnet:
            metadata_db_name = 'metadata_testnet.db'
        elif config.gui_test_mode:  # Avoid interfering with the main database in test mode
            # Note we don't use in-memory database in core test mode, because MDS uses threads,
            # and SQLite creates a different in-memory DB for each connection by default.
            # To change this behaviour, we have to use url-based SQLite initialization syntax,
            # which is not supported by PonyORM yet.
            metadata_db_name = 'metadata_gui_test.db'

        database_path = config.state_dir / STATEDIR_DB_DIR / metadata_db_name

        # Make sure that we start with a clean metadata database when in GUI mode every time.
        if config.gui_test_mode and database_path.exists():
            self.logger.info("Wiping metadata database in GUI test mode")
            database_path.unlink(missing_ok=True)

        masterkey = await self.use(MasterKeyComponent)

        metadata_store = MetadataStore(
            database_path,
            channels_dir,
            masterkey.keypair,
            notifier=self.session.notifier,
            disable_sync=config.gui_test_mode,
        )
        self.mds = metadata_store
        rest_manager.set_attr_for_endpoints(self.endpoints, 'mds', metadata_store, skip_missing=True)
        self.session.notifier.add_observer(NTFY.TORRENT_METADATA_ADDED,
                                           metadata_store.TorrentMetadata.add_ffa_from_dict)

        if config.gui_test_mode:
            generate_test_channels(metadata_store)

    async def shutdown(self):
        # Release endpoints
        if self._rest_manager:
            self._rest_manager.set_attr_for_endpoints(self._endpoints, 'mds', None, skip_missing=True)
        await self.release(RESTComponent)

        await self.unused.wait()
        self.session.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.mds.shutdown()
