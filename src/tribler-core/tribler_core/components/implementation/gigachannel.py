from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8
from tribler_core.components.base import Component
from tribler_core.components.implementation.ipv8 import Ipv8Component
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.modules.metadata_store.community.gigachannel_community import (
    GigaChannelCommunity,
    GigaChannelTestnetCommunity,
)
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.restapi.rest_manager import RESTManager

INFINITE = -1


class GigaChannelComponent(Component):
    rest_manager: RESTManager
    community: GigaChannelCommunity
    _ipv8: IPv8

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        notifier = self.session.notifier

        ipv8_component = await self.use(Ipv8Component)
        ipv8 = self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager
        metadata_store = (await self.use(MetadataStoreComponent)).mds

        giga_channel_cls = GigaChannelTestnetCommunity if config.general.testnet else GigaChannelCommunity
        community = giga_channel_cls(
            peer,
            ipv8.endpoint,
            ipv8.network,
            notifier=notifier,
            settings=config.chant,
            rqc_settings=config.remote_query_community,
            metadata_store=metadata_store,
            max_peers=50,
        )
        self.community = community

        ipv8.add_strategy(community, RandomWalk(community), 30)
        ipv8.add_strategy(community, RemovePeers(community), INFINITE)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        rest_manager.get_endpoint('remote_query').gigachannel_community = community
        rest_manager.get_endpoint('channels').gigachannel_community = community
        rest_manager.get_endpoint('collections').gigachannel_community = community

    async def shutdown(self):
        self.rest_manager.get_endpoint('remote_query').gigachannel_community = None
        self.rest_manager.get_endpoint('channels').gigachannel_community = None
        self.rest_manager.get_endpoint('collections').gigachannel_community = None
        await self.release(RESTComponent)

        await self._ipv8.unload_overlay(self.community)
