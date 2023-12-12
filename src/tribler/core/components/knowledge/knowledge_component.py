from tribler.core.components.component import Component
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.community.knowledge_community import KnowledgeCommunity
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor


class KnowledgeComponent(Component):
    tribler_should_stop_on_component_error = False

    community: KnowledgeCommunity = None
    rules_processor: KnowledgeRulesProcessor = None
    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        key_component = await self.require_component(KeyComponent)
        db_component = await self.require_component(DatabaseComponent)

        self.community = KnowledgeCommunity(
            self._ipv8_component.peer,
            self._ipv8_component.ipv8.endpoint,
            self._ipv8_component.ipv8.network,
            db=db_component.db,
            key=key_component.secondary_key
        )
        self.rules_processor = KnowledgeRulesProcessor(
            notifier=self.session.notifier,
            db=db_component.db,
            mds=db_component.mds,
        )
        self.rules_processor.start()

        self._ipv8_component.initialise_community_by_default(self.community)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
        if self.rules_processor:
            await self.rules_processor.shutdown()
