from unittest.mock import patch

import pytest

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Session
from tribler_core.components.ipv8 import Ipv8Component
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RESTComponent


# pylint: disable=protected-access

@pytest.mark.asyncio
async def test_bandwidth_accounting_component(tribler_config):
    tribler_config.ipv8.enabled = True
    components = [RESTComponent(), MasterKeyComponent(), Ipv8Component(), BandwidthAccountingComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = BandwidthAccountingComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component

        await session.shutdown()
