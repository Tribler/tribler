import logging
import os
from pathlib import Path

from ipv8.taskmanager import TaskManager

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.utilities import path_util
from tribler.core.utilities.notifier import Notifier

WATCH_FOLDER_CHECK_INTERVAL = 10


class WatchFolder(TaskManager):
    def __init__(self, state_dir: Path, settings: WatchFolderSettings, download_manager: DownloadManager,
                 notifier: Notifier):
        super().__init__()
        self.state_dir = state_dir
        self.settings = settings
        self.download_manager = download_manager
        self.notifier = notifier

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f'Initialised with {settings}')

    def start(self):
        self.register_task("check watch folder", self.check_watch_folder, interval=WATCH_FOLDER_CHECK_INTERVAL)

    async def stop(self):
        await self.shutdown_task_manager()

    def cleanup_torrent_file(self, root, name):
        fullpath = root / name
        if not fullpath.exists():
            self._logger.warning("File with path %s does not exist (anymore)", root / name)
            return
        path = Path(str(fullpath) + ".corrupt")
        try:
            path.unlink(missing_ok=True)
            fullpath.rename(path)
        except (PermissionError, FileExistsError) as e:
            self._logger.warning(f'Cant rename the file to {path}. Exception: {e}')

        self._logger.warning("Watch folder - corrupt torrent file %s", name)
        self.notifier[notifications.watch_folder_corrupt_file](name)

    def check_watch_folder(self):
        self._logger.debug(f'Checking watch folder...')

        if not self.settings.enabled or not self.state_dir:
            self._logger.debug(f'Cancelled. Enabled: {self.settings.enabled}. State dir: {self.state_dir}.')
            return

        directory = self.settings.get_path_as_absolute('directory', self.state_dir)
        if not directory.is_dir():
            self._logger.debug(f'Cancelled. Is not directory: {directory}.')
            return

        # Make sure that we pass a str to os.walk
        watch_dir = str(directory)
        self._logger.debug(f'Watch dir: {watch_dir}')

        for root, _, files in os.walk(watch_dir):
            root = path_util.Path(root)
            for name in files:
                if not name.endswith(".torrent"):
                    continue

                try:
                    tdef = TorrentDef.load(root / name)
                    if not tdef.get_metainfo():
                        self.cleanup_torrent_file(root, name)
                        continue
                except:  # torrent appears to be corrupt
                    self.cleanup_torrent_file(root, name)
                    continue

                infohash = tdef.get_infohash()

                if not self.download_manager.download_exists(infohash):
                    self._logger.info("Starting download from torrent file %s", name)
                    self.download_manager.start_download(torrent_file=root / name)
        self._logger.debug(f'Checking watch folder completed.')
