from tribler.core.components.component import Component
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.community.knowledge_community import KnowledgeCommunity
from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
from tribler.core.components.metadata_store import metadata_store_component
from tribler.core.components.metadata_store.utils import generate_test_channels
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class KnowledgeComponent(Component):
    tribler_should_stop_on_component_error = False

    community: KnowledgeCommunity = None
    knowledge_db: KnowledgeDatabase = None
    rules_processor: KnowledgeRulesProcessor = None
    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        key_component = await self.require_component(KeyComponent)
        mds_component = await self.require_component(metadata_store_component.MetadataStoreComponent)

        db_path = self.session.config.state_dir / STATEDIR_DB_DIR / "knowledge.db"
        if self.session.config.gui_test_mode:
            db_path = ":memory:"

        self.knowledge_db = KnowledgeDatabase(str(db_path), create_tables=True)
        self.community = KnowledgeCommunity(
            self._ipv8_component.peer,
            self._ipv8_component.ipv8.endpoint,
            self._ipv8_component.ipv8.network,
            db=self.knowledge_db,
            key=key_component.secondary_key
        )
        self.rules_processor = KnowledgeRulesProcessor(
            notifier=self.session.notifier,
            db=self.knowledge_db,
            mds=mds_component.mds,
        )
        self.rules_processor.start()

        self._ipv8_component.initialise_community_by_default(self.community)

        if self.session.config.gui_test_mode:
            generate_test_channels(mds_component.mds, self.knowledge_db)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
        if self.rules_processor:
            await self.rules_processor.shutdown()
        if self.knowledge_db:
            self.knowledge_db.shutdown()
