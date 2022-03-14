import tribler.core.components.metadata_store.metadata_store_component as metadata_store_component
from tribler.core.components.base import Component
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.metadata_store.utils import generate_test_channels
from tribler.core.components.tag.community.tag_community import TagCommunity
from tribler.core.components.tag.db.tag_db import TagDatabase
from tribler.core.components.tag.rules.tag_rules_processor import TagRulesProcessor
from tribler.core.utilities.simpledefs import STATEDIR_DB_DIR


class TagComponent(Component):
    tribler_should_stop_on_component_error = False

    community: TagCommunity = None
    tags_db: TagDatabase = None
    rules_processor: TagRulesProcessor = None
    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        key_component = await self.require_component(KeyComponent)
        mds_component = await self.require_component(metadata_store_component.MetadataStoreComponent)

        db_path = self.session.config.state_dir / STATEDIR_DB_DIR / "tags.db"
        if self.session.config.gui_test_mode:
            db_path = ":memory:"

        self.tags_db = TagDatabase(str(db_path), create_tables=True)
        self.community = TagCommunity(
            self._ipv8_component.peer,
            self._ipv8_component.ipv8.endpoint,
            self._ipv8_component.ipv8.network,
            db=self.tags_db,
            tags_key=key_component.secondary_key
        )
        self.rules_processor = TagRulesProcessor(
            notifier=self.session.notifier,
            db=self.tags_db,
            mds=mds_component.mds,
        )
        self.rules_processor.start()

        self._ipv8_component.initialise_community_by_default(self.community)

        if self.session.config.gui_test_mode:
            generate_test_channels(mds_component.mds, self.tags_db)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
        if self.tags_db:
            self.tags_db.shutdown()
