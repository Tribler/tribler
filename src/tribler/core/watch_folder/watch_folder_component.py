from tribler.core.components.component import Component
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(Component):
    watch_folder: WatchFolder = None

    async def run(self):
        await super().run()
        notifier = self.session.notifier
        libtorrent_component = await self.require_component(LibtorrentComponent)

        watch_folder = WatchFolder(
            state_dir=self.session.config.state_dir,
            settings=self.session.config.watch_folder,
            download_manager=libtorrent_component.download_manager,
            notifier=notifier
        )
        watch_folder.start()
        self.watch_folder = watch_folder

    async def shutdown(self):
        await super().shutdown()
        if self.watch_folder:
            await self.watch_folder.stop()
