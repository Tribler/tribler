# see LICENSE.txt for license information

import unittest
import os
from time import time

import binascii
from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr

DEBUG = True


class TestLibtorrentDownload(TestGuiAsServer):

    def test_downloadfromfile(self):
        infohash = binascii.unhexlify('66ED7F30E3B30FA647ABAA19A36E7503AA071535')

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from file')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(infohash).original_data.ds.progress > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list, 'no download in librarylist')

        def do_downloadfromfile():
            self.guiUtility.showLibrary()
            self.frame.startDownload(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"), self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_downloadfromfile)

    def test_downloadfromurl(self):
        infohash = binascii.unhexlify('24ad1d85206db5f85491a690e6723e27f4551e01')

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from url')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(infohash).original_data.ds.progress > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list, 'no download in librarylist')

        def do_downloadfromurl():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromUrl(r'http://www.clearbits.net/get/1678-zenith-part-1.torrent', self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_downloadfromurl)

    def test_downloadfrommagnet(self):
        infohash = binascii.unhexlify('5ac55cf1b935291f6fc92ad7afd34597498ff2f7')

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from magnet')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(60, lambda: self.frame.librarylist.list.GetItem(infohash).original_data.ds and self.frame.librarylist.list.GetItem(infohash).original_data.ds.progress > 0, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list, 'no download in librarylist')

        def do_downloadfrommagnet():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromMagnet(r'magnet:?xt=urn:btih:5ac55cf1b935291f6fc92ad7afd34597498ff2f7&dn=Pioneer+One+S01E01+Xvid-VODO&title=', self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_downloadfrommagnet, True)

    def test_stopresumedelete(self):
        infohash = binascii.unhexlify('3d062d3b57481f23af8bd736ccfaaae0ccddf4b3')

        def do_final():
            self.assert_(infohash not in self.frame.librarylist.list.items, 'download not deleted')

            self.screenshot('After deleting a libtorrent download')
            self.quit()

        def do_deletedownload():
            self.assert_('stopped' not in self.frame.librarylist.list.GetItem(infohash).original_data.state, 'download not resumed')

            self.screenshot('After resuming a libtorrent download')

            self.frame.top_bg.OnDelete(silent=True)
            self.Call(10, do_final)

        def do_resume():
            self.assert_('stopped' in self.frame.librarylist.list.GetItem(infohash).original_data.state, 'download not stopped')

            self.screenshot('After stopping a libtorrent download')

            self.frame.top_bg.OnResume()
            self.Call(5, do_deletedownload)

        def do_stop():
            self.assert_(infohash in self.frame.librarylist.list.items, 'no download in librarylist')
            self.assert_(self.frame.librarylist.list.GetItem(infohash).original_data.ds.progress > 0, 'no download progress')

            self.screenshot('After starting a libtorrent download')

            self.frame.librarylist.list.Select(infohash)
            self.frame.top_bg.OnStop()
            self.Call(5, do_resume)

        def item_shown_in_list():
            self.Call(30, do_stop)

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list, 'no download in librarylist')

        def do_start():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromUrl(r'http://www.clearbits.net/get/1763-zenith-part-2.torrent', self.getDestDir())
            self.CallConditional(60, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_start)

    def test_playdownload(self):
        t = time()

        def take_screenshot():
            self.screenshot("After streaming a libtorrent download (buffering took %.2f s)" % (time() - t))
            self.quit()

        def check_playlist():
            from Tribler.Video.VideoPlayer import VideoPlayer
            from Tribler.Video.utils import videoextdefaults

            d = VideoPlayer.getInstance().get_vod_download()
            videofiles = []
            for filename in d.get_def().get_files():
                _, ext = os.path.splitext(filename)
                if ext.startswith('.'):
                    ext = ext[1:]
                if ext in videoextdefaults:
                    videofiles.append(filename)

            playlist = self.guiUtility.frame.actlist.expandedPanel_videoplayer
            self.CallConditional(1, lambda: len(playlist.links) == len(videofiles), take_screenshot)

        def do_monitor():
            from Tribler.Video.VideoPlayer import VideoPlayer

            d = VideoPlayer.getInstance().get_vod_download()
            self.assert_(bool(d), "No VOD download found")

            self.screenshot('After starting a VOD download')
            self.CallConditional(60, lambda: d.network_get_vod_stats()['status'] == "started", check_playlist, "streaming did not start")

        def do_vod():
            self.frame.startDownloadFromUrl(r'http://www.clearbits.net/get/8-blue---a-short-film.torrent', self.getDestDir(), selectedFiles=[os.path.join('Content', 'blue-a-short-film-divx.avi')], vodmode=True)
            self.guiUtility.ShowPlayer()
            self.Call(30, do_monitor)

        self.startTest(do_vod)


if __name__ == "__main__":
    unittest.main()
