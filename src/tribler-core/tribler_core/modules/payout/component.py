from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.dht.routing import RoutingTable
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address
from tribler_common.simpledefs import NTFY
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity

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

        dht_community = await mediator.awaitable_components.get(DHTDiscoveryCommunity)
        bandwidth_community = await mediator.awaitable_components.get(BandwidthAccountingCommunity)

        if not dht_community or not bandwidth_community:
            return

        payout_manager = PayoutManager(bandwidth_community, dht_community)
        mediator.notifier.add_observer(NTFY.PEER_DISCONNECTED_EVENT, payout_manager.do_payout)
        mediator.notifier.add_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, payout_manager.update_peer)

        if config.core_test_mode:
            dht_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        self.payout_manager = payout_manager

    async def shutdown(self, mediator):
        if self.payout_manager:
            await self.payout_manager.shutdown()
        await super().shutdown(mediator)

