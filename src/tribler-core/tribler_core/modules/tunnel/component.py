from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_common.network_utils import NetworkUtils

from tribler_core.modules.bandwidth_accounting.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity

INFINITE = -1


class TunnelsComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bandwidth_community = None
        self.tunnel_community = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config
        notifier = mediator.notifier

        ipv8 = await mediator.optional['ipv8']
        api_manager = mediator.optional.get('api_manager', None)

        if not ipv8:
            return

        await self.set_anon_proxy_settings(config)
        bandwidth_community = await self.create_bandwidth_community(config, notifier, ipv8, mediator)
        tunnel_community = await self.create_tunnel_community(config, notifier, ipv8, mediator, bandwidth_community)

        if api_manager:
            api_manager.get_endpoint('trustview').bandwidth_db = bandwidth_community.database
            api_manager.get_endpoint('downloads').tunnel_community = tunnel_community

        if api_manager and tunnel_community:
            api_manager.get_endpoint('ipv8').initialize(ipv8)
            await tunnel_community.wait_for_socks_servers()

        mediator.optional['bandwidth_community'] = bandwidth_community
        mediator.optional['tunnel_community'] = tunnel_community

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        ipv8 = mediator.optional.get('ipv8', None)
        if not ipv8:
            return

        mediator.notifier.notify_shutdown_state("Unloading Tunnel Community...")
        await ipv8.unload_overlay(self.tunnel_community)
        mediator.notifier.notify_shutdown_state("Shutting down Bandwidth Community...")
        await ipv8.unload_overlay(self.bandwidth_community)

    async def set_anon_proxy_settings(self, config):
        anon_proxy_ports = config.tunnel_community.socks5_listen_ports
        if not anon_proxy_ports:
            anon_proxy_ports = [NetworkUtils().get_random_free_port() for _ in range(5)]
            config.tunnel_community.socks5_listen_ports = anon_proxy_ports
        anon_proxy_settings = ("127.0.0.1", anon_proxy_ports)
        self.logger.info(f'Set anon proxy settings: {anon_proxy_settings}')

        DownloadManager.set_anon_proxy_settings(config.libtorrent, 2, anon_proxy_settings)

    async def create_bandwidth_community(self, config, notifier, ipv8, mediator):
        peer = mediator.optional.get('peer', None)
        bootstrapper = mediator.optional.get('bootstrapper', None)

        bandwidth_cls = BandwidthAccountingTestnetCommunity if config.general.testnet or config.bandwidth_accounting.testnet else BandwidthAccountingCommunity
        community = bandwidth_cls(peer, ipv8.endpoint, ipv8.network,
                                  settings=config.bandwidth_accounting,
                                  database=config.state_dir / "sqlite" / "bandwidth.db")

        ipv8.strategies.append((RandomWalk(community), 20))

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

        return community

    async def create_tunnel_community(self, config, notifier, ipv8, mediator, bandwidth_community):
        if not config.tunnel_community.enabled:
            return None

        peer = mediator.optional.get('peer', None)
        bootstrapper = mediator.optional.get('bootstrapper', None)
        dht_community = mediator.optional.get('dht_community', None)
        dlmgr = mediator.optional.get('download_manager', None)

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        tunnel_cls = TriblerTunnelTestnetCommunity if config.general.testnet or config.tunnel_community.testnet else TriblerTunnelCommunity
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               config=config.tunnel_community,
                               notifier=notifier,
                               dlmgr=dlmgr,
                               bandwidth_community=bandwidth_community,
                               dht_community=dht_community,
                               ipv8_port=config.ipv8.port,
                               settings=settings)
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

        return community
