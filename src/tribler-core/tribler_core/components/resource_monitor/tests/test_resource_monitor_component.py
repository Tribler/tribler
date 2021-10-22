import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler_core.components.restapi.restapi_component import RESTComponent


# pylint: disable=protected-access
@pytest.mark.asyncio
async def test_resource_monitor_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), ResourceMonitorComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = ResourceMonitorComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.resource_monitor

        await session.shutdown()
