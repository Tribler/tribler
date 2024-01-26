from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings

from tribler.core.components.component import Component
from tribler.core.components.ipv8.ipv8_component import INFINITE, Ipv8Component
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.tunnel.community.discovery import GoldenRatioStrategy
from tribler.core.components.tunnel.community.tunnel_community import (
    TriblerTunnelCommunity,
    TriblerTunnelTestnetCommunity,
)


class TunnelsComponent(Component):
    community: TriblerTunnelCommunity = None

    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        dht_discovery_community = self._ipv8_component.dht_discovery_community

        download_component = await self.get_component(LibtorrentComponent)
        download_manager = download_component.download_manager if download_component else None

        socks_servers_component = await self.get_component(SocksServersComponent)
        socks_servers = socks_servers_component.socks_servers if socks_servers_component else None

        settings = TunnelSettings()
        config = self.session.config
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        if config.general.testnet or config.tunnel_community.testnet:
            tunnel_cls = TriblerTunnelTestnetCommunity
        else:
            tunnel_cls = TriblerTunnelCommunity

        provider = DHTCommunityProvider(dht_discovery_community, config.ipv8.port) if dht_discovery_community else None
        exitnode_cache = config.state_dir / "exitnode_cache.dat"

        self.community = tunnel_cls(self._ipv8_component.peer,
                                    self._ipv8_component.ipv8.endpoint,
                                    self._ipv8_component.ipv8.network,
                                    socks_servers=socks_servers,
                                    config=config.tunnel_community,
                                    notifier=self.session.notifier,
                                    dlmgr=download_manager,
                                    dht_provider=provider,
                                    exitnode_cache=exitnode_cache,
                                    **settings.__dict__)

        self._ipv8_component.initialise_community_by_default(self.community)
        self._ipv8_component.ipv8.add_strategy(self.community, GoldenRatioStrategy(self.community), INFINITE)

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
