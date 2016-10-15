import os

import shutil
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class FakeTriblerSession:

    def __init__(self, state_dir):
        self.notifier = Notifier(False)
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


class TestLibtorrentMgr(AbstractServer):

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
