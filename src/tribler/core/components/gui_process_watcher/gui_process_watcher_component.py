from tribler.core.components.component import Component
from tribler.core.components.gui_process_watcher.gui_process_watcher import GuiProcessWatcher


class GuiProcessWatcherComponent(Component):
    watcher: GuiProcessWatcher = None

    async def run(self):
        await super().run()

        gui_process = GuiProcessWatcher.get_gui_process()
        if not gui_process:
            self.logger.warning('Cannot found GUI process to watch')
            return

        self.watcher = GuiProcessWatcher(gui_process, self.session.shutdown_event.set)
        self.logger.info(f'Watching GUI process with pid {self.watcher.gui_process.pid}')
        self.watcher.start()

    async def shutdown(self):
        await super().shutdown()
        if self.watcher:
            await self.watcher.stop()
