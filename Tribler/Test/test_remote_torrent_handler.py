# see LICENSE.txt for license information

import os
import sys
from shutil import copyfile, rmtree
from time import sleep
from threading import Event

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR
from Tribler.dispersy.candidate import Candidate


class TestRemoteTorrentHandler(TestAsServer):
    """ Tests the download_torrent() method of TestRemoteTorrentHandler.
    """

    def test_remotedownload(self):
        def do_check_download(torrent_file=None):
            des_file_path = os.path.join(self.session2.get_torrent_collecting_dir(), self.file_name)
            self.assertTrue(os.path.exists(des_file_path) and os.path.isfile(des_file_path),
                            u"Failed to download torrent file.")

            print >> sys.stderr, u"Torrent file downloaded successfully."
            self.quit()
            self.download_event.set()

        def do_start_download():
            self.setup_downloader()

            timeout = 10

            candidate = Candidate(("127.0.0.1", self.session1_port), False)
            self.session2.lm.rtorrent_handler.download_torrent(candidate, self.infohash, usercallback=do_check_download)
            self.CallConditional(timeout, self.download_event.is_set, do_check_download,
                                 u"Failed to download torrent within %s seconds" % timeout)

        self.startTest(do_start_download)

    def startTest(self, callback):
        super(TestRemoteTorrentHandler, self).startTest(callback)

    def setUpPreSession(self):
        super(TestRemoteTorrentHandler, self).setUpPreSession()
        self.config.set_dispersy(True)

    def tearDown(self):
        self._shutdown_session(self.session2)
        self.session2 = None
        rmtree(self.session2_state_dir)
        rmtree(self.session2_torrent_collecting_dir)
        super(TestRemoteTorrentHandler, self).tearDown()

    def setup_downloader(self):
        self.download_event = Event()
        self.session1_port = self.session.get_dispersy_port()

        infohash_str = "41aea20908363a80d44234e8fef07fab506cd3b4"
        self.infohash = infohash_str.decode('hex')
        self.file_name = u"%s.torrent" % infohash_str

        # copy file to the uploader's torrent_collecting_dir
        src_file_path = os.path.join(BASE_DIR, u"data", self.file_name)
        des_file_path = os.path.join(self.session.get_torrent_collecting_dir(), self.file_name)
        print >> sys.stderr, u"Uploader's torrent_collect_dir = %s" % self.session.get_torrent_collecting_dir()
        copyfile(src_file_path, des_file_path)

        from Tribler.Core.Session import Session

        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_torrent_collecting(True)

        self.session2_state_dir = self.session.get_state_dir() + "2"
        self.session2_torrent_collecting_dir = self.session.get_torrent_collecting_dir() + "2"

        self.config2.set_state_dir(self.session2_state_dir)
        self.config2.set_torrent_collecting_dir(self.session2_torrent_collecting_dir)
        self.session2 = Session(self.config2, ignore_singleton=True)
        self.session2.start()
        sleep(1)

        print >> sys.stderr, u"Downloader's torrent_collect_dir = %s" % self.session2.get_torrent_collecting_dir()
