from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8
from tribler_core.components.base import Component
from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.implementation.ipv8 import Ipv8Component
from tribler_core.components.implementation.libtorrent import LibtorrentComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.components.implementation.socks_configurator import SocksServersComponent
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity
from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy

INFINITE = -1


class TunnelsComponent(Component):
    community: TriblerTunnelCommunity
    _ipv8: IPv8


class TunnelsComponentImp(TunnelsComponent):
    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        ipv8_component = await self.use(Ipv8Component)
        ipv8 = self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        dht_discovery_community = ipv8_component.dht_discovery_community

        bandwidth_component = await self.use(BandwidthAccountingComponent, required=False)
        bandwidth_community = bandwidth_component.community if bandwidth_component.enabled else None

        download_component = await self.use(LibtorrentComponent, required=False)
        download_manager = download_component.download_manager if download_component.enabled else None

        rest_component = await self.use(RESTComponent, required=False)
        rest_manager = rest_component.rest_manager if rest_component.enabled else None

        socks_servers_component = await self.use(SocksServersComponent, required=False)
        socks_servers = socks_servers_component.socks_servers if socks_servers_component.enabled else None

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        if config.general.testnet or config.tunnel_community.testnet:
            tunnel_cls = TriblerTunnelTestnetCommunity
        else:
            tunnel_cls = TriblerTunnelCommunity

        provider = DHTCommunityProvider(dht_discovery_community, config.ipv8.port) if dht_discovery_community else None
        exitnode_cache = config.state_dir / "exitnode_cache.dat"

        # TODO: decouple bandwidth community and dlmgr to initiate later
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               socks_servers=socks_servers,
                               config=config.tunnel_community,
                               notifier=self.session.notifier,
                               dlmgr=download_manager,
                               bandwidth_community=bandwidth_community,
                               dht_provider=provider,
                               exitnode_cache=exitnode_cache,
                               settings=settings)

        # Value of `target_peers` must not be equal to the value of `max_peers` for this community.
        # This causes a deformed network topology and makes it harder for peers to connect to others.
        # More information: https://github.com/Tribler/py-ipv8/issues/979#issuecomment-896643760
        ipv8.add_strategy(community, RandomWalk(community), 20)
        ipv8.add_strategy(community, GoldenRatioStrategy(community), INFINITE)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        self.community = community

        if rest_component.enabled:
            rest_manager.get_endpoint('ipv8').endpoints['/tunnel'].initialize(ipv8)
            if download_component.enabled:
                rest_manager.get_endpoint('downloads').tunnel_community = community

            debug_endpoint = rest_manager.get_endpoint('debug')
            debug_endpoint.tunnel_community = community

    async def shutdown(self):
        await self._ipv8.unload_overlay(self.community)
