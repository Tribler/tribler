from ipv8.bootstrapping.bootstrapper_interface import Bootstrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8

from tribler_core.modules.bandwidth_accounting.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.modules.component import Component
from tribler_core.restapi.rest_manager import RESTManager


class BandwidthAccountingComponent(Component):
    start_async = True
    provided_futures = (BandwidthAccountingCommunity,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bandwidth_community = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        if (ipv8 := await mediator.awaitable_components.get(IPv8)) is None:
            return
        peer = await mediator.awaitable_components.get(Peer)

        bandwidth_cls = BandwidthAccountingTestnetCommunity if config.general.testnet or config.bandwidth_accounting.testnet else BandwidthAccountingCommunity

        community = bandwidth_cls(peer, ipv8.endpoint, ipv8.network,
                                  settings=config.bandwidth_accounting,
                                  database=config.state_dir / "sqlite" / "bandwidth.db")
        ipv8.strategies.append((RandomWalk(community), 20))

        if bootstrapper := await mediator.awaitable_components.get(Bootstrapper):
            community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        mediator.awaitable_components[BandwidthAccountingCommunity].set_result(community)

        if api_manager := await mediator.awaitable_components.get(RESTManager):
            api_manager.get_endpoint('trustview').bandwidth_db = community.database
            api_manager.get_endpoint('bandwidth').bandwidth_community = community
