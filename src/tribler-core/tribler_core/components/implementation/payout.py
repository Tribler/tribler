from tribler_common.simpledefs import NTFY
from tribler_core.components.base import Component, ComponentError
from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.implementation.ipv8 import Ipv8Component
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.modules.payout.payout_manager import PayoutManager

INFINITE = -1


class PayoutComponent(Component):
    payout_manager: PayoutManager

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config

        ipv8_component = await self.use(Ipv8Component)
        if not ipv8_component:
            raise ComponentError(f'Missed dependency: {self.__class__.__name__} requires Ipv8Component to be active')

        bandwidth_accounting_component = await self.use(BandwidthAccountingComponent)
        if not bandwidth_accounting_component:
            raise ComponentError(
                f'Missed dependency: {self.__class__.__name__} requires BandwidthAccountingComponent to be active')

        payout_manager = PayoutManager(bandwidth_accounting_component.community, ipv8_component.dht_discovery_community)
        self.session.notifier.add_observer(NTFY.PEER_DISCONNECTED_EVENT, payout_manager.do_payout)
        self.session.notifier.add_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, payout_manager.update_peer)

        assert not config.gui_test_mode

        self.payout_manager = payout_manager

    async def shutdown(self):
        self.session.notifier.remove_observer(NTFY.PEER_DISCONNECTED_EVENT, self.payout_manager.do_payout)
        self.session.notifier.remove_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, self.payout_manager.update_peer)

        await self.payout_manager.shutdown()
