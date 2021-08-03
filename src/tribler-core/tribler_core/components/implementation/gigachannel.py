from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.components.interfaces.gigachannel import GigaChannelComponent
from tribler_core.components.interfaces.ipv8 import Ipv8BootstrapperComponent, Ipv8Component, Ipv8PeerComponent
from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.modules.metadata_store.community.gigachannel_community import (
    GigaChannelCommunity,
    GigaChannelTestnetCommunity,
)
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.restapi.rest_manager import RESTManager

INFINITE = -1


class GigaChannelComponentImp(GigaChannelComponent):
    rest_manager: RESTManager

    async def run(self):
        config = self.session.config
        notifier = self.session.notifier

        ipv8 = (await self.use(Ipv8Component)).ipv8
        metadata_store = (await self.use(MetadataStoreComponent)).mds
        peer = (await self.use(Ipv8PeerComponent)).peer
        bootstrapper = (await self.use(Ipv8BootstrapperComponent)).bootstrapper
        rest_manager = self.rest_manager = (await self.use(RESTComponent)).rest_manager

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
        # self.provide(mediator, community)

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

        rest_manager.get_endpoint('remote_query').gigachannel_community = community
        rest_manager.get_endpoint('channels').gigachannel_community = community
        rest_manager.get_endpoint('collections').gigachannel_community = community

    async def shutdown(self):
        self.rest_manager.get_endpoint('remote_query').gigachannel_community = None
        self.rest_manager.get_endpoint('channels').gigachannel_community = None
        self.rest_manager.get_endpoint('collections').gigachannel_community = None
        await self.release(RESTComponent)

        await self.community.unload()
