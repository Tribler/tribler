from tribler_common.simpledefs import NTFY

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Component
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.payout.payout_manager import PayoutManager

INFINITE = -1


class PayoutComponent(Component):
    payout_manager: PayoutManager = None

    async def run(self):
        await super().run()

        config = self.session.config
        assert not config.gui_test_mode

        await self.get_component(ReporterComponent)

        ipv8_component = await self.require_component(Ipv8Component)
        bandwidth_accounting_component = await self.require_component(BandwidthAccountingComponent)

        self.payout_manager = PayoutManager(bandwidth_accounting_component.community,
                                            ipv8_component.dht_discovery_community)

        self.session.notifier.add_observer(NTFY.PEER_DISCONNECTED_EVENT, self.payout_manager.do_payout)
        self.session.notifier.add_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, self.payout_manager.update_peer)


    async def shutdown(self):
        await super().shutdown()
        if self.payout_manager:
            self.session.notifier.remove_observer(NTFY.PEER_DISCONNECTED_EVENT, self.payout_manager.do_payout)
            self.session.notifier.remove_observer(NTFY.TRIBLER_TORRENT_PEER_UPDATE, self.payout_manager.update_peer)

            await self.payout_manager.shutdown()
