from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler.core.components.session import Session


# pylint: disable=protected-access
async def test_resource_monitor_component(tribler_config):
    components = [KeyComponent(), ResourceMonitorComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(ResourceMonitorComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.resource_monitor
