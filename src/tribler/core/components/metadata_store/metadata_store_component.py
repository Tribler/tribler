from tribler.core import notifications
from tribler.core.components.component import Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class MetadataStoreComponent(Component):
    mds: MetadataStore = None

    async def run(self):
        await super().run()

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

        key_component = await self.require_component(KeyComponent)

        metadata_store = MetadataStore(
            database_path,
            channels_dir,
            key_component.primary_key,
            notifier=self.session.notifier,
            disable_sync=config.gui_test_mode,
            tag_processor_version=KnowledgeRulesProcessor.version
        )
        self.mds = metadata_store
        self.session.notifier.add_observer(notifications.torrent_metadata_added,
                                           metadata_store.TorrentMetadata.add_ffa_from_dict)

    async def shutdown(self):
        await super().shutdown()
        if self.mds:
            self.mds.shutdown()
