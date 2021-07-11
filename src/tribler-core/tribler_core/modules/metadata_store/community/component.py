from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity, \
    GigaChannelTestnetCommunity
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.session import Mediator

INFINITE = -1


class GigaChannelComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        config = mediator.config
        notifier = mediator.notifier

        ipv8 = await mediator.optional['ipv8']
        peer = mediator.optional.get('peer', None)
        bootstrapper = mediator.optional.get('bootstrapper', None)
        metadata_store = mediator.optional.get('metadata_store', None)
        api_manager = mediator.optional.get('api_manager', None)

        if not ipv8 or not metadata_store:
            return
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

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        if api_manager:
            api_manager.get_endpoint('remote_query').gigachannel_community = community
            api_manager.get_endpoint('channels').gigachannel_community = community
            api_manager.get_endpoint('collections').gigachannel_community = community

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
