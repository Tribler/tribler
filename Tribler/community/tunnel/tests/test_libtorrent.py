import logging
import os
import time
from Tribler.community.anontunnel.events import TunnelObserver
import shutil


class LibtorrentTest(TunnelObserver):
    """
    @param ProxyCommunity proxy : The proxy community instance
    @param Tribler.Core.Session.Session tribler_session: The Tribler Session
    """

    def __init__(self, proxy, tribler_session, delay):
        super(LibtorrentTest, self).__init__()

        self._logger = logging.getLogger(__name__)
        self.proxy = proxy
        self.tribler_session = tribler_session
        self.delay = delay
        self.tribler_session.lm.rawserver.add_task(self.schedule)
        self.download = None
        self.stopping = False

        self.download_started_at = None
        self.download_finished_at = None

    def schedule(self):
        self._logger.debug("Scheduling Anonymous LibTorrent download")
        self.tribler_session.lm.rawserver.add_task(self.start, self.delay)

    def _mark_test_completed(self):
        filename = self.tribler_session.get_state_dir() + "/anon_test.txt"
        handle = open(filename, "w")

        try:
            handle.write("Delete this file to redo the anonymous download test")
        finally:
            handle.close()

    def on_unload(self):
        self.stop()

    def stop(self, delay=0.0):
        if self.download:
            def remove_download():
                self.tribler_session.remove_download(self.download, True, True)
                self.download = None
                self._logger.error("Removed test download")

            self.tribler_session.lm.rawserver.add_task(remove_download, delay=delay)

    def _has_completed_before(self):
        return os.path.isfile(self.tribler_session.get_state_dir() + "/anon_test.txt")

    def start(self):
        from Tribler.community.anontunnel.stats import StatsCollector
        import wx
        from Tribler.Core.TorrentDef import TorrentDef
        from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING
        from Tribler.Main.globals import DefaultDownloadStartupConfig
        from Tribler.Main.vwxGUI import forceWxThread

        hosts = [("94.23.38.156", 51413), ("95.211.198.147", 51413), ("95.211.198.142", 51413), ("95.211.198.140", 51413), ("95.211.198.141", 51413)]

        @forceWxThread
        def thank_you(file_size, start_time, end_time):
            avg_speed_KBps = 1.0 * file_size / (end_time - start_time) / 1024.0
            wx.MessageBox('Your average speed was %.2f KB/s' % (avg_speed_KBps) , 'Download Completed', wx.OK | wx.ICON_INFORMATION)

        def state_call():
            stats_collector = StatsCollector(self.proxy, "AnonTest")

            def _callback(ds):
                if self.stopping:
                    return 1.0, False

                if ds.get_status() == DLSTATUS_DOWNLOADING:
                    if not self.download_started_at:
                        self.download_started_at = time.time()
                        stats_collector.start()

                    stats_collector.download_stats = {
                        'size': ds.get_progress() * ds.get_length(),
                        'download_time': time.time() - self.download_started_at
                    }

                elif ds.get_status() == DLSTATUS_SEEDING and self.download_started_at and not self.download_finished_at:
                    self.download_finished_at = time.time()
                    stats_collector.download_stats = {
                        'size': ds.get_length(),
                        'download_time': self.download_finished_at - self.download_started_at
                    }

                    stats_collector.share_stats()
                    stats_collector.stop()
                    self.stop(5.0)

                    self._mark_test_completed()

                    thank_you(ds.get_length(), self.download_started_at, self.download_finished_at)
                return 1.0, False

            return _callback

        if self._has_completed_before():
            self._logger.warning("Skipping Anon Test since it has been run before")
            return False

        destination_dir = self.tribler_session.get_state_dir() + "/anon_test/"

        try:
            shutil.rmtree(destination_dir)
        except:
            pass

        tdef = TorrentDef.load("anon_test.torrent")
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        ''' :type : DefaultDownloadStartupConfig '''

        dscfg.set_anon_mode(True)
        dscfg.set_dest_dir(destination_dir)

        self.download = self.tribler_session.start_download(tdef, dscfg)
        self.download.set_state_callback(state_call(), delay=1)

        for peer in hosts:
            self.download.add_peer(peer)
