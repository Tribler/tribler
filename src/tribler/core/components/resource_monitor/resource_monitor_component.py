from tribler.core.components.component import Component
from tribler.core.components.resource_monitor.implementation.core import CoreResourceMonitor


class ResourceMonitorComponent(Component):
    resource_monitor: CoreResourceMonitor = None

    async def run(self):
        await super().run()

        config = self.session.config
        notifier = self.session.notifier

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()
        self.resource_monitor = resource_monitor

    async def shutdown(self):
        await super().shutdown()
        if self.resource_monitor:
            await self.resource_monitor.stop()
