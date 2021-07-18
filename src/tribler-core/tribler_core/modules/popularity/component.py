from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8
from tribler_core.awaitable_resources import POPULARITY_COMMUNITY, TORRENT_CHECKER, MY_PEER, IPV8_SERVICE, \
    METADATA_STORE, IPV8_BOOTSTRAPPER

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.popularity.community import PopularityCommunity
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker

INFINITE = -1


class PopularityComponent(Component):
    role = POPULARITY_COMMUNITY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        peer = await self.use(mediator, MY_PEER)
        metadata_store = await self.use(mediator, METADATA_STORE)
        torrent_checker = await self.use(mediator, TORRENT_CHECKER)

        community = PopularityCommunity(peer, ipv8.endpoint, ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store,
                                        torrent_checker=torrent_checker)
        self.provide(mediator, community)

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)
        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

    async def shutdown(self, mediator):
        await self._provided_object.unload()

        await super().shutdown(mediator)
