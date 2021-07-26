from ipv8.dht.routing import RoutingTable
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address

from tribler_common.simpledefs import NTFY

from tribler_core.components.interfaces.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.interfaces.ipv8 import DHTDiscoveryCommunityComponent
from tribler_core.components.interfaces.payout import PayoutComponent
from tribler_core.modules.payout.payout_manager import PayoutManager

INFINITE = -1


class PayoutComponentImp(PayoutComponent):
    async def run(self):
        config = self.session.config

        dht_community = (await self.use(DHTDiscoveryCommunityComponent)).community
        bandwidth_community = (await self.use(BandwidthAccountingComponent)).community

        payout_manager = PayoutManager(bandwidth_community, dht_community)
        self.session.notifier.add_observer(NTFY.PEER_DISCONNECTED_EVENT, payout_manager.do_payout)
        self.session.notifier.add_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, payout_manager.update_peer)

        if config.core_test_mode:
            dht_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        self.payout_manager = payout_manager
        # self.provide(mediator, payout_manager)

    async def shutdown(self):
        self.session.notifier.remove_observer(NTFY.PEER_DISCONNECTED_EVENT, self.payout_manager.do_payout)
        self.session.notifier.remove_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, self.payout_manager.update_peer)

        await self.payout_manager.shutdown()
