import pytest

from tribler_core.components.resource_monitor.settings import ResourceMonitorSettings


@pytest.mark.asyncio
async def test_cpu_priority():
    assert ResourceMonitorSettings(cpu_priority=3)

    with pytest.raises(ValueError):
        ResourceMonitorSettings(cpu_priority=-1)

    with pytest.raises(ValueError):
        ResourceMonitorSettings(cpu_priority=6)


@pytest.mark.asyncio
async def test_poll_interval():
    assert ResourceMonitorSettings(poll_interval=1)
    assert ResourceMonitorSettings(poll_interval=2)

    with pytest.raises(ValueError):
        ResourceMonitorSettings(poll_interval=0)
