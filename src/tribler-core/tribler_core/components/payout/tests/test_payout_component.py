# pylint: disable=protected-access
import pytest

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.payout.payout_component import PayoutComponent
from tribler_core.components.restapi.restapi_component import RESTComponent


@pytest.mark.asyncio
async def test_payout_component(tribler_config):
    components = [BandwidthAccountingComponent(), KeyComponent(), RESTComponent(), Ipv8Component(),
                  PayoutComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = PayoutComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.payout_manager

        await session.shutdown()
