import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent


# pylint: disable=protected-access
@pytest.mark.asyncio
async def test_resource_monitor_component(tribler_config):
    components = [KeyComponent(), ResourceMonitorComponent()]
    async with Session(tribler_config, components).start():
        comp = ResourceMonitorComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.resource_monitor
