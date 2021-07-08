from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.popularity.community import PopularityCommunity

INFINITE = -1


class PopularityComponent(Component):
    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        ipv8 = mediator.optional.get('ipv8', None)
        peer = mediator.optional.get('peer', None)
        bootstrapper = mediator.optional.get('bootstrapper', None)
        torrent_checker = mediator.optional.get('torrent_checker', None)
        metadata_store = mediator.optional.get('metadata_store', None)

        if not ipv8 or not metadata_store:
            return

        community = PopularityCommunity(peer, ipv8.endpoint, ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store,
                                        torrent_checker=torrent_checker)

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
