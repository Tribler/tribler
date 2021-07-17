from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.messaging.anonymization.community import TunnelSettings
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8

from tribler_common.network_utils import NetworkUtils
from tribler_common.simpledefs import NTFY

from tribler_core.modules.bandwidth_accounting.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity
from tribler_core.restapi.rest_manager import RESTManager

INFINITE = -1


class TunnelsComponent(Component):
    start_async = True

    provided_futures = (BandwidthAccountingCommunity, TriblerTunnelCommunity)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tunnel_community = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config
        notifier = mediator.notifier

        if (ipv8 := await mediator.awaitable_components.get(IPv8)) is None:
            return

        bandwidth_community = await mediator.awaitable_components.get(BandwidthAccountingCommunity)
        peer = await mediator.awaitable_components.get(Peer)
        dht_community = await mediator.awaitable_components.get(DHTDiscoveryCommunity)
        download_manager = await mediator.awaitable_components.get(DownloadManager)

        settings = TunnelSettings()
        settings.min_circuits = config.tunnel_community.min_circuits
        settings.max_circuits = config.tunnel_community.max_circuits

        tunnel_cls = TriblerTunnelTestnetCommunity if config.general.testnet or config.tunnel_community.testnet else TriblerTunnelCommunity
        # TODO: decouple bandwidth community and dlmgr to initiate later
        community = tunnel_cls(peer, ipv8.endpoint, ipv8.network,
                               config=config.tunnel_community,
                               notifier=notifier,
                               dlmgr=download_manager,
                               bandwidth_community=bandwidth_community,
                               dht_community=dht_community,
                               ipv8_port=config.ipv8.port,
                               settings=settings)
        await community.wait_for_socks_servers()
        ipv8.strategies.append((RandomWalk(community), 30))
        ipv8.strategies.append((RemovePeers(community), INFINITE))

        bootstrapper = await mediator.awaitable_components.get(Bootstrapper)
        if bootstrapper:
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)

        mediator.awaitable_components[TriblerTunnelCommunity].set_result(community)
        mediator.notifier.add_observer(NTFY.DOWNLOADS_LIST_UPDATE, community.monitor_downloads)

        if api_manager := await mediator.awaitable_components.get(RESTManager):
            api_manager.get_endpoint('downloads').tunnel_community = community

