from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.session import Session


# pylint: disable=protected-access


async def test_bandwidth_accounting_component(tribler_config):
    components = [KeyComponent(), Ipv8Component(), BandwidthAccountingComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(BandwidthAccountingComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component
