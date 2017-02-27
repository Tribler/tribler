import logging
import os

from twisted.internet.task import LoopingCall

from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.utilities import fix_torrent
from Tribler.Core.simpledefs import NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, STATEDIR_GUICONFIG
from Tribler.dispersy.taskmanager import TaskManager


WATCH_FOLDER_CHECK_INTERVAL = 10


class WatchFolder(TaskManager):

    def __init__(self, session):
        super(WatchFolder, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        gui_config_file_path = os.path.join(self.session.get_state_dir(), STATEDIR_GUICONFIG)
        config = CallbackConfigParser()
        config.read_file(gui_config_file_path, 'utf-8-sig')
        self.tribler_gui_config = config.get_config_as_json()

    def start(self):
        self.register_task("check watch folder", LoopingCall(self.check_watch_folder))\
            .start(WATCH_FOLDER_CHECK_INTERVAL, now=False)

    def stop(self):
        self.cancel_all_pending_tasks()

    def cleanup_torrent_file(self, root, name):
        os.rename(os.path.join(root, name), os.path.join(root, name + ".corrupt"))
        self._logger.warning("Watch folder - corrupt torrent file %s", name)
        self.session.notifier.notify(NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, None, name)

    def check_watch_folder(self):
        if not os.path.isdir(self.session.get_watch_folder_path()):
            return

        for root, _, files in os.walk(self.session.get_watch_folder_path()):
            for name in files:
                if not name.endswith(u".torrent"):
                    continue

                try:
                    tdef = TorrentDef.load_from_memory(fix_torrent(os.path.join(root, name)))
                except:  # torrent appears to be corrupt
                    self.cleanup_torrent_file(root, name)
                    continue

                infohash = tdef.get_infohash()

                if not self.session.has_download(infohash):
                    self._logger.info("Starting download from torrent file %s", name)
                    dl_config = DefaultDownloadStartupConfig.getInstance().copy()

                    anon_enabled = self.tribler_gui_config['Tribler']['default_anonymity_enabled']
                    default_num_hops = self.tribler_gui_config['Tribler']['default_number_hops']
                    dl_config.set_hops(default_num_hops if anon_enabled else 0)
                    dl_config.set_safe_seeding(self.tribler_gui_config['Tribler']['default_safeseeding_enabled'])
                    self.session.lm.ltmgr.start_download(tdef=tdef, dconfig=dl_config)
