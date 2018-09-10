import binascii
import os
import shutil
import tempfile

from libtorrent import bencode
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet import reactor

from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.exceptions import TorrentFileException
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestLibtorrentMgr(AbstractServer):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    LIBTORRENT_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/libtorrent/"))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestLibtorrentMgr, self).setUp(annotate)

        self.tribler_session = MockObject()
        self.tribler_session.lm = MockObject()
        self.tribler_session.notifier = Notifier()
        self.tribler_session.state_dir = self.session_base_dir
        self.tribler_session.trustchain_keypair = MockObject()
        self.tribler_session.trustchain_keypair.key_to_hash = lambda: 'a' * 20

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
        self.tribler_session.config.get_libtorrent_dht_enabled = lambda: False
        self.tribler_session.config.set_libtorrent_port_runtime = lambda _: None

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
            self.assertEqual(metainfo, {'info': {'pieces': ['a']}, 'leechers': 0,
                                        'nodes': [], 'seeders': 0, 'initial peers': []})
            test_deferred.callback(None)

        infohash = "a" * 20

        self.ltmgr.initialize()

        torrent_info = MockObject()
        torrent_info.metadata = lambda: bencode({'pieces': ['a']})
        torrent_info.trackers = lambda: []

        fake_handle = MockObject()
        fake_handle.is_valid = lambda: True
        fake_handle.has_metadata = lambda: True
        fake_handle.get_peer_info = lambda: []
        fake_handle.torrent_file = lambda: torrent_info
        self.ltmgr.ltsession_metainfo.add_torrent = lambda *_: fake_handle
        self.ltmgr.ltsession_metainfo.remove_torrent = lambda *_: None

        fake_alert = type('lt.metadata_received_alert', (object,), dict(handle=fake_handle))
        self.ltmgr.ltsession_metainfo.pop_alerts = lambda: [fake_alert]

        self.ltmgr.is_dht_ready = lambda: True
        self.ltmgr.get_metainfo(infohash.decode('hex'), metainfo_cb)

        return test_deferred

    @deferred(timeout=20)
    def test_get_metainfo_cache(self):
        """
        Testing metainfo caching
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

        self.ltmgr.ltsession_metainfo.remove_torrent = lambda *_: None

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
        self.ltmgr.ltsession_metainfo.remove_torrent = lambda _dummy1, _dummy2: None
        self.ltmgr.got_metainfo(('a' * 20).encode('hex'), timeout=True)

        return test_deferred

    @deferred(timeout=20)
    def test_get_metainfo_with_already_added_torrent(self):
        """
        Testing metainfo fetching for a torrent which is already in session.
        got_metainfo() should be called with timeout=False.
        """
        magnet_link = "magnet:?xt=urn:btih:f72636475a375653083e49d501601675ce3e6619&dn=ubuntu-16.04.3-server-i386.iso"

        test_deferred = Deferred()

        def fake_got_metainfo(_, timeout):
            self.assertFalse(timeout, "Timeout should not be True")
            test_deferred.callback(None)

        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: True
        mock_handle.has_metadata = lambda: True

        mock_ltsession = MockObject()
        mock_ltsession.add_torrent = lambda _: mock_handle
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: []
        mock_ltsession.start_upnp = lambda: None
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.ltsession_metainfo = mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        self.ltmgr.is_dht_ready = lambda: True
        self.ltmgr.got_metainfo = fake_got_metainfo

        self.ltmgr.get_metainfo(magnet_link, lambda _: None)
        return test_deferred

    @deferred(timeout=20)
    def test_add_torrent(self):
        """
        Testing the addition of a torrent to the libtorrent manager
        """
        test_deferred = Deferred()

        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: False

        mock_error = MockObject()
        mock_error.value = lambda: None

        mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle, error=mock_error))()

        mock_ltsession = MockObject()
        mock_ltsession.async_add_torrent = lambda _: reactor.callLater(0.1, self.ltmgr.process_alert, mock_alert)
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: []
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_: mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20

        mock_download = MockObject()
        mock_download.deferred_added = Deferred()

        def cb_torrent_added(handle):
            self.assertEqual(handle, mock_handle)
            test_deferred.callback(None)

        self.ltmgr.add_torrent(mock_download, {'ti': infohash}).addCallback(cb_torrent_added)

        return test_deferred

    @deferred(timeout=20)
    def test_add_torrent_desync(self):
        """
        Testing the addition of a torrent to the libtorrent manager, if it already exists in the session.
        """
        mock_handle = MockObject()
        mock_handle.info_hash = lambda: 'a' * 20
        mock_handle.is_valid = lambda: True

        mock_alert = type('add_torrent_alert', (object,), dict(handle=mock_handle))

        mock_ltsession = MockObject()
        mock_ltsession.async_add_torrent = lambda _: self.ltmgr.process_alert(mock_alert)
        mock_ltsession.find_torrent = lambda _: mock_handle
        mock_ltsession.get_torrents = lambda: [mock_handle]
        mock_ltsession.stop_upnp = lambda: None
        mock_ltsession.save_state = lambda: None

        self.ltmgr.get_session = lambda *_: mock_ltsession
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')

        infohash = MockObject()
        infohash.info_hash = lambda: 'a' * 20

        mock_download = MockObject()
        mock_download.deferred_added = Deferred()
        return self.ltmgr.add_torrent(mock_download, {'ti': infohash}).addCallback(
            lambda handle: self.assertEqual(handle, mock_handle)
        )

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
        mock_download.get_credit_mining = lambda: False
        self.tribler_session.get_download = lambda _: mock_download
        self.tribler_session.start_download_from_tdef = lambda tdef, _: MockObject()

        self.ltmgr.tribler_session = self.tribler_session
        self.ltmgr.metadata_tmpdir = tempfile.mkdtemp(suffix=u'tribler_metainfo_tmpdir')
        self.ltmgr.start_download(infohash='a' * 20, tdef=mock_tdef)

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

        def on_set_settings(settings):
            self.assertTrue(settings)
            self.assertEqual(settings['proxy_hostname'], 'a')
            self.assertEqual(settings['proxy_port'], 1234)
            self.assertEqual(settings['proxy_username'], 'abc')
            self.assertEqual(settings['proxy_password'], 'def')
            self.assertEqual(settings['proxy_peer_connections'], True)
            self.assertEqual(settings['proxy_hostnames'], True)

        mock_lt_session = MockObject()
        mock_lt_session.get_settings = lambda: {}
        mock_lt_session.set_settings = on_set_settings
        mock_lt_session.set_proxy = on_proxy_set  # Libtorrent < 1.1.0 uses set_proxy to set proxy settings
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

    @deferred(timeout=5)
    def test_callback_on_alert(self):
        """
        Test whether the alert callback is called when a libtorrent alert is posted
        """
        self.ltmgr.default_alert_mask = 0xffffffff
        test_deferred = Deferred()

        def callback(*args):
            self.ltmgr.alert_callback = None
            test_deferred.callback(None)

        callback.called = False
        self.ltmgr.alert_callback = callback
        self.ltmgr.initialize()
        self.ltmgr._task_process_alerts()
        return test_deferred

    def test_payout_on_disconnect(self):
        """
        Test whether a payout is initialized when a peer disconnects
        """
        class peer_disconnected_alert(object):
            def __init__(self):
                self.pid = MockObject()
                self.pid.to_string = lambda: 'a' * 20

        def mocked_do_payout(mid):
            self.assertEqual(mid, 'a' * 20)
            mocked_do_payout.called = True
        mocked_do_payout.called = False

        disconnect_alert = peer_disconnected_alert()
        self.ltmgr.tribler_session.lm.payout_manager = MockObject()
        self.ltmgr.tribler_session.lm.payout_manager.do_payout = mocked_do_payout
        self.ltmgr.initialize()
        self.ltmgr.get_session(0).pop_alerts = lambda: [disconnect_alert]
        self.ltmgr._task_process_alerts()

        self.assertTrue(mocked_do_payout.called)
