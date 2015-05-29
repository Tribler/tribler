# see LICENSE.txt for license information
import binascii
import os
import unittest
from time import time

from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TestGuiAsServer, TESTS_DATA_DIR
from Tribler.Core.simpledefs import DOWNLOAD


TORRENT_R = r'http://torrent.fedoraproject.org/torrents/Fedora-Live-Workstation-x86_64-21.torrent'
TORRENT_INFOHASH = binascii.unhexlify('89f0835dc2def218ec4bac73da6be6b8c20534ea')

class TestLibtorrentDownload(TestGuiAsServer):

    def test_downloadfromfile(self):
        infohash = binascii.unhexlify('66ED7F30E3B30FA647ABAA19A36E7503AA071535')

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from file')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(
                infohash).original_data.ds.get_current_speed(DOWNLOAD) > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                infohash), item_shown_in_list, 'no download in librarylist')

        def do_downloadfromfile():
            self.guiUtility.showLibrary()
            self.frame.startDownload(
                os.path.join(TESTS_DATA_DIR, "Pioneer.One.S01E06.720p.x264-VODO.torrent"), self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfromfile() failed')

        self.startTest(do_downloadfromfile)

    def test_downloadfromurl(self):
        infohash = TORRENT_INFOHASH

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from url')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(
                infohash).original_data.ds.get_current_speed(DOWNLOAD) > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                infohash), item_shown_in_list, 'no download in librarylist')

        def do_downloadfromurl():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromUrl(TORRENT_R, self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfromurl() failed')

        self.startTest(do_downloadfromurl)

    def test_downloadfrommagnet(self):
        infohash = UBUNTU_1504_INFOHASH

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from magnet')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(60, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(
                infohash).original_data.ds.get_current_speed(DOWNLOAD) > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                infohash), item_shown_in_list, 'no download in librarylist')

        def do_downloadfrommagnet():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromMagnet(
                r'magnet:?xt=urn:btih:%s&dn=ubuntu-14.04.2-desktop-amd64.iso' % binascii.hexlify(UBUNTU_1504_INFOHASH),
                self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfrommagnet() failed')

        self.startTest(do_downloadfrommagnet)

    def test_stopresumedelete(self):
        infohash = TORRENT_INFOHASH

        def do_final():
            self.screenshot('After deleting a libtorrent download')
            self.quit()

        def do_deletedownload():
            self.screenshot('After resuming a libtorrent download')

            self.frame.librarylist.list.Select(infohash)
            self.frame.top_bg.OnDelete(silent=True)
            self.CallConditional(10, lambda: not self.frame.librarylist.list.HasItem(
                infohash), lambda: self.Call(1, do_final), 'download not deleted')

        def do_resume():
            self.screenshot('After stopping a libtorrent download')

            self.frame.librarylist.list.Select(infohash)
            self.frame.top_bg.OnResume()
            self.CallConditional(10, lambda: 'stopped' not in self.frame.librarylist.list.GetItem(
                infohash).original_data.state, do_deletedownload, 'download not resumed')

        def do_stop():
            self.screenshot('After starting a libtorrent download')

            self.frame.librarylist.list.Select(infohash)
            self.frame.top_bg.OnStop()
            self.CallConditional(10, lambda: 'stopped' in self.frame.librarylist.list.GetItem(
                infohash).original_data.state, do_resume, 'download not stopped')

        def item_shown_in_list():
            self.CallConditional(30, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(
                infohash).original_data.ds.progress > 0, do_stop, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                infohash), item_shown_in_list, 'no download in librarylist')

        def do_start():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromUrl(TORRENT_R, self.getDestDir())
            self.CallConditional(60, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_start() failed')

        self.startTest(do_start)

    def test_playdownload(self):
        t = time()

        def take_screenshot(buffer_complete):
            self.screenshot("After streaming a libtorrent download (buffering took %.2f s)" % (buffer_complete - t))
            self.quit()

        def check_playlist():
            from Tribler.Core.Video.utils import videoextdefaults

            buffer_complete = time()

            d = self.guiUtility.videoplayer.get_vod_download()
            videofiles = []
            for filename in d.get_def().get_files():
                _, ext = os.path.splitext(filename)
                if ext.startswith('.'):
                    ext = ext[1:]
                if ext in videoextdefaults:
                    videofiles.append(filename)

            playlist = self.guiUtility.frame.actlist.expandedPanel_videoplayer

            do_check = lambda: len(playlist.links) == len(videofiles) and \
                playlist.tdef.get_infohash() == self.guiUtility.videoplayer.get_vod_download().get_def().get_infohash() and \
                playlist.fileindex == self.guiUtility.videoplayer.get_vod_fileindex()

            self.CallConditional(10, do_check, lambda: self.Call(
                5, lambda: take_screenshot(buffer_complete)), "playlist set incorrectly")

        def do_monitor():
            self.screenshot('After starting a VOD download')
            self.CallConditional(60, lambda: self.guiUtility.videoplayer
                                 .vod_playing, check_playlist, "streaming did not start")

        def do_vod():
            from Tribler.Core.Video.VideoPlayer import VideoPlayer

            ds = self.frame.startDownload(os.path.join(TESTS_DATA_DIR, "Pioneer.One.S01E06.720p.x264-VODO.torrent"),
                                          self.getDestDir(),
                                          selectedFiles=[
                                              os.path.join('Sample', 'Pioneer.One.S01E06.720p.x264.Sample-VODO.mkv')],
                                          vodmode=True)
            # set the max prebuffsize to be smaller so that the unit test runs faster
            ds.max_prebuffsize = 16 * 1024
            self.guiUtility.ShowPlayer()
            self.CallConditional(30, lambda: self.guiUtility.videoplayer
                                 .get_vod_download(), do_monitor, "VOD download not found")

        self.startTest(do_vod)


if __name__ == "__main__":
    unittest.main()
