import logging
import os
import shutil
import time
import copy

from os import path
from platform import system

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Main.vwxGUI import forceWxThread


class LibtorrentTest(object):

    """
    @param ProxyCommunity proxy : The proxy community instance
    @param Tribler.Core.Session.Session tribler_session: The Tribler Session
    """

    def __init__(self, proxy, tribler_session):
        super(LibtorrentTest, self).__init__()

        self._logger = logging.getLogger(__name__)
        self.proxy = proxy
        self.tribler_session = tribler_session

        self.download_started_at = None
        self.download_finished_at = None

    def _mark_test_completed(self):
        filename = os.path.join(self.tribler_session.get_state_dir(), "anon_test.txt")
        handle = open(filename, "w")

        try:
            handle.write("Delete this file to redo the anonymous download test")
        finally:
            handle.close()

    def on_unload(self):
        pass

    def has_completed_before(self):
        return os.path.isfile(os.path.join(self.tribler_session.get_state_dir(), "anon_test.txt"))

    @forceWxThread
    def start(self):
        import wx
        from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING
        from Tribler.Core.TorrentDef import TorrentDef

        hosts = [("95.211.198.147", 51413), ("95.211.198.142", 51413),
                 ("95.211.198.140", 51413), ("95.211.198.141", 51413)]

        @forceWxThread
        def thank_you(file_size, start_time, end_time):
            avg_speed_KBps = 1.0 * file_size / (end_time - start_time) / 1024.0
            wx.MessageBox('Your average speed was %.2f KB/s. ' % (avg_speed_KBps) +
                          'Tribler will now start seeding the test download anonymously.',
                          'Download Completed', wx.OK | wx.ICON_INFORMATION)

        def state_call():
            def _callback(ds):

                if ds.get_status() == DLSTATUS_DOWNLOADING:
                    if not self.download_started_at:
                        self.download_started_at = time.time()

                elif ds.get_status() == DLSTATUS_SEEDING and self.download_started_at and not self.download_finished_at:
                    self.download_finished_at = time.time()

                    self._mark_test_completed()

                    thank_you(ds.get_length(), self.download_started_at, self.download_finished_at)

                return 4.0, False

            return _callback

        # Load torrent
        torrent_path = "anon_test.torrent"
        if system() == "Linux" and path.exists("/usr/share/tribler/anon_test.torrent"):
            torrent_path = "/usr/share/tribler/anon_test.torrent"

        assert path.exists(torrent_path), torrent_path
        from Tribler.Core.TorrentDef import TorrentDef
        tdef = TorrentDef.load(torrent_path)
        tdef.set_private()  # disable dht

        if self.has_completed_before() or self.tribler_session.get_download(tdef.get_infohash()):
            self._logger.error("Skipping Anon Test since it has been run before")
            return False

        destination_dir = os.path.join(self.tribler_session.get_state_dir(), "anon_test")

        shutil.rmtree(destination_dir, ignore_errors=True)

        frame = None
        try:
            # If we want to attempt to use hidden services, we need to use MainFrame.startDownload
            from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
            frame = GUIUtility.getInstance().frame

        except:
            self._logger.error("Could not execute startDownload. Running Tribler without the GUI?")
            return

        download = frame.startDownload(tdef=tdef, destdir=destination_dir, hops=2)

        if not download:
            self._logger.error("Could not start test download")
            return

        download.set_state_callback(state_call(), delay=4)

        for peer in hosts:
            download.add_peer(peer)
