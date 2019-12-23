from asyncio import Future
from binascii import unhexlify

from anydex.core.community import MarketCommunity

from ipv8.attestation.trustchain.community import TrustChainCommunity

from nose.tools import raises

from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Core.Session import SOCKET_BLOCK_ERRORCODE
from Tribler.Core.Utilities.utilities import succeed
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import DLSTATUS_METADATA
from Tribler.Test.Core.Libtorrent.test_libtorrent_mgr import create_fake_download_and_state
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout
from Tribler.community.gigachannel.community import GigaChannelCommunity

from TriblerGUI.defs import DLSTATUS_DOWNLOADING


class TestSessionAsServer(TestAsServer):

    async def setUp(self):
        await super(TestSessionAsServer, self).setUp()
        self.called = None

    def mock_endpoints(self):
        self.session.api_manager = MockObject()
        self.session.api_manager.stop = lambda: succeed(None)
        endpoint = MockObject()
        self.session.api_manager.get_endpoint = lambda _: endpoint

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        self.mock_endpoints()

        expected_text = ""

        def on_tribler_exception(exception_text):
            self.assertEqual(exception_text, expected_text)

        on_tribler_exception.called = 0
        self.session.api_manager.get_endpoint('events').on_tribler_exception = on_tribler_exception
        self.session.api_manager.get_endpoint('state').on_tribler_exception = on_tribler_exception
        expected_text = "abcd"
        self.session.unhandled_error_observer(None, {'message': 'abcd'})

    def test_error_observer_ignored_error(self):
        """
        Testing whether some errors are ignored (like socket errors)
        """
        self.mock_endpoints()

        def on_tribler_exception(_):
            raise RuntimeError("This method cannot be called!")

        self.session.api_manager.get_endpoint('events').on_tribler_exception = on_tribler_exception
        self.session.api_manager.get_endpoint('state').on_tribler_exception = on_tribler_exception

        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 113]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 51]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 16]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 11001]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 10053]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 10054]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno %s]' % SOCKET_BLOCK_ERRORCODE})
        self.session.unhandled_error_observer(None, {'message': 'exceptions.RuntimeError: invalid info-hash'})

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_ipv8_instance(self):
        """
        Test whether the get IPv8 instance throws an exception if IPv8 is not enabled.
        """
        self.session.config.set_ipv8_enabled(False)
        self.session.get_ipv8_instance()


class TestSessionWithLibTorrent(TestSessionAsServer):

    def setUpPreSession(self):
        super(TestSessionWithLibTorrent, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    def temporary_directory(self, suffix=''):
        return super(TestSessionWithLibTorrent, self).temporary_directory(suffix,
                                                                          exist_ok=suffix == u'_tribler_test_session_')


class TestBootstrapSession(TestAsServer):

    async def setUp(self):
        await super(TestBootstrapSession, self).setUp()
        self.test_future = Future()

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['bootstrap', 'libtorrent']

        for section in config_sections:
            self.config.config[section]['enabled'] = True
        self.config.set_bootstrap_infohash("200a4aeb677a04817f1043e8d24591818c7e827c")

    def downloader_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_METADATA or ds.get_status() == DLSTATUS_DOWNLOADING:
            self.test_future.set_result(None)
            return 0.0
        return 0.5

    @timeout(20)
    async def test_bootstrap_downloader(self):
        self.session.start_bootstrap_download()
        self.session.bootstrap.download.set_state_callback(self.downloader_state_callback)

        infohash = self.config.get_bootstrap_infohash()
        self.assertIsNotNone(self.session.bootstrap)
        self.assertTrue(unhexlify(infohash) in self.session.ltmgr.downloads,
                        "Infohash %s Should be in downloads" % infohash)
        await self.test_future


class TestLaunchFullSession(TestAsServer):

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['trustchain', 'tunnel_community', 'ipv8', 'dht', 'chant', 'market_community']

        for section in config_sections:
            self.config.config[section]['enabled'] = True

        self.config.set_tunnel_community_socks5_listen_ports(self.get_ports(5))
        self.config.set_ipv8_bootstrap_override("127.0.0.1:12345")  # So we do not contact the real trackers

    def get_community(self, overlay_cls):
        for overlay in self.session.get_ipv8_instance().overlays:
            if isinstance(overlay, overlay_cls):
                return overlay

    def test_load_communities(self):
        """
        Testing whether all IPv8 communities can be succesfully loaded
        """
        self.assertTrue(self.get_community(GigaChannelCommunity))
        self.assertTrue(self.get_community(MarketCommunity))
        self.assertTrue(self.get_community(TrustChainCommunity))

    async def test_update_payout_balance(self):
        """
        Test whether the balance of peers is correctly updated
        """
        fake_download, dl_state = create_fake_download_and_state()
        dl_state.get_status = lambda: DLSTATUS_DOWNLOADING

        self.session.ltmgr = LibtorrentMgr(self.session)

        fake_tc = MockObject()
        fake_tc.add_listener = lambda *_: None
        self.session.payout_manager = PayoutManager(fake_tc, None)

        self.session.ltmgr.state_cb_count = 4
        self.session.ltmgr.downloads = {b'aaaa': fake_download}
        await self.session.ltmgr.sesscb_states_callback([dl_state])

        self.assertTrue(self.session.payout_manager.tribler_peers)
