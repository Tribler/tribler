from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.components.interfaces.ipv8 import Ipv8Component
from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.popularity import PopularityComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.torrent_checker import TorrentCheckerComponent
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.popularity.community import PopularityCommunity

INFINITE = -1


class PopularityComponentImp(PopularityComponent):
    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        ipv8_component = await self.use(Ipv8Component)
        ipv8 = self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        metadata_store = (await self.use(MetadataStoreComponent)).mds

        torrent_checker_component = await self.use(TorrentCheckerComponent)
        torrent_checker = torrent_checker_component.torrent_checker if torrent_checker_component.enabled else None

        community = PopularityCommunity(peer, ipv8.endpoint, ipv8.network,
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store,
                                        torrent_checker=torrent_checker)
        self.community = community

        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        ipv8.overlays.append(community)

    async def shutdown(self):
        await self._ipv8.unload_overlay(self.community)
