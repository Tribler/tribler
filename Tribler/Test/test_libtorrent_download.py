# see LICENSE.txt for license information

import unittest
import os
from time import time
import binascii

from Tribler.Core.simpledefs import DOWNLOAD
from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR


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
                os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"), self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfromfile() failed')

        self.startTest(do_downloadfromfile)

    def test_downloadfromurl(self):
        infohash = binascii.unhexlify('8C3760CB651C863861FA9ABE2EF70246943C1994')

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
            self.frame.startDownloadFromUrl(
                r'http://torrent.fedoraproject.org/torrents/Fedora-Live-Desktop-x86_64-19.torrent', self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfromurl() failed')

        self.startTest(do_downloadfromurl)

    def test_downloadfrommagnet(self):
        infohash = binascii.unhexlify('5ac55cf1b935291f6fc92ad7afd34597498ff2f7')

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
                r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfrommagnet() failed')

        self.startTest(do_downloadfrommagnet)

    def test_stopresumedelete(self):
        infohash = binascii.unhexlify('8C3760CB651C863861FA9ABE2EF70246943C1994')

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
            self.frame.startDownloadFromUrl(
                r'http://torrent.fedoraproject.org/torrents/Fedora-Live-Desktop-x86_64-19.torrent', self.getDestDir())
            self.CallConditional(60, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_start() failed')

        self.startTest(do_start)

    def test_playdownload(self):
        t = time()

        def take_screenshot(buffer_complete):
            self.screenshot("After streaming a libtorrent download (buffering took %.2f s)" % (buffer_complete - t))
            self.quit()

        def check_playlist():
            from Tribler.Core.Video.VideoPlayer import VideoPlayer
            from Tribler.Core.Video.utils import videoextdefaults

            buffer_complete = time()

            d = VideoPlayer.getInstance().get_vod_download()
            videofiles = []
            for filename in d.get_def().get_files():
                _, ext = os.path.splitext(filename)
                if ext.startswith('.'):
                    ext = ext[1:]
                if ext in videoextdefaults:
                    videofiles.append(filename)

            playlist = self.guiUtility.frame.actlist.expandedPanel_videoplayer

            do_check = lambda: len(playlist.links) == len(videofiles) and \
                playlist.tdef.get_infohash() == VideoPlayer.getInstance().get_vod_download().get_def().get_infohash() and \
                playlist.fileindex == VideoPlayer.getInstance().get_vod_fileindex()

            self.CallConditional(10, do_check, lambda: self.Call(
                5, lambda: take_screenshot(buffer_complete)), "playlist set incorrectly")

        def do_monitor():
            from Tribler.Core.Video.VideoPlayer import VideoPlayer

            self.screenshot('After starting a VOD download')
            self.CallConditional(60, lambda: VideoPlayer.getInstance()
                                 .vod_playing, check_playlist, "streaming did not start")

        def do_vod():
            from Tribler.Core.Video.VideoPlayer import VideoPlayer

            ds = self.frame.startDownload(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"),
                                          self.getDestDir(),
                                          selectedFiles=[
                                              os.path.join('Sample', 'Pioneer.One.S01E06.720p.x264.Sample-VODO.mkv')],
                                          vodmode=True)
            # set the max prebuffsize to be smaller so that the unit test runs faster
            ds.max_prebuffsize = 16 * 1024
            self.guiUtility.ShowPlayer()
            self.CallConditional(30, lambda: VideoPlayer.getInstance()
                                 .get_vod_download(), do_monitor, "VOD download not found")

        self.startTest(do_vod)


if __name__ == "__main__":
    unittest.main()
