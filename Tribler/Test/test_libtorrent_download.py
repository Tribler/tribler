# see LICENSE.txt for license information
import binascii
import os
import shutil
import unittest
from time import time
from Tribler.Core.Utilities.network_utils import get_random_port

from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TestGuiAsServer, TESTS_DATA_DIR
from Tribler.Core.simpledefs import DOWNLOAD, DLSTATUS_SEEDING

TORRENT_FILE = os.path.join(TESTS_DATA_DIR, "ubuntu-15.04-desktop-amd64.iso.torrent")
TORRENT_FILE_INFOHASH = binascii.unhexlify("fc8a15a2faf2734dbb1dc5f7afdc5c9beaeb1f59")
TORRENT_VIDEO_FILE = os.path.join(TESTS_DATA_DIR, "Night.Of.The.Living.Dead_1080p_archive.torrent")
TORRENT_VIDEO_FILE_INFOHASH = binascii.unhexlify("90ed3962785c52a774e89706fb4f811a468e6c05")


class TestLibtorrentDownload(TestGuiAsServer):

    def setup_video_seed(self):
        video_tdef, self.torrent_path = self.create_local_torrent(os.path.join(TESTS_DATA_DIR, 'video.avi'))
        self.torrent_infohash = video_tdef.get_infohash()
        self.setup_seeder(video_tdef, TESTS_DATA_DIR)

    def item_has_downloaded(self):
            if self.frame.librarylist.list.HasItem(self.torrent_infohash):
                item = self.frame.librarylist.list.GetItem(self.torrent_infohash)
                return item.original_data.ds and item.original_data.ds.get_status() == DLSTATUS_SEEDING

    def test_downloadfromfile(self):

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from file')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, self.item_has_downloaded, make_screenshot, 'no download progress')

        def add_peer():
            download = self.session.get_download(self.torrent_infohash)
            download.add_peer(("127.0.0.1", self.seeder_session.get_listen_port()))

        def do_downloadfromfile():
            self.setup_video_seed()
            self.guiUtility.showLibrary()
            self.frame.startDownload(self.torrent_path, self.getDestDir())
            self.callLater(3, add_peer)

            self.CallConditional(30, lambda: self.session.get_download(self.torrent_infohash), item_shown_in_list,
                                 'do_downloadfromfile() failed')

        self.startTest(do_downloadfromfile)

    def test_downloadfromfileuri(self):

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from file URI')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(30, self.item_has_downloaded, make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                self.torrent_infohash), item_shown_in_list, 'no download in librarylist')

        def add_peer():
            download = self.session.get_download(self.torrent_infohash)
            download.add_peer(("127.0.0.1", self.seeder_session.get_listen_port()))

        def do_downloadfromfile():
            self.setup_video_seed()
            self.guiUtility.showLibrary()

            from urllib import pathname2url
            file_uri = "file:" + pathname2url(self.torrent_path)
            self.frame.startDownloadFromArg(file_uri, self.getDestDir())
            self.callLater(3, add_peer)

            self.CallConditional(30, lambda: self.session.get_download(self.torrent_infohash), download_object_ready,
                                 'do_downloadfromfile() failed')

        self.startTest(do_downloadfromfile)

    def test_downloadfromurl(self):

        def make_screenshot():
            self.screenshot('After starting a libtorrent download from url')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(10, lambda: self.frame.librarylist.list.GetItem(TORRENT_FILE_INFOHASH).original_data.ds and self.frame.librarylist.list.GetItem(TORRENT_FILE_INFOHASH).original_data.ds.get_current_speed(DOWNLOAD) > 0,
                                 make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                TORRENT_FILE_INFOHASH), item_shown_in_list, 'no download in librarylist')

        def do_downloadfromurl():
            self.guiUtility.showLibrary()
            self.frame.startDownloadFromArg(r'http://localhost:%s/ubuntu.torrent' % self.file_server_port,
                                            self.getDestDir())

            self.CallConditional(10, lambda: self.session.get_download(TORRENT_FILE_INFOHASH), download_object_ready,
                                 'do_downloadfromurl() failed')

        # Create directory with files and setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        self.file_server_port = get_random_port()
        self.setUpFileServer(self.file_server_port, files_path)

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
            self.frame.startDownloadFromArg(
                r'magnet:?xt=urn:btih:%s&dn=ubuntu-14.04.2-desktop-amd64.iso' % binascii.hexlify(UBUNTU_1504_INFOHASH),
                self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready,
                                 'do_downloadfrommagnet() failed')

        self.startTest(do_downloadfrommagnet)

    def test_stopresumedelete(self):
        infohash = TORRENT_VIDEO_FILE_INFOHASH

        def do_final():
            self.screenshot('After deleting a libtorrent download')
            self.quit()

        def do_deletedownload():
            self.screenshot('After resuming a libtorrent download')

            self.frame.librarylist.list.Select(infohash)
            self.frame.top_bg.OnDelete(silent=True)
            self.CallConditional(10, lambda: not self.frame.librarylist.list.HasItem(
                infohash), lambda: self.callLater(1, do_final), 'download not deleted')

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
            self.frame.startDownloadFromArg('file:' + TORRENT_VIDEO_FILE, self.getDestDir())
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

            self.CallConditional(10, do_check, lambda: self.callLater(
                5, lambda: take_screenshot(buffer_complete)), "playlist set incorrectly")

        def do_monitor():
            self.screenshot('After starting a VOD download')
            self.CallConditional(60, lambda: self.guiUtility.videoplayer
                                 .vod_playing, check_playlist, "streaming did not start")

        def add_peer():
            download = self.session.get_download(self.torrent_infohash)
            download.add_peer(("127.0.0.1", self.seeder_session.get_listen_port()))

        def do_vod():
            self.setup_video_seed()
            self.frame.startDownload(self.torrent_path, self.getDestDir(), vodmode=True)
            self.guiUtility.ShowPlayer()
            self.callLater(3, add_peer)
            self.CallConditional(30, self.guiUtility.videoplayer.get_vod_download, do_monitor, "VOD download not found")

        self.startTest(do_vod)


if __name__ == "__main__":
    unittest.main()
