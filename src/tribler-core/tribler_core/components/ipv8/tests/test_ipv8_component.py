import pytest

from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access
async def test_ipv8_component(tribler_config):
    session = Session(tribler_config, [KeyComponent(), RESTComponent(), Ipv8Component()])
    with session:
        await session.start()

        comp = Ipv8Component.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.ipv8
        assert comp.peer
        assert not comp.dht_discovery_community
        assert comp._task_manager
        assert not comp._peer_discovery_community

        await session.shutdown()


async def test_ipv8_component_dht_disabled(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.dht.enabled = True
    session = Session(tribler_config, [KeyComponent(), RESTComponent(), Ipv8Component()])
    with session:
        await session.start()

        comp = Ipv8Component.instance()
        assert comp.dht_discovery_community


async def test_ipv8_component_discovery_community_enabled(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.gui_test_mode = False
    tribler_config.discovery_community.enabled = True
    session = Session(tribler_config, [KeyComponent(), RESTComponent(), Ipv8Component()])
    with session:
        await session.start()

        comp = Ipv8Component.instance()
        assert comp._peer_discovery_community
