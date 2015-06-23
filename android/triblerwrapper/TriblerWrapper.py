from kivy.logger import Logger
import time

from TriblerSession import TriblerSession
from DownloadManager import DownloadManager
from SettingsManager import SettingsManager
from TorrentManager import TorrentManager
# from ChannelManager import ChannelManager


class TriblerWrapper:
    tribler = None
    dm = None
    tm = None
    cm = None
    sm = None

    def __init__(self):
        self.tribler = TriblerSession(None)

    def stop(self):
        self.tribler.stop_session()

    def keep_running(self):
        return self.tribler.is_running()

    def start(self):
        self.tribler.start_session()

        # Wait for dispersy to initialize
        while not self.tribler.is_running():
            time.sleep(1)

        # Logger.error("Loading ChannelManager")
        # self.cm = ChannelManager.getInstance(self.tribler.get_session())

        Logger.error("Loading TorrentManager")
        self.tm = TorrentManager.getInstance(self.tribler.get_session())

        Logger.error("Loading DownloadManager")
        self.dm = DownloadManager.getInstance(self.tribler.get_session())

        Logger.error("Loading ConfigurationManager")
        # Load this last because it sets settings in other managers
        self.sm = SettingsManager.getInstance(self.tribler.get_session())

    def get_session_mgr(self):
        return self.tribler

    def get_download_mgr(self):
        return self.dm

    def get_torrent_mgr(self):
        return self.tm

    def get_settings_mgr(self):
        return self.sm
