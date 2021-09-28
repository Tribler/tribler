from tribler_common.simpledefs import NTFY, STATEDIR_DB_DIR

from tribler_core.components.base import Component
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RestfulComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.metadata_store.utils import generate_test_channels
from tribler_core.restapi.rest_manager import RESTManager


class MetadataStoreComponent(RestfulComponent):
    mds: MetadataStore

    async def run(self):
        await self.get_component(ReporterComponent)
        await self.get_component(UpgradeComponent)

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

        master_key_component = await self.require_component(MasterKeyComponent)

        metadata_store = MetadataStore(
            database_path,
            channels_dir,
            master_key_component.keypair,
            notifier=self.session.notifier,
            disable_sync=config.gui_test_mode,
        )
        self.mds = metadata_store

        await self.init_endpoints(
            ['search', 'metadata', 'remote_query', 'downloads', 'channels', 'collections', 'statistics'],
            [('mds', metadata_store)]
        )

        self.session.notifier.add_observer(NTFY.TORRENT_METADATA_ADDED,
                                           metadata_store.TorrentMetadata.add_ffa_from_dict)

        if config.gui_test_mode:
            generate_test_channels(metadata_store)

    async def shutdown(self):
        await super().shutdown()
        self.session.notifier.notify_shutdown_state("Shutting down Metadata Store...")
        self.mds.shutdown()
