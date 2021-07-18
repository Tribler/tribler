from asyncio import gather

from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_common.simpledefs import NTFY
from tribler_core.awaitable_resources import IPV8_SERVICE, TUNNELS_COMMUNITY, \
    BANDWIDTH_ACCOUNTING_COMMUNITY, DHT_DISCOVERY_COMMUNITY, DOWNLOAD_MANAGER, MY_PEER, IPV8_BOOTSTRAPPER, REST_MANAGER

from tribler_core.modules.component import Component
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity

INFINITE = -1


class TunnelsComponent(Component):
    role = TUNNELS_COMMUNITY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        bandwidth_community = await self.use(mediator, BANDWIDTH_ACCOUNTING_COMMUNITY)
        peer = await self.use(mediator, MY_PEER)
        dht_community = await self.use(mediator, DHT_DISCOVERY_COMMUNITY)
        download_manager = await self.use(mediator, DOWNLOAD_MANAGER)

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        tunnel_cls = TriblerTunnelTestnetCommunity if config.general.testnet or config.tunnel_community.testnet else TriblerTunnelCommunity
        # TODO: decouple bandwidth community and dlmgr to initiate later
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               config=config.tunnel_community,
                               notifier=mediator.notifier,
                               dlmgr=download_manager,
                               bandwidth_community=bandwidth_community,
                               dht_community=dht_community,
                               ipv8_port=config.ipv8.port,
                               settings=settings)
        await community.wait_for_socks_servers()
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))
        ipv8.overlays.append(community)

        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)
        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        mediator.notifier.add_observer(NTFY.DOWNLOADS_LIST_UPDATE, community.monitor_downloads)
        self.provide(mediator, community)

        api_manager = await self.use(mediator, REST_MANAGER)
        api_manager.get_endpoint('downloads').tunnel_community = community

    async def shutdown(self, mediator):
        mediator.notifier.remove_observer(NTFY.DOWNLOADS_LIST_UPDATE, self._provided_object.monitor_downloads)
        await self._provided_object.unload()
        await super(self).shutdown(mediator)

