from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.popularity.community import PopularityCommunity
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker

INFINITE = -1


class PopularityComponent(Component):
    start_async = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.community = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        ipv8 = await mediator.awaitable_components.get(IPv8)
        peer = await mediator.awaitable_components.get(Peer)
        metadata_store = await mediator.awaitable_components.get(MetadataStore)

        if not ipv8 or not peer or not metadata_store:
            return

        community = PopularityCommunity(peer, ipv8.endpoint, ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store)
        self.community = community
        community.torrent_checker = await mediator.awaitable_components.get(TorrentChecker)

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        if bootstrapper := await mediator.awaitable_components.get(Bootstrapper):
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
