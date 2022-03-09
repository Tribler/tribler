import pytest

from tribler.core.components.base import Session
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.tunnel.tunnel_component import TunnelsComponent


# pylint: disable=protected-access

@pytest.mark.asyncio
@pytest.mark.no_parallel
async def test_tunnels_component(tribler_config):
    components = [Ipv8Component(), KeyComponent(), TunnelsComponent()]
    async with Session(tribler_config, components).start():
        comp = TunnelsComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component
