import logging
import os
from pathlib import Path

from ipv8.taskmanager import TaskManager

from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.session import Session

logger = logging.getLogger(__name__)


class WatchFolderManager:
    """
    Watch the torrent files in a folder.

    Add torrents that are in this folder and remove torrents that are removed while we are watching.
    """

    def __init__(self, session: Session, task_manager: TaskManager) -> None:
        """
        Attach to the given task manager.
        """
        super().__init__()
        self.session = session
        self.task_manager = task_manager

    def start(self) -> None:
        """
        Start the periodic processing of the watch folder.
        """
        update_interval = self.session.config.get("watch_folder/check_interval")
        self.task_manager.register_task("Watch Folder", self.check, interval=update_interval, delay=update_interval)

    def check(self) -> bool:
        """
        Check the watch folder for new torrents and start downloading them.
        """
        logger.debug("Checking watch folder...")
        str_directory = self.session.config.get("watch_folder/directory")
        if not str_directory:
            logger.debug("Cancelled. Directory: %s.", str_directory)
            return False

        path_directory = Path(str_directory).absolute()
        logger.info("Checking watch folder: %s", str(path_directory))
        if not path_directory.exists():
            logger.warning("Cancelled. Directory does not exist: %s.", str(path_directory))
            return False

        if not path_directory.is_dir():
            logger.warning("Cancelled. Is not directory: %s.", str(path_directory))
            return False

        processed: set[Path] = set()
        for root, _, files in os.walk(str(path_directory)):
            for name in files:
                path = Path(root) / name
                processed.add(path)
                if not name.endswith(".torrent"):
                    continue
                self.task_manager.replace_task(f"Process file {path!s}", self.process_torrent_file, path)

        logger.debug("Checking watch folder completed.")
        return True

    async def process_torrent_file(self, path: Path) -> None:
        """
        Process an individual torrent file.
        """
        logger.debug("Add watched torrent file: %s", str(path))
        try:
            tdef = await TorrentDef.load(path)
            if not self.session.download_manager.download_exists(tdef.infohash):
                logger.info("Starting download from torrent file %s", path.name)
                await self.session.download_manager.start_download(torrent_file=path, tdef=tdef)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Exception while adding watched torrent! %s: %s", e.__class__.__name__, str(e))
