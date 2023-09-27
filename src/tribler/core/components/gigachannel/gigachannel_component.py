from ipv8.peerdiscovery.network import Network

from tribler.core.components.component import Component
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.gigachannel.community.gigachannel_community import (
    GigaChannelCommunity,
    GigaChannelTestnetCommunity,
)
from tribler.core.components.gigachannel.community.sync_strategy import RemovePeers
from tribler.core.components.ipv8.ipv8_component import INFINITE, Ipv8Component
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.reporter.reporter_component import ReporterComponent


class GigaChannelComponent(Component):
    community: GigaChannelCommunity = None
    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

        config = self.session.config
        notifier = self.session.notifier

        self._ipv8_component = await self.require_component(Ipv8Component)
        metadata_store_component = await self.require_component(MetadataStoreComponent)
        db_component = await self.get_component(DatabaseComponent)

        giga_channel_cls = GigaChannelTestnetCommunity if config.general.testnet else GigaChannelCommunity
        community = giga_channel_cls(
            self._ipv8_component.peer,
            self._ipv8_component.ipv8.endpoint,
            Network(),
            notifier=notifier,
            settings=config.chant,
            rqc_settings=config.remote_query_community,
            metadata_store=metadata_store_component.mds,
            max_peers=50,
            tribler_db=db_component.db if db_component else None
        )
        self.community = community
        self._ipv8_component.initialise_community_by_default(community, default_random_walk_max_peers=30)
        self._ipv8_component.ipv8.add_strategy(community, RemovePeers(community), INFINITE)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
