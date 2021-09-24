from tribler_core.components.base import Component
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.upgrade import UpgradeComponent
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager

    async def run(self):
        await self.get_component(ReporterComponent)
        await self.get_component(UpgradeComponent)

        notifier = self.session.notifier

        self.version_check_manager = VersionCheckManager(notifier=notifier)
        self.version_check_manager.start()

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Version Checker...")
        await self.version_check_manager.stop()
