from tribler_common.simpledefs import STATE_START_WATCH_FOLDER
from tribler_core.components.base import Component
from tribler_core.components.libtorrent import LibtorrentComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.modules.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(Component):
    watch_folder: WatchFolder

    async def run(self):
        await self.get_component(ReporterComponent)
        config = self.session.config
        notifier = self.session.notifier
        libtorrent_component = await self.require_component(LibtorrentComponent)

        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=libtorrent_component.download_manager,
                                   notifier=notifier)

        rest_component = await self.require_component(RESTComponent)
        rest_component.rest_manager.get_endpoint('state').readable_status = STATE_START_WATCH_FOLDER

        watch_folder.start()
        self.watch_folder = watch_folder

    async def shutdown(self):
        self.session.notifier.notify_shutdown_state("Shutting down Watch Folder...")
        await self.watch_folder.stop()
