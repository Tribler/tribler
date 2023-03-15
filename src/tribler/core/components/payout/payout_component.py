from tribler.core import notifications
from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.component import Component
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.payout.payout_manager import PayoutManager
from tribler.core.components.reporter.reporter_component import ReporterComponent

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

        self.session.notifier.add_observer(notifications.peer_disconnected, self.payout_manager.on_peer_disconnected)
        self.session.notifier.add_observer(notifications.tribler_torrent_peer_update, self.payout_manager.update_peer)

    async def shutdown(self):
        await super().shutdown()
        if self.payout_manager:
            notifier = self.session.notifier
            notifier.remove_observer(notifications.peer_disconnected, self.payout_manager.on_peer_disconnected)
            notifier.remove_observer(notifications.tribler_torrent_peer_update, self.payout_manager.update_peer)

            await self.payout_manager.shutdown()
