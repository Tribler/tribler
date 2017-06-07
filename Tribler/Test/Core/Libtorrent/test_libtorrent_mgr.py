import os
import shutil
import tempfile
from libtorrent import bencode
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.exceptions import DuplicateDownloadException, TorrentFileException
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestLibtorrentMgr(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    LIBTORRENT_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/libtorrent/"))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestLibtorrentMgr, self).setUp(annotate)

        self.tribler_session = MockObject()
        self.tribler_session.notifier = Notifier()
        self.tribler_session.state_dir = self.session_base_dir

        self.tribler_session.config = MockObject()
        self.tribler_session.config.get_libtorrent_utp = lambda: True
        self.tribler_session.config.get_libtorrent_proxy_settings = lambda: (0, None, None)
        self.tribler_session.config.get_anon_proxy_settings = lambda: (2, ('127.0.0.1', [1338]), None)
        self.tribler_session.config.get_libtorrent_port = lambda: 1337
        self.tribler_session.config.get_anon_listen_port = lambda: 1338
        self.tribler_session.config.get_state_dir = lambda: self.session_base_dir
        self.tribler_session.config.set_listen_port_runtime = lambda: None
        self.tribler_session.config.get_libtorrent_max_upload_rate = lambda: 100
        self.tribler_session.config.get_libtorrent_max_download_rate = lambda: 120

        self.ltmgr = LibtorrentMgr(self.tribler_session)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.ltmgr.shutdown()
        self.assertTrue(os.path.exists(os.path.join(self.session_base_dir, 'lt.state')))
        yield super(TestLibtorrentMgr, self).tearDown(annotate)

    def test_get_session_zero_hops(self):
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_one_hop(self):
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(1)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_corrupt_lt_state(self):
        file = open(os.path.join(self.session_base_dir, 'lt.state'), "w")
        file.write("Lorem ipsum")
        file.close()

        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_session_zero_hops_working_lt_state(self):
        shutil.copy(os.path.join(self.LIBTORRENT_FILES_DIR, 'lt.state'),
                    os.path.join(self.session_base_dir, 'lt.state'))
        self.ltmgr.initialize()
        ltsession = self.ltmgr.get_session(0)
        self.assertTrue(ltsession)

    def test_get_metainfo_not_ready(self):
        """
        Testing the metainfo fetching method when the DHT is not ready
        """
        self.ltmgr.initialize()
        self.assertFalse(self.ltmgr.get_metainfo("a" * 20, None))

    @deferred(timeout=20)
    def test_get_metainfo(self):
        """
        Testing the metainfo fetching method
        """
        test_deferred = Deferred()

        def metainfo_cb(metainfo):
            self.assertEqual(metainfo, "test")
            test_deferred.callback(None)

        self.ltmgr.initialize()
        self.ltmgr.is_dht_ready = lambda: True
        self.ltmgr.metainfo_cache[("a" * 20).encode('hex')] = {'meta_info': 'test'}
        self.ltmgr.get_metainfo("a" * 20, metainfo_cb)

        return test_deferred

    @deferred(timeout=20)
    def test_got_metainfo(self):
        """
        Testing whether the callback is correctly invoked when we received metainfo
        """
        test_deferred = Deferred()
        self.ltmgr.initialize()

        def metainfo_cb(metainfo):
            self.assertDictEqual(metainfo, {'info': {'pieces': ['a']}, 'leechers': 0,
                                            'nodes': [], 'seeders': 0, 'initial peers': []})
            test_deferred.callback(None)

        fake_handle = MockObject()
        torrent_info = MockObject()
        torrent_info.metadata = lambda: bencode({'pieces': ['a']})
        torrent_info.trackers = lambda: []
        fake_handle.get_peer_info = lambda: []
        fake_handle.torrent_file = lambda: torrent_info

        self.ltmgr.get_session().remove_torrent = lambda *_: None

        self.ltmgr.metainfo_requests['a' * 20] = {
            'handle': fake_handle,
            'timeout_callbacks': [],
            'callbacks': [metainfo_cb],
            'notify': False
        }
        self.ltmgr.got_metainfo("a" * 20)

        return test_deferred

    @deferred(timeout=20)
    def test_got_metainfo_timeout(self):
        """
        Testing whether the callback is correctly invoked when we received metainfo after timeout
        """
        test_deferred = Deferred()

        def metainfo_timeout_cb(metainfo):
            self.assertEqual(metainfo, 'a' * 20)
            test_deferred.callback(None)

        fake_handle = MockObject()

        self.ltmgr.initialize()
        self.ltmgr.metainfo_requests[('a' * 20).encode('hex')] = {'handle': fake_handle,
                                                                  'timeout_callbacks': [metainfo_timeout_cb],
                                                                  'callbacks': [],
                                                                  'notify': True}
        self.ltmgr.get_session().remove_torrent = lambda _dummy1, _dummy2: None
        self.ltmgr.got_metainfo(('a' * 20).encode('hex'), timeout=True)

        return test_deferred

    def test_add_torrent(self):
        """
        Testing the addition of a torrent to the libtorrent manager
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20

        mock_ltsession = MockObject()
        mock_ltsession.add_torrent = lambda _: mock_handle
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_: mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20
        self.assertEqual(self.ltmgr.add_torrent(None, {'ti': infohash}), mock_handle)
        self.assertRaises(DuplicateDownloadException, self.ltmgr.add_torrent, None, {'ti': infohash})

    def test_start_download_corrupt(self):
        """
        Testing whether starting the download of a corrupt torrent file raises an exception
        """
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        corrupt_file = os.path.join(self.LIBTORRENT_FILES_DIR, 'corrupt_torrent.torrent')
        self.assertRaises(TorrentFileException, self.ltmgr.start_download, torrentfilename=corrupt_file)

    def test_start_download_duplicate(self):
        """
        Test the starting of a download when there are no new trackers
        """
        mock_tdef = MockObject()
        mock_tdef.get_infohash = lambda: 'a' * 20
        mock_tdef.get_trackers_as_single_tuple = lambda: tuple()

        mock_download = MockObject()
        mock_download.get_def = lambda: mock_tdef
        self.tribler_session.get_download = lambda _: mock_download

        self.ltmgr.tribler_session = self.tribler_session
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        self.assertRaises(DuplicateDownloadException, self.ltmgr.start_download, infohash='a' * 20, tdef=mock_tdef)
