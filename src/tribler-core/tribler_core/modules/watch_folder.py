import logging
import os
from pathlib import Path

from ipv8.taskmanager import TaskManager

from tribler_common.simpledefs import NTFY

from tribler_core.modules.libtorrent.download_config import DownloadConfig, get_default_dest_dir
from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.notifier import Notifier
from tribler_core.utilities import path_util

WATCH_FOLDER_CHECK_INTERVAL = 10


class WatchFolder(TaskManager):

    def __init__(self, watch_folder_path, download_manager: DownloadManager, notifier: Notifier):
        super().__init__()
        self.watch_folder = watch_folder_path
        self.download_manager = download_manager
        self.notifier = notifier

        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self):
        self.register_task("check watch folder", self.check_watch_folder, interval=WATCH_FOLDER_CHECK_INTERVAL)

    async def stop(self):
        await self.shutdown_task_manager()

    def cleanup_torrent_file(self, root, name):
        fullpath = root / name
        if not fullpath.exists():
            self._logger.warning("File with path %s does not exist (anymore)", root / name)
            return

        fullpath.rename(Path(str(fullpath)+".corrupt"))
        self._logger.warning("Watch folder - corrupt torrent file %s", name)
        self.notifier.notify(NTFY.WATCH_FOLDER_CORRUPT_FILE, name)

    def check_watch_folder(self):
        if not self.watch_folder.is_dir():
            return

        # Make sure that we pass a str to os.walk
        watch_dir = str(self.watch_folder)

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

                if not self.dlmgr.download_exists(infohash):
                    self._logger.info("Starting download from torrent file %s", name)
                    dl_config = DownloadConfig()

                    anon_enabled = config.download_defaults.anonymity_enabled
                    default_num_hops = config.download_defaults.number_hops
                    default_destination = config.download_defaults.get_path_as_absolute('saveas', config.state_dir)
                    destination_dir = default_destination or get_default_dest_dir()
                    dl_config.set_hops(default_num_hops if anon_enabled else 0)
                    dl_config.set_safe_seeding(config.download_defaults.safeseeding_enabled)
                    dl_config.set_dest_dir(destination_dir)
                    self.dlmgr.start_download(tdef=tdef, config=dl_config)
