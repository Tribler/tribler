import asyncio
import logging
import os

from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.reporter.exception_handler import NoCrashException
from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.utilities.async_group.async_group import AsyncGroup
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.path_util import Path

WATCH_FOLDER_CHECK_INTERVAL = 10


class WatchFolder:
    def __init__(self, state_dir: Path, settings: WatchFolderSettings, download_manager: DownloadManager,
                 notifier: Notifier, check_interval: float = WATCH_FOLDER_CHECK_INTERVAL):
        super().__init__()
        self.state_dir = state_dir
        self.settings = settings
        self.download_manager = download_manager
        self.notifier = notifier
        self.check_interval = check_interval
        self.group = AsyncGroup()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f'Initialised with {settings}')

    def start(self):
        self.group.add_task(self._run())

    async def stop(self):
        await self.group.cancel()

    async def _run(self):
        while True:
            await asyncio.sleep(self.check_interval)
            self.group.add_task(self._check_watch_folder_handle_exceptions())

    async def _check_watch_folder_handle_exceptions(self):
        try:
            await self._check_watch_folder()
        except Exception as e:
            self._logger.exception(f'Failed download attempt: {e}')
            raise NoCrashException from e

    async def _check_watch_folder(self) -> bool:
        """ Check the watch folder for new torrents and start downloading them."""

        self._logger.debug('Checking watch folder...')
        if not self.settings.enabled or not self.state_dir:
            self._logger.debug(f'Cancelled. Enabled: {self.settings.enabled}. State dir: {self.state_dir}.')
            return False

        directory = self.settings.get_path_as_absolute('directory', self.state_dir)
        self._logger.info(f'Checking watch folder: {directory}')
        if not directory.is_valid():
            self._logger.warning(f'Cancelled. Directory is not valid: {directory}.')
            return False

        if not directory.is_dir():
            self._logger.warning(f'Cancelled. Is not directory: {directory}.')
            return False

        for root, _, files in os.walk(str(directory)):
            for name in files:
                path = Path(root) / name
                await self._process_torrent_file(path)

        self._logger.debug('Checking watch folder completed.')
        return True

    async def _process_torrent_file(self, path: Path):
        if not path.name.endswith(".torrent"):
            return

        self._logger.info(f'Torrent file found: {path}')
        exception = None
        try:
            await self._start_download(path)
        except Exception as e:  # pylint: disable=broad-except
            self._logger.error(f'{e.__class__.__name__}: {e}')
            exception = e

        if exception:
            self._logger.info(f'Corrupted: {path}')
            try:
                path.replace(f'{path}.corrupt')
            except OSError as e:
                self._logger.warning(f'{e.__class__.__name__}: {e}')

    async def _start_download(self, path: Path):
        tdef = await TorrentDef.load(path)
        if not tdef.get_metainfo():
            self._logger.warning(f'Missed metainfo: {path}')
            return

        infohash = tdef.get_infohash()

        if not self.download_manager.download_exists(infohash):
            self._logger.info("Starting download from torrent file %s", path.name)

            download_config = DownloadConfig.from_defaults(self.download_manager.download_defaults,
                                                           state_dir=self.state_dir)

            await self.download_manager.start_download(torrent_file=path, config=download_config)
