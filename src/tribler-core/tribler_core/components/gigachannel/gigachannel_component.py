from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8.peerdiscovery.network import Network

from tribler_core.components.gigachannel.community.gigachannel_community import (
    GigaChannelCommunity,
    GigaChannelTestnetCommunity,
)
from tribler_core.components.gigachannel.community.sync_strategy import RemovePeers
from tribler_core.components.ipv8 import INFINITE, Ipv8Component
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RestfulComponent


class GigaChannelComponent(RestfulComponent):
    community: GigaChannelCommunity

    _ipv8_component: Ipv8Component

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

        config = self.session.config
        notifier = self.session.notifier

        self._ipv8_component = await self.require_component(Ipv8Component)
        metadata_store_component = await self.require_component(MetadataStoreComponent)

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
        )
        self.community = community
        self._ipv8_component.initialise_community_by_default(community, default_random_walk_max_peers=30)
        self._ipv8_component.ipv8.add_strategy(community, RemovePeers(community), INFINITE)
        await self.init_endpoints(endpoints=['remote_query', 'channels', 'collections'],
                                  values={'gigachannel_community': community})

    async def shutdown(self):
        await super().shutdown()
        await self._ipv8_component.unload_community(self.community)
