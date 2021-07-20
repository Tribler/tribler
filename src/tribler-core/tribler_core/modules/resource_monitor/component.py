from tribler_core.awaitable_resources import RESOURCE_MONITOR, REST_MANAGER, TUNNELS_COMMUNITY, UPGRADER
from tribler_core.modules.component import Component
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor
from tribler_core.session import Mediator


class ResourceMonitorComponent(Component):
    role = RESOURCE_MONITOR

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        await mediator.optional[UPGRADER]._resource_initialized_event.wait()

        config = mediator.config
        notifier = mediator.notifier

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()
        self.provide(mediator, resource_monitor)
        rest_manager = await self.use(mediator, REST_MANAGER)
        # TODO: Split debug endpoint initialization
        debug_endpoint = rest_manager.get_endpoint('debug')
        debug_endpoint.resource_monitor = resource_monitor
        debug_endpoint.tunnel_community = await self.use(mediator, TUNNELS_COMMUNITY)
        debug_endpoint.log_dir = log_dir
        debug_endpoint.state_dir = config.state_dir

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await self._provided_object.stop()

        await super().shutdown(mediator)
