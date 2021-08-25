from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.components.interfaces.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.interfaces.ipv8 import Ipv8Component
from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.socks_configurator import SocksServersComponent
from tribler_core.components.interfaces.tunnels import TunnelsComponent
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity

INFINITE = -1


class TunnelsComponentImp(TunnelsComponent):
    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config
        ipv8_component = await self.use(Ipv8Component)
        ipv8 = ipv8_component.ipv8
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

        # TODO: decouple bandwidth community and dlmgr to initiate later
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               socks_servers=socks_servers,
                               config=config.tunnel_community,
                               notifier=self.session.notifier,
                               dlmgr=download_manager,
                               bandwidth_community=bandwidth_community,
                               dht_provider=DHTCommunityProvider(dht_discovery_community, config.ipv8.port),
                               settings=settings)
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))
        ipv8.overlays.append(community)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

        self.community = community

        if rest_component.enabled:
            rest_manager.get_endpoint('ipv8').endpoints['/tunnel'].initialize(ipv8)
            if download_component.enabled:
                rest_manager.get_endpoint('downloads').tunnel_community = community

    async def shutdown(self):
        await self.community.unload()
