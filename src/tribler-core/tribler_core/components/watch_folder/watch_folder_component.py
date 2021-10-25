from tribler_common.simpledefs import STATE_START_WATCH_FOLDER

from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.restapi.restapi_component import RestfulComponent
from tribler_core.components.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(RestfulComponent):
    watch_folder: WatchFolder = None

    async def run(self):
        await super().run()
        config = self.session.config
        notifier = self.session.notifier
        libtorrent_component = await self.require_component(LibtorrentComponent)

        watch_folder_path = config.watch_folder.get_path_as_absolute('directory', config.state_dir)
        watch_folder = WatchFolder(watch_folder_path=watch_folder_path,
                                   download_manager=libtorrent_component.download_manager,
                                   notifier=notifier)
        await self.set_readable_status(STATE_START_WATCH_FOLDER)
        watch_folder.start()
        self.watch_folder = watch_folder

    async def shutdown(self):
        await super().shutdown()
        if self.watch_folder:
            await self.watch_folder.stop()
