from tribler_core.awaitable_resources import VERSION_CHECKER, UPGRADER
from tribler_core.modules.component import Component
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager
from tribler_core.session import Mediator


class VersionCheckComponent(Component):
    role = VERSION_CHECKER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator: Mediator):
        await super().run(mediator)
        await mediator.optional[UPGRADER]._resource_initialized_event.wait()

        notifier = mediator.notifier

        version_check_manager = VersionCheckManager(notifier=notifier)
        version_check_manager.start()
        self.provide(mediator, version_check_manager)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Version Checker...")
        await self._provided_object.stop()

        await super().shutdown(mediator)
