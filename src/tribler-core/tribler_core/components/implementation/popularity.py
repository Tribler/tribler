from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8
from tribler_core.components.base import Component, ComponentError
from tribler_core.components.implementation.ipv8 import Ipv8Component
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.torrent_checker import TorrentCheckerComponent
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.popularity.community import PopularityCommunity

INFINITE = -1


class PopularityComponent(Component):
    community: PopularityCommunity
    _ipv8: IPv8

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        ipv8_component = await self.use(Ipv8Component)
        if not ipv8_component:
            raise ComponentError(f'Missed dependency: {self.__class__.__name__} requires Ipv8Component to be active')

        self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        metadata_store_component = await self.use(MetadataStoreComponent)
        metadata_store = metadata_store_component.mds if metadata_store_component else None

        torrent_checker_component = await self.use(TorrentCheckerComponent)
        torrent_checker = torrent_checker_component.torrent_checker if torrent_checker_component else None

        community = PopularityCommunity(peer, self._ipv8.endpoint, self._ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store,
                                        torrent_checker=torrent_checker)
        self.community = community

        self._ipv8.add_strategy(community, RandomWalk(community), 30)
        self._ipv8.add_strategy(community, RemovePeers(community), INFINITE)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

    async def shutdown(self):
        await self._ipv8.unload_overlay(self.community)
