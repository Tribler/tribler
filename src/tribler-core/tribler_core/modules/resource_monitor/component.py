from tribler_core.modules.component import Component
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor
from tribler_core.session import Mediator


class ResourceMonitorComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resource_monitor = None

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
        self.resource_monitor = resource_monitor

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await self.resource_monitor.stop()
        await super().shutdown(mediator)
