
from ipv8.dht.provider import DHTCommunityProvider
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_common.simpledefs import NTFY

from tribler_core.components.interfaces.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.interfaces.ipv8 import (
    DHTDiscoveryCommunityComponent,
    Ipv8BootstrapperComponent,
    Ipv8Component,
    Ipv8PeerComponent,
)
from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.tunnels import TunnelsComponent
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity

INFINITE = -1


class TunnelsComponentImp(TunnelsComponent):
    async def run(self):
        config = self.session.config

        ipv8 = (await self.claim(Ipv8Component)).ipv8
        bandwidth_community = (await self.claim(BandwidthAccountingComponent)).community
        peer = (await self.claim(Ipv8PeerComponent)).peer
        dht_community = (await self.claim(DHTDiscoveryCommunityComponent)).community
        download_manager = (await self.claim(LibtorrentComponent)).download_manager
        bootstrapper = (await self.claim(Ipv8BootstrapperComponent)).bootstrapper
        rest_manager = (await self.claim(RESTComponent)).rest_manager

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        if config.general.testnet or config.tunnel_community.testnet:
            tunnel_cls = TriblerTunnelTestnetCommunity
        else:
            tunnel_cls = TriblerTunnelCommunity

        # TODO: decouple bandwidth community and dlmgr to initiate later
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               config=config.tunnel_community,
                               notifier=self.session.notifier,
                               dlmgr=download_manager,
                               bandwidth_community=bandwidth_community,
                               dht_provider=DHTCommunityProvider(dht_community, config.ipv8.port),
                               settings=settings)
        await community.wait_for_socks_servers()
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))
        ipv8.overlays.append(community)

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        # TODO: make this into a poller task instead
        self.session.notifier.add_observer(NTFY.DOWNLOADS_LIST_UPDATE, community.monitor_downloads)
        self.community = community
        # self.provide(mediator, community)

        rest_manager.get_endpoint('downloads').tunnel_community = community

    async def shutdown(self):
        self.session.notifier.remove_observer(NTFY.DOWNLOADS_LIST_UPDATE, self.community.monitor_downloads)
        await self.community.unload()
