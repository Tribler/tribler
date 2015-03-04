# see LICENSE.txt for license information

import os
from shutil import rmtree, copytree
from time import sleep
from threading import Event

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import call_on_reactor_thread

from unittest import skip


class TestRemoteTorrentHandler(TestAsServer):

    """ Tests the download_torrent() method of TestRemoteTorrentHandler.
    """

    def __init__(self, *argv, **kwargs):
        super(TestRemoteTorrentHandler, self).__init__(*argv, **kwargs)

        self.file_names = {}
        self.infohash_strs = {}
        self.infohashes = {}

    def setUpPreSession(self):
        super(TestRemoteTorrentHandler, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_torrent_store(True)

    def tearDown(self):
        self._shutdown_session(self.session2)
        self.session2 = None
        rmtree(self.session2_state_dir)
        super(TestRemoteTorrentHandler, self).tearDown()

    def test_torrentdownload(self):
        self._logger.info(u"Start torrent download test...")

        def do_check_download(torrent_file=None):

            for i, infohash_str in enumerate(self.infohash_strs):
                self._logger.info(u"Checking... %s", self.file_names[i])
                for item in self.session2.lm.torrent_store.iterkeys():
                    self.assertTrue(infohash_str in self.session2.lm.torrent_store,
                                    u"Failed to download torrent file 1.")

            self._logger.info(u"Torrent files 1 and 2 downloaded successfully.")
            self.download_event.set()
            self.quit()

        def do_start_download():
            self.setup_torrentdownloader()

            @call_on_reactor_thread
            def _start_download():
                candidate = Candidate(("127.0.0.1", self.session1_port), False)
                self.session2.lm.rtorrent_handler.download_torrent(candidate, self.infohashes[0])
                self.session2.lm.rtorrent_handler.download_torrent(candidate, self.infohashes[1],
                                                                   user_callback=do_check_download)

            _start_download()

            timeout = 10
            self.CallConditional(timeout, self.download_event.is_set,
                                 do_check_download, u"Failed to download torrent within %s seconds" % timeout)

        self.startTest(do_start_download)

    def setup_torrentdownloader(self):
        self.download_event = Event()
        self.session1_port = self.session.get_dispersy_port()

        self.infohash_strs = ["41aea20908363a80d44234e8fef07fab506cd3b4",
                              "45a647b1120ed9fe7f793e17585efb4b0efdf1a5"]

        for i, infohash in enumerate(self.infohash_strs):
            self.infohashes[i] = infohash.decode('hex')
            self.file_names[i] = file_name = u"%s.torrent" % infohash

            # Put the torrents into the uploader's store
            with open(os.path.join(BASE_DIR, u"data", file_name), 'r') as torrent_file:
                self.session.lm.torrent_store.put(infohash, torrent_file.read())

        from Tribler.Core.Session import Session

        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_megacache(True)
        self.config2.set_torrent_collecting(True)

        self.session2_state_dir = self.session.get_state_dir() + u"2"
        self.config2.set_state_dir(self.session2_state_dir)

        self.session2 = Session(self.config2, ignore_singleton=True)
        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session2.start()
        sleep(1)

    @skip("The metadata collecting is not used ATM, broken by the new torrent store stuff too")
    def test_metadatadownload(self):
        self._logger.info(u"Start metadata download test...")

        def do_check_download(torrent_file=None):
            des_file_path = os.path.join(u"", self.metadata_dir)
            self.assertTrue(os.path.exists(des_file_path) and os.path.isdir(des_file_path),
                            u"Failed to download metadata.")

            self._logger.info(u"metadata downloaded successfully.")
            self.quit()
            self.download_event.set()

        def do_start_download():
            self.setup_metadatadownloader()

            timeout = 10

            candidate = Candidate(("127.0.0.1", self.session1_port), False)
            self.session2.lm.rtorrent_handler.download_metadata(candidate, self.infohash, self.metadata_subpath,
                                                                usercallback=do_check_download)
            self.CallConditional(timeout, self.download_event.is_set, do_check_download,
                                 u"Failed to download metadata within %s seconds" % timeout)

        self.startTest(do_start_download)

    def setup_metadatadownloader(self):
        self.download_event = Event()
        self.session1_port = self.session.get_dispersy_port()

        infohash_str = "41aea20908363a80d44234e8fef07fab506cd3b4"
        self.infohash = infohash_str.decode('hex')
        self.metadata_dir = u"%s" % infohash_str

        self.metadata_subpath = os.path.join(self.metadata_dir, u"421px-Pots_10k_100k.jpeg")

        # copy file to the uploader's torrent_collecting_dir
        src_dir_path = os.path.join(BASE_DIR, u"data", self.metadata_dir)
        des_dir_path = os.path.join(u"", self.metadata_dir)
        self._logger.info(u"Uploader's torrent_collect_dir = %s", u"")
        copytree(src_dir_path, des_dir_path)

        from Tribler.Core.Session import Session

        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_megacache(True)
        self.config2.set_torrent_collecting(True)

        self.session2_state_dir = self.session.get_state_dir() + u"2"
        self.config2.set_state_dir(self.session2_state_dir)

        self.session2 = Session(self.config2, ignore_singleton=True)
        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session2.start()
        sleep(1)

        self._logger.info(u"Downloader's torrent_collect_dir = %s", u"")
        self._logger.info(u"Uploader port: %s, Downloader port: %s",
                          self.session1_port, self.session2.get_dispersy_port())
