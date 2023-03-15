# pylint: disable=protected-access

from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.payout.payout_component import PayoutComponent
from tribler.core.components.session import Session


async def test_payout_component(tribler_config):
    components = [BandwidthAccountingComponent(), KeyComponent(), Ipv8Component(), PayoutComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(PayoutComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.payout_manager
