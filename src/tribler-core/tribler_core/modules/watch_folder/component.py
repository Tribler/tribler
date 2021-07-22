from tribler_common.simpledefs import STATE_START_WATCH_FOLDER
from tribler_core.awaitable_resources import WATCH_FOLDER, REST_MANAGER, DOWNLOAD_MANAGER
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.watch_folder.watch_folder import WatchFolder
from tribler_core.session import Mediator


class WatchFolderComponent(Component):
    role = WATCH_FOLDER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier
        download_manager = await self.use(mediator, DOWNLOAD_MANAGER)
        rest_manager = await self.use(mediator, REST_MANAGER)

        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=download_manager,
                                   notifier=notifier)

        rest_manager.get_endpoint('state').readable_status = STATE_START_WATCH_FOLDER

        watch_folder.start()
        self.provide(mediator, watch_folder)

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Watch Folder...")
        await self._provided_object.stop()

        await super().shutdown(mediator)
