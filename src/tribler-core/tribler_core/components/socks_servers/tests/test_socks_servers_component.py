import pytest

from tribler_core.components.base import Session
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

async def test_socks_servers_component(tribler_config):
    components = [SocksServersComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = SocksServersComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.socks_ports
        assert comp.socks_servers

        await session.shutdown()
