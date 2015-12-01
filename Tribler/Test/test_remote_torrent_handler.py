# see LICENSE.txt for license information

import os
from binascii import hexlify
from hashlib import sha1
from shutil import rmtree
from time import sleep
from threading import Event

from Tribler.Test.test_as_server import TestAsServer, TESTS_DATA_DIR
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import call_on_reactor_thread


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
        self.config.set_enable_metadata(True)

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
            with open(os.path.join(TESTS_DATA_DIR, file_name), 'r') as torrent_file:
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

    def test_metadata_download(self):
        self._logger.info(u"Start metadata download test...")

        def do_check_download(torrent_file=None):
            self.assertTrue(self.session2.lm.rtorrent_handler.has_metadata(self.thumb_hash))
            retrieved_data = self.session2.lm.rtorrent_handler.get_metadata(self.thumb_hash)
            assert retrieved_data == self.thumb_data, "metadata doesn't match"

            self._logger.info(u"metadata downloaded successfully.")
            self.quit()
            self.download_event.set()

        def do_start_download():
            self.setup_metadata_downloader()

            timeout = 10

            candidate = Candidate(("127.0.0.1", self.session1_port), False)
            self.session2.lm.rtorrent_handler.download_metadata(candidate, self.thumb_hash,
                                                                usercallback=do_check_download)
            self.CallConditional(timeout, self.download_event.is_set, do_check_download,
                                 u"Failed to download metadata within %s seconds" % timeout)

        self.startTest(do_start_download)

    def setup_metadata_downloader(self):
        self.download_event = Event()
        self.session1_port = self.session.get_dispersy_port()

        # load thumbnail, calculate hash, and save into the metadata_store
        infohash_str = "41aea20908363a80d44234e8fef07fab506cd3b4"
        self.infohash = infohash_str.decode('hex')
        self.metadata_dir = u"%s" % infohash_str

        self.thumb_file = os.path.join(unicode(TESTS_DATA_DIR), self.metadata_dir, u"421px-Pots_10k_100k.jpeg")
        with open(self.thumb_file, 'rb') as f:
            self.thumb_data = f.read()
        self.thumb_hash = sha1(self.thumb_data).digest()

        # start session
        from Tribler.Core.Session import Session
        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_megacache(True)
        self.config2.set_torrent_collecting(True)
        self.config2.set_enable_metadata(True)

        self.session2_state_dir = self.session.get_state_dir() + u"2"
        self.config2.set_state_dir(self.session2_state_dir)

        self.session2 = Session(self.config2, ignore_singleton=True)

        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session2.start()
        sleep(1)

        # save thumbnail into metadata_store
        thumb_hash_str = hexlify(self.thumb_hash)
        self.session.lm.metadata_store[thumb_hash_str] = self.thumb_data

        self._logger.info(u"Downloader's torrent_collect_dir = %s", u"")
        self._logger.info(u"Uploader port: %s, Downloader port: %s",
                          self.session1_port, self.session2.get_dispersy_port())
