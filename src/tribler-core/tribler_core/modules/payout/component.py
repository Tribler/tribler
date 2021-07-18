from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.dht.routing import RoutingTable
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address
from tribler_common.simpledefs import NTFY
from tribler_core.awaitable_resources import PAYOUT_MANAGER, DHT_DISCOVERY_COMMUNITY, BANDWIDTH_ACCOUNTING_COMMUNITY
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity

from tribler_core.modules.component import Component
from tribler_core.modules.payout.payout_manager import PayoutManager

INFINITE = -1


class PayoutComponent(Component):
    role = PAYOUT_MANAGER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        dht_community = await self.use(mediator, DHT_DISCOVERY_COMMUNITY)
        bandwidth_community = await self.use(mediator, BANDWIDTH_ACCOUNTING_COMMUNITY)

        payout_manager = PayoutManager(bandwidth_community, dht_community)
        mediator.notifier.add_observer(NTFY.PEER_DISCONNECTED_EVENT, payout_manager.do_payout)
        mediator.notifier.add_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, payout_manager.update_peer)

        if config.core_test_mode:
            dht_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        self.provide(mediator, payout_manager)

    async def shutdown(self, mediator):
        mediator.notifier.remove_observer(NTFY.PEER_DISCONNECTED_EVENT, self._provided_object.do_payout)
        mediator.notifier.remove_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, self._provided_object.update_peer)

        await self._provided_object.shutdown()
        await super().shutdown(mediator)

