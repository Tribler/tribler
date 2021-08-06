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
        await self.use(ReporterComponent)

        config = self.session.config
        ipv8_component = await self.use(Ipv8Component)
        ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        dht_discovery_community = ipv8_component.dht_discovery_community

        bandwidth_community = (await self.use(BandwidthAccountingComponent)).community
        download_manager = (await self.use(LibtorrentComponent)).download_manager
        rest_manager = (await self.use(RESTComponent)).rest_manager
        socks_servers = (await self.use(SocksServersComponent)).socks_servers

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

        if ipv8_component.bootstrapper:
            community.bootstrappers.append(ipv8_component.bootstrapper)

        self.community = community
        # self.provide(mediator, community)

        rest_manager.get_endpoint('downloads').tunnel_community = community
        rest_manager.get_endpoint('ipv8').endpoints['/tunnel'].initialize(ipv8)

    async def shutdown(self):
        await self.community.unload()
