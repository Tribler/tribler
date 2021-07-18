from tribler_core.awaitable_resources import RESOURCE_MONITOR
from tribler_core.modules.component import Component
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor
from tribler_core.session import Mediator


class ResourceMonitorComponent(Component):
    role = RESOURCE_MONITOR

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()
        self.provide(mediator, resource_monitor)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await self._provided_object.stop()

        await super().shutdown(mediator)
