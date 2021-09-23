from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.components.implementation.upgrade import UpgradeComponent
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor


class ResourceMonitorComponent(Component):
    resource_monitor: CoreResourceMonitor


class ResourceMonitorComponentImp(ResourceMonitorComponent):
    async def run(self):
        await self.use(ReporterComponent, required=False)
        await self.use(UpgradeComponent, required=False)

        config = self.session.config
        notifier = self.session.notifier

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()
        self.resource_monitor = resource_monitor

        rest_manager = (await self.use(RESTComponent)).rest_manager
        rest_manager.get_endpoint('debug').resource_monitor = resource_monitor

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await self.resource_monitor.stop()


@testcomponent
class ResourceMonitorComponentMock(ResourceMonitorComponent):
    resource_monitor = Mock()
