from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.network import Network
from tribler.core.components.component import Component
from tribler.core.components.content_discovery.community.content_discovery_community import ContentDiscoveryCommunity
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.ipv8.ipv8_component import INFINITE, Ipv8Component
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent


class ContentDiscoveryComponent(Component):
    community: ContentDiscoveryCommunity = None

    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

        self._ipv8_component = await self.require_component(Ipv8Component)
        database_component = await self.require_component(DatabaseComponent)
        torrent_checker_component = await self.require_component(TorrentCheckerComponent)

        self.community = ContentDiscoveryCommunity(ContentDiscoveryCommunity.settings_class(
            my_peer = self._ipv8_component.peer,
            endpoint = self._ipv8_component.ipv8.endpoint,
            network = Network(),
            maximum_payload_size = self.session.config.content_discovery_community.maximum_payload_size,
            metadata_store=database_component.mds,
            torrent_checker=torrent_checker_component.torrent_checker,
            notifier=self.session.notifier
        ))

        self._ipv8_component.initialise_community_by_default(self.community, default_random_walk_max_peers=30)
        self._ipv8_component.ipv8.add_strategy(self.community, RandomChurn(self.community), INFINITE)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
