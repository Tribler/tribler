import hashlib
import logging
import os
from twisted.internet.task import LoopingCall
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import fix_torrent
from Tribler.Core.simpledefs import NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT
from Tribler.dispersy.taskmanager import TaskManager


WATCH_FOLDER_CHECK_INTERVAL = 10


class WatchFolder(TaskManager):

    def __init__(self, session):
        super(WatchFolder, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def start(self):
        self.register_task("check watch folder", LoopingCall(self.check_watch_folder))\
            .start(WATCH_FOLDER_CHECK_INTERVAL, now=False)

    def stop(self):
        self.cancel_all_pending_tasks()

    def check_watch_folder(self):
        if not os.path.isdir(self.session.get_watch_folder_path()):
            return

        for root, _, files in os.walk(self.session.get_watch_folder_path()):
            for name in files:
                if not name.endswith(u".torrent"):
                    continue

                torrent_data = fix_torrent(os.path.join(root, name))
                if not torrent_data:  # torrent appears to be corrupt
                    os.rename(os.path.join(root, name), os.path.join(root, name + ".corrupt"))
                    self._logger.warning("Watch folder - corrupt torrent file %s", name)
                    self.session.notifier.notify(NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, None, name)
                    continue

                tdef = TorrentDef.load_from_memory(torrent_data)
                infohash = tdef.get_infohash()

                if not self.session.has_download(infohash):
                    self._logger.info("Starting download from torrent file %s", name)
                    self.session.lm.ltmgr.start_download(tdef=tdef)
