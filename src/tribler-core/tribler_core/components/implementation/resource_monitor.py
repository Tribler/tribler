from tribler_core.components.interfaces.resource_monitor import ResourceMonitorComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.tunnels import TunnelsComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.modules.resource_monitor.core import CoreResourceMonitor


class ResourceMonitorComponentImp(ResourceMonitorComponent):
    async def run(self):
        await self.claim(UpgradeComponent)
        tunnel_community = (await self.claim(TunnelsComponent)).community

        config = self.session.config
        notifier = self.session.notifier

        log_dir = config.general.get_path_as_absolute('log_dir', config.state_dir)
        resource_monitor = CoreResourceMonitor(state_dir=config.state_dir,
                                               log_dir=log_dir,
                                               config=config.resource_monitor,
                                               notifier=notifier)
        resource_monitor.start()
        self.resource_monitor = resource_monitor
        # self.provide(mediator, resource_monitor)

        rest_manager = (await self.claim(RESTComponent)).rest_manager

        # TODO: Split debug endpoint initialization
        debug_endpoint = rest_manager.get_endpoint('debug')
        debug_endpoint.resource_monitor = resource_monitor
        debug_endpoint.tunnel_community = tunnel_community
        debug_endpoint.log_dir = log_dir
        debug_endpoint.state_dir = config.state_dir

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Resource Monitor...")
        await self.resource_monitor.stop()
