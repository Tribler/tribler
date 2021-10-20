from ipv8.peerdiscovery.network import Network

from tribler_core.components.base import Component
from tribler_core.components.gigachannel.community.sync_strategy import RemovePeers
from tribler_core.components.ipv8.ipv8_component import INFINITE, Ipv8Component
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler_core.components.popularity.community.popularity_community import PopularityCommunity


class PopularityComponent(Component):
    community: PopularityCommunity = None

    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

        self._ipv8_component = await self.require_component(Ipv8Component)
        metadata_store_component = await self.require_component(MetadataStoreComponent)
        torrent_checker_component = await self.require_component(TorrentCheckerComponent)

        config = self.session.config
        community = PopularityCommunity(self._ipv8_component.peer,
                                        self._ipv8_component.ipv8.endpoint,
                                        Network(),
                                        settings=config.popularity_community,
                                        rqc_settings=config.remote_query_community,
                                        metadata_store=metadata_store_component.mds,
                                        torrent_checker=torrent_checker_component.torrent_checker)
        self.community = community

        self._ipv8_component.initialise_community_by_default(community, default_random_walk_max_peers=30)
        self._ipv8_component.ipv8.add_strategy(community, RemovePeers(community), INFINITE)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
