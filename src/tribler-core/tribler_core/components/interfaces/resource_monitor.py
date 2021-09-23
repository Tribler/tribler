from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor


class ResourceMonitorComponent(Component):
    enable_in_gui_test_mode = True
    resource_monitor: CoreResourceMonitor


@testcomponent
class ResourceMonitorComponentMock(ResourceMonitorComponent):
    resource_monitor = Mock()
