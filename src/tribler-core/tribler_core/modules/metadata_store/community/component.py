from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.awaitable_resources import GIGACHANNEL_COMMUNITY, IPV8_SERVICE, METADATA_STORE, MY_PEER, REST_MANAGER, \
    IPV8_BOOTSTRAPPER

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity, \
    GigaChannelTestnetCommunity
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.session import Mediator

INFINITE = -1


class GigaChannelComponent(Component):
    role = GIGACHANNEL_COMMUNITY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rest_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config
        notifier = mediator.notifier

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        metadata_store = await self.use(mediator, METADATA_STORE)
        peer = await self.use(mediator, MY_PEER)
        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)
        rest_manager = self._rest_manager = await self.use(mediator, REST_MANAGER)

        giga_channel_cls = GigaChannelTestnetCommunity if config.general.testnet else GigaChannelCommunity
        community = giga_channel_cls(peer, ipv8.endpoint, ipv8.network,
                                     notifier=notifier,
                                     settings=config.chant,
                                     rqc_settings=config.remote_query_community,
                                     metadata_store=metadata_store,
                                     max_peers=50,
                                     )
        self.provide(mediator, community)

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

        rest_manager.get_endpoint('remote_query').gigachannel_community = community
        rest_manager.get_endpoint('channels').gigachannel_community = community
        rest_manager.get_endpoint('collections').gigachannel_community = community

    async def shutdown(self, mediator):
        self._rest_manager.get_endpoint('remote_query').gigachannel_community = None
        self._rest_manager.get_endpoint('channels').gigachannel_community = None
        self._rest_manager.get_endpoint('collections').gigachannel_community = None
        self.release_dependency(mediator, REST_MANAGER)

        await self._provided_object.unload()
        await super().shutdown(mediator)
