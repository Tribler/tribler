from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.ipv8.ipv8_component import INFINITE, Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.restapi.restapi_component import RestfulComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tunnel.community.tunnel_community import TriblerTunnelCommunity, \
    TriblerTunnelTestnetCommunity
from tribler_core.components.tunnel.community.discovery import GoldenRatioStrategy


class TunnelsComponent(RestfulComponent):
    community: TriblerTunnelCommunity = None

    _ipv8_component: Ipv8Component = None

    async def run(self):
        await super().run()

        self._ipv8_component = await self.require_component(Ipv8Component)
        dht_discovery_community = self._ipv8_component.dht_discovery_community

        bandwidth_component = await self.get_component(BandwidthAccountingComponent)
        bandwidth_community = bandwidth_component.community if bandwidth_component else None

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

        # TODO: decouple bandwidth community and dlmgr to initiate later
        self.community = tunnel_cls(self._ipv8_component.peer,
                                    self._ipv8_component.ipv8.endpoint,
                                    self._ipv8_component.ipv8.network,
                                    socks_servers=socks_servers,
                                    config=config.tunnel_community,
                                    notifier=self.session.notifier,
                                    dlmgr=download_manager,
                                    bandwidth_community=bandwidth_community,
                                    dht_provider=provider,
                                    exitnode_cache=exitnode_cache,
                                    settings=settings)

        self._ipv8_component.initialise_community_by_default(self.community)
        self._ipv8_component.ipv8.add_strategy(self.community, GoldenRatioStrategy(self.community), INFINITE)

        await self.init_endpoints(endpoints=['downloads', 'debug'], values={'tunnel_community': self.community})
        await self.init_ipv8_endpoints(self._ipv8_component.ipv8, endpoints=['tunnel'])

    async def shutdown(self):
        await super().shutdown()
        if self._ipv8_component and self.community:
            await self._ipv8_component.unload_community(self.community)
