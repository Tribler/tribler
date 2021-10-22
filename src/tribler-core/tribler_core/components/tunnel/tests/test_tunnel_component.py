import pytest

from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access
async def test_tunnels_component(tribler_config):
    components = [Ipv8Component(), KeyComponent(), RESTComponent(), TunnelsComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = TunnelsComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component

        await session.shutdown()
