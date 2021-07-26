from tribler_common.simpledefs import STATE_START_WATCH_FOLDER

from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.watch_folder import WatchFolderComponent
from tribler_core.modules.watch_folder.watch_folder import WatchFolder


class WatchFolderComponentImp(WatchFolderComponent):
    async def run(self):
        config = self.session.config
        notifier = self.session.notifier
        download_manager = (await self.use(LibtorrentComponent)).download_manager
        rest_manager = (await self.use(RESTComponent)).rest_manager

        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=download_manager,
                                   notifier=notifier)

        rest_manager.get_endpoint('state').readable_status = STATE_START_WATCH_FOLDER

        watch_folder.start()
        self.watch_folder = watch_folder

        # self.provide(mediator, watch_folder)

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Watch Folder...")
        await self.watch_folder.stop()
