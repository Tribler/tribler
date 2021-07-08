from tribler_core.modules.component import Component
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager
from tribler_core.session import Mediator


class VersionCheckComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version_check_manager = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        notifier = mediator.notifier

        self.version_check_manager = VersionCheckManager(notifier=notifier)
        self.version_check_manager.start()

    async def shutdown(self, mediator):
        await super().shutdown(mediator)

        mediator.notifier.notify_shutdown_state("Shutting down Version Checker...")
        await self.version_check_manager.stop()
