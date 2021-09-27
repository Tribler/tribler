from unittest.mock import patch

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Session
from tribler_core.components.ipv8 import Ipv8Component
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access


async def test_bandwidth_accounting_component(tribler_config):
    components = [RESTComponent(), MasterKeyComponent(), Ipv8Component(), BandwidthAccountingComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = BandwidthAccountingComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.community
            assert comp._rest_manager
            assert comp._ipv8

            await session.shutdown()
