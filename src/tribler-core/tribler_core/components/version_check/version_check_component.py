from tribler_core.components.base import Component
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.upgrade.upgrade_component import UpgradeComponent
from tribler_core.components.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager = None

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)
        await self.get_component(UpgradeComponent)

        notifier = self.session.notifier

        self.version_check_manager = VersionCheckManager(notifier=notifier)
        self.version_check_manager.start()

    async def shutdown(self):
        await super().shutdown()
        if self.version_check_manager:
            await self.version_check_manager.stop()
