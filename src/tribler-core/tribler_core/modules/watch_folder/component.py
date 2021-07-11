from tribler_common.simpledefs import STATE_START_WATCH_FOLDER
from tribler_core.modules.component import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.watch_folder.watch_folder import WatchFolder
from tribler_core.session import Mediator


class WatchFolderComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watch_folder = None

    async def run(self, mediator: Mediator):
        await super().run(mediator)

        config = mediator.config
        notifier = mediator.notifier

        download_manager = await mediator.awaitable_components.get(DownloadManager)

        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=download_manager,
                                   notifier=notifier)

        if api_manager := mediator.optional.get('api_manager'):
            api_manager.get_endpoint('state').readable_status = STATE_START_WATCH_FOLDER
        watch_folder.start()
        self.watch_folder = watch_folder

    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down Watch Folder...")
        await self.watch_folder.stop()
        await super().shutdown(mediator)
