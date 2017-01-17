# see LICENSE.txt for license information

import os
from binascii import hexlify
from hashlib import sha1
from unittest import skipIf
import sys

from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.Session import Session
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestRemoteTorrentHandler(TestAsServer):
    """
    Tests the download_torrent() method of TestRemoteTorrentHandler.
    """

    def __init__(self, *argv, **kwargs):
        super(TestRemoteTorrentHandler, self).__init__(*argv, **kwargs)

        self.file_names = {}
        self.infohash_strs = {}
        self.infohashes = {}
        self.test_deferred = Deferred()
        self.config2 = None
        self.session2 = None

    def setUpPreSession(self):
        super(TestRemoteTorrentHandler, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_torrent_store(True)
        self.config.set_enable_metadata(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.session2.shutdown()
        yield super(TestRemoteTorrentHandler, self).tearDown(annotate=annotate)

    def setup_downloader(self):
        self.config2 = self.config.copy()
        self.config2.set_megacache(True)
        self.config2.set_torrent_collecting(True)
        self.config2.set_torrent_store_dir(None)
        self.config2.set_metadata_store_dir(None)
        self.config2.set_enable_metadata(True)
        self.config2.set_state_dir(self.getStateDir(2))

        self.session2 = Session(self.config2, ignore_singleton=True)
        return self.session2.start()

    @deferred(timeout=20)
    @skipIf(sys.platform == "win32", "chmod does not work on Windows")
    def test_torrent_download(self):
        """
        Testing whether downloading a torrent from another peer is successful
        """
        self._logger.info(u"Start torrent download test...")
        session1_port = self.session.get_dispersy_port()

        def start_download(_):
            candidate = Candidate(("127.0.0.1", session1_port), False)
            self.session2.lm.rtorrent_handler.download_torrent(candidate, self.infohashes[0])
            self.session2.lm.rtorrent_handler.download_torrent(candidate, self.infohashes[1],
                                                               user_callback=do_check_download)

        def do_check_download(_):
            for i, infohash_str in enumerate(self.infohash_strs):
                self._logger.info(u"Checking... %s", self.file_names[i])
                for _ in self.session2.lm.torrent_store.iterkeys():
                    self.assertTrue(infohash_str in self.session2.lm.torrent_store,
                                    u"Failed to download torrent file 1.")

            self._logger.info(u"Torrent files 1 and 2 downloaded successfully.")
            self.test_deferred.callback(None)

        # Add some torrents to the main session
        self.infohash_strs = ["41aea20908363a80d44234e8fef07fab506cd3b4", "45a647b1120ed9fe7f793e17585efb4b0efdf1a5"]

        for i, infohash in enumerate(self.infohash_strs):
            self.infohashes[i] = infohash.decode('hex')
            self.file_names[i] = file_name = u"%s.torrent" % infohash

            # Put the torrents into the uploader's store
            with open(os.path.join(TESTS_DATA_DIR, file_name), 'r') as torrent_file:
                self.session.lm.torrent_store.put(infohash, torrent_file.read())

        self.setup_downloader().addCallback(start_download)
        return self.test_deferred

    @deferred(timeout=20)
    def test_metadata_download(self):
        """
        Testing whether downloading torrent metadata from another peer is successful
        Testing whether downloading torrent metadata from another peer is successful
        """
        self._logger.info(u"Start metadata download test...")
        session1_port = self.session.get_dispersy_port()

        # Add thumbnails to the store of the second session
        thumb_file = os.path.join(unicode(TESTS_DATA_DIR), u"41aea20908363a80d44234e8fef07fab506cd3b4",
                                  u"421px-Pots_10k_100k.jpeg")
        with open(thumb_file, 'rb') as f:
            self.thumb_data = f.read()
        thumb_hash = sha1(self.thumb_data).digest()

        thumb_hash_str = hexlify(thumb_hash)
        self.session.lm.metadata_store[thumb_hash_str] = self.thumb_data

        def start_download(_):
            candidate = Candidate(("127.0.0.1", session1_port), False)
            self.session2.lm.rtorrent_handler.download_metadata(candidate, thumb_hash,
                                                                usercallback=do_check_download)

        def do_check_download(_):
            self.assertTrue(self.session2.lm.rtorrent_handler.has_metadata(thumb_hash))
            retrieved_data = self.session2.lm.rtorrent_handler.get_metadata(thumb_hash)
            self.assertEqual(retrieved_data, self.thumb_data, "metadata doesn't match")
            self.test_deferred.callback(None)

        self.setup_downloader().addCallback(start_download)
        return self.test_deferred
