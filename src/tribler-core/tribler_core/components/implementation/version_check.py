from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.components.interfaces.version_check import VersionCheckComponent
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponentImp(VersionCheckComponent):
    async def run(self):
        await self.claim(UpgradeComponent)

        notifier = self.session.notifier

        self.version_check_manager = VersionCheckManager(notifier=notifier)
        self.version_check_manager.start()
        # self.provide(mediator, version_check_manager)

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Version Checker...")
        await self.version_check_manager.stop()
