from tribler.core.components.component import Component
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager = None

    async def run(self):
        await super().run()
        await self.get_component(ReporterComponent)

        notifier = self.session.notifier

        self.version_check_manager = VersionCheckManager(notifier=notifier)
        self.version_check_manager.start()

    async def shutdown(self):
        await super().shutdown()
        if self.version_check_manager:
            await self.version_check_manager.stop()
