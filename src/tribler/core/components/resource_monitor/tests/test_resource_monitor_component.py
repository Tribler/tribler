import pytest

from tribler.core.components.session import Session
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent


# pylint: disable=protected-access
async def test_resource_monitor_component(tribler_config):
    components = [KeyComponent(), ResourceMonitorComponent()]
    async with Session(tribler_config, components).start():
        comp = ResourceMonitorComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.resource_monitor
