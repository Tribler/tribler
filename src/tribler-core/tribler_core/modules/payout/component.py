from ipv8.dht.routing import RoutingTable
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address

from tribler_core.modules.component import Component
from tribler_core.modules.payout.payout_manager import PayoutManager

INFINITE = -1


class PayoutComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.payout_manager = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        bandwidth_community = mediator.optional.get('bandwidth_community', None)
        dht_community = mediator.optional.get('dht_community', None)
        download_manager = mediator.optional.get('download_manager', None)

        if not dht_community or not bandwidth_community:
            return

        payout_manager = PayoutManager(bandwidth_community, dht_community)
        if download_manager:
            download_manager.payout_manager = payout_manager

        if config.core_test_mode:
            dht_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        self.payout_manager = payout_manager

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        await self.payout_manager.shutdown()

