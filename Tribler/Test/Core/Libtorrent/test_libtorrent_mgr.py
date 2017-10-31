import binascii
import os
import shutil
import tempfile

from libtorrent import bencode
from twisted.internet.defer import inlineCallbacks, Deferred, succeed

from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.exceptions import DuplicateDownloadException, TorrentFileException, MetainfoTimeoutException
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class FakeTriblerSession:

    def __init__(self, state_dir):
        self.notifier = Notifier()
        self.state_dir = state_dir

    def get_libtorrent_utp(self):
        return True

    def get_libtorrent_proxy_settings(self):
        return (0, None, None)

    def get_anon_proxy_settings(self):
        return (2, ('127.0.0.1', [1338]), None)

    def get_listen_port(self):
        return 1337

    def get_anon_listen_port(self):
        return 1338

    def get_state_dir(self):
        return self.state_dir

    def set_listen_port_runtime(self, _):
        pass

    def get_libtorrent_max_upload_rate(self):
        return 100

    def get_libtorrent_max_download_rate(self):
        return 100


class TestLibtorrentMgr(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    LIBTORRENT_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/libtorrent/"))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestLibtorrentMgr, self).setUp(annotate)
        self.tribler_session = FakeTriblerSession(self.session_base_dir)
        self.ltmgr = LibtorrentMgr(self.tribler_session)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.ltmgr.shutdown()
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

    @deferred(timeout=20)
    def test_get_metainfo_not_ready(self):
        """
        Testing the metainfo fetching method when the DHT is not ready
        """
        self.ltmgr.schedule_metainfo_lookup = lambda *_: succeed(None)
        test_deferred = self.ltmgr.get_metainfo("a" * 20, 20)
        self.ltmgr.on_dht_ready()
        return test_deferred

    @deferred(timeout=20)
    def test_get_metainfo_cached(self):
        """
        Testing the metainfo fetching method
        """
        def verify_metainfo(metainfo):
            self.assertDictEqual(metainfo, {'abc': 'test'})

        self.ltmgr.dht_ready = True
        self.ltmgr.metainfo_cache[("a" * 20).encode('hex')] = {'abc': 'test'}
        return self.ltmgr.get_metainfo("a" * 20).addCallback(verify_metainfo)

    @deferred(timeout=20)
    def test_schedule_metainfo_existing_mt(self):
        """
        Test scheduling a metainfo lookup when there this torrent is available in the session with metadata
        """
        torrent_info = MockObject()
        torrent_info.metadata = lambda: bencode({'pieces': ['a']})

        mock_handle = MockObject()
        mock_handle.info_hash = lambda: ('a' * 20).encode('hex')
        mock_handle.is_valid = lambda: True
        mock_handle.torrent_file = lambda: torrent_info
        mock_handle.has_metadata = lambda: True

        mock_download = MockObject()
        mock_download.get_handle = lambda: succeed(mock_handle)

        self.ltmgr.torrents[('a' * 20).encode('hex')] = mock_download, None
        return self.ltmgr.schedule_metainfo_lookup('a' * 20, 30)

    @deferred(timeout=20)
    def test_schedule_metainfo_lookup(self):
        """
        Testing whether we can successfully fetch metainfo
        """
        torrent_info = MockObject()
        torrent_info.metadata = lambda: bencode({'pieces': ['a']})
        torrent_info.trackers = lambda: []

        mock_handle = MockObject()
        mock_handle.is_valid = lambda: True
        mock_handle.info_hash = lambda: ('a' * 20).encode('hex')
        mock_handle.torrent_file = lambda: torrent_info
        mock_handle.get_peer_info = lambda: []

        mock_lt_session = MockObject()
        mock_lt_session.stop_upnp = lambda: None
        mock_lt_session.save_state = lambda: None
        mock_lt_session.add_torrent = lambda _: mock_handle
        self.ltmgr.get_session = lambda *_dummy1, **_dummy2: mock_lt_session

        test_deferred = self.ltmgr.schedule_metainfo_lookup('a' * 20, 30)
        mock_download_impl = MockObject()
        mock_download_impl.process_alert = lambda *_: None
        self.ltmgr.torrents[('a' * 20).encode('hex')] = mock_download_impl, None

        self.assertIn(('a' * 20).encode('hex'), self.ltmgr.metainfo_deferreds)

        mock_alert = MockObject()
        mock_alert.handle = mock_handle
        mock_alert.__class__.__name__ = 'metadata_received_alert'
        self.ltmgr.process_alert(mock_alert)

        return test_deferred

    @deferred(timeout=20)
    def test_metainfo_timeout(self):
        """
        Test whether the timeout mechanism of the metainfo lookup is working
        """
        test_deferred = Deferred()

        mock_handle = MockObject()

        mock_lt_session = MockObject()
        mock_lt_session.stop_upnp = lambda: None
        mock_lt_session.save_state = lambda: None
        mock_lt_session.add_torrent = lambda _: mock_handle
        self.ltmgr.get_session = lambda *_dummy1, **_dummy2: mock_lt_session

        def on_timeout(failure):
            self.assertIsInstance(failure.value, MetainfoTimeoutException)
            test_deferred.callback(None)

        self.ltmgr.schedule_metainfo_lookup('a' * 20, 0.1).addErrback(on_timeout)
        return test_deferred

    def test_add_torrent(self):
        """
        Testing the addition of a torrent to the libtorrent manager
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: False

        mock_ltsession = MockObject()
        mock_ltsession.add_torrent = lambda _: mock_handle
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: []
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_dummy1, **_dummy2: mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20
        self.assertEqual(self.ltmgr.add_torrent(None, {'ti': infohash}), mock_handle)
        self.assertRaises(DuplicateDownloadException, self.ltmgr.add_torrent, None, {'ti': infohash})

    def test_add_torrent_desync(self):
        """
        Testing the addition of a torrent to the libtorrent manager, if it already exists in the session.
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: True

        mock_ltsession = MockObject()
        mock_ltsession.add_torrent = lambda _: mock_handle
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: [mock_handle]
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_dummy1, **_dummy2: mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20
        self.assertEqual(self.ltmgr.add_torrent(None, {'ti': infohash}), mock_handle)

    def test_remove_invalid_torrent(self):
        """
        Tests a successful removal status of torrents without a handle
        """
        self.ltmgr.initialize()
        mock_dl = MockObject()
        mock_dl.handle = None
        self.assertTrue(self.ltmgr.remove_torrent(mock_dl).called)

    def test_remove_invalid_handle_torrent(self):
        """
        Tests a successful removal status of torrents with an invalid handle
        """
        self.ltmgr.initialize()
        mock_handle = MockObject()
        mock_handle.is_valid = lambda: False
        mock_dl = MockObject()
        mock_dl.handle = mock_handle
        self.assertTrue(self.ltmgr.remove_torrent(mock_dl).called)

    def test_remove_unregistered_torrent(self):
        """
        Tests a successful removal status of torrents which aren't known
        """
        self.ltmgr.initialize()
        mock_handle = MockObject()
        mock_handle.is_valid = lambda: False
        alert = type('torrent_removed_alert', (object, ), dict(handle=mock_handle, info_hash='0'*20))
        self.ltmgr.process_alert(alert())

        self.assertNotIn('0'*20, self.ltmgr.torrents)

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

        self.ltmgr.trsession = self.tribler_session
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        self.assertRaises(DuplicateDownloadException, self.ltmgr.start_download, infohash='a' * 20, tdef=mock_tdef)

    def test_set_proxy_settings(self):
        """
        Test setting the proxy settings
        """
        def on_proxy_set(settings):
            self.assertTrue(settings)
            self.assertEqual(settings.hostname, 'a')
            self.assertEqual(settings.port, 1234)
            self.assertEqual(settings.username, 'abc')
            self.assertEqual(settings.password, 'def')

        mock_lt_session = MockObject()
        mock_lt_session.set_proxy = on_proxy_set
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        self.ltmgr.set_proxy_settings(mock_lt_session, 0, ('a', "1234"), ('abc', 'def'))

    def test_save_resume_preresolved_magnet(self):
        """
        Test whether a magnet link correctly writes save-resume data before it is resolved.

        This can happen when a magnet link is added when the user does not have internet.
        """
        self.ltmgr.initialize()
        self.ltmgr.trsession = self.tribler_session
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        mock_tdef = MockObject()
        mock_tdef.get_infohash = lambda: 'a' * 20

        self.tribler_session.get_download = lambda _: None
        self.tribler_session.get_downloads_pstate_dir = lambda: self.ltmgr.metadata_tmpdir

        mock_lm = MockObject()
        mock_lm.ltmgr = self.ltmgr
        mock_lm.tunnel_community = None
        self.tribler_session.lm = mock_lm

        def dl_from_tdef(tdef, _):
            dl = LibtorrentDownloadImpl(self.tribler_session, tdef)
            dl.setup()
            dl.cancel_all_pending_tasks()
            return dl
        self.tribler_session.start_download_from_tdef = dl_from_tdef

        download = self.ltmgr.start_download_from_magnet("magnet:?xt=urn:btih:" + ('1'*40))

        basename = binascii.hexlify(download.get_def().get_infohash()) + '.state'
        filename = os.path.join(download.session.get_downloads_pstate_dir(), basename)

        self.assertTrue(os.path.isfile(filename))

    def test_get_cached_metainfo(self):
        """
        Test whether cached metainfo is returned by the libtorrent manager
        """
        self.assertIsNone(self.ltmgr._get_cached_metainfo('a' * 20))
        self.ltmgr._add_cached_metainfo('a' * 20, {'abc': 'def'})
        self.assertDictEqual(self.ltmgr._get_cached_metainfo('a' * 20), {'abc': 'def'})
