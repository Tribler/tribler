# pylint: disable=protected-access
import pytest

from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.base import Session
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.payout.payout_component import PayoutComponent


@pytest.mark.no_parallel
async def test_payout_component(tribler_config):
    components = [BandwidthAccountingComponent(), KeyComponent(), Ipv8Component(), PayoutComponent()]
    async with Session(tribler_config, components).start():
        comp = PayoutComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.payout_manager
