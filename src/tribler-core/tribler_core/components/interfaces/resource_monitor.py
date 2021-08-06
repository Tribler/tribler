from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor


class ResourceMonitorComponent(Component):
    resource_monitor: CoreResourceMonitor

    @classmethod
    def should_be_enabled(cls, config):
        return config.resource_monitor.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.resource_monitor import ResourceMonitorComponentImp
            return ResourceMonitorComponentImp()
        return ResourceMonitorComponentMock()


@testcomponent
class ResourceMonitorComponentMock(ResourceMonitorComponent):
    resource_monitor = Mock()
