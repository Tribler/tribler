from binascii import unhexlify

from anydex.core.community import MarketCommunity

from ipv8.attestation.trustchain.community import TrustChainCommunity

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_METADATA

from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.libtorrent.tests.test_download_manager import create_fake_download_and_state
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
from tribler_core.modules.payout_manager import PayoutManager
from tribler_core.session import SOCKET_BLOCK_ERRORCODE
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.utilities import succeed


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

        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno 113]'})
        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno 51]'})
        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno 16]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.gaierror [Errno 11001]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.gaierror [Errno -2]'})
        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno 10053]'})
        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno 10054]'})
        self.session.unhandled_error_observer(None, {'message': 'builtins.OSError: [Errno %s]' % SOCKET_BLOCK_ERRORCODE})
        self.session.unhandled_error_observer(None, {'message': 'exceptions.RuntimeError: invalid info-hash'})


class TestSessionWithLibTorrent(TestSessionAsServer):

    def setUpPreSession(self):
        super(TestSessionWithLibTorrent, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    def temporary_directory(self, suffix=''):
        return super(TestSessionWithLibTorrent, self).temporary_directory(suffix,
                                                                          exist_ok=suffix == u'_tribler_test_session_')


class TestBootstrapSession(TestAsServer):

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['bootstrap', 'libtorrent']

        for section in config_sections:
            self.config.config[section]['enabled'] = True
        self.config.set_bootstrap_infohash("200a4aeb677a04817f1043e8d24591818c7e827c")

    @timeout(20)
    async def test_bootstrap_downloader(self):
        await self.session.start_bootstrap_download()
        await self.session.bootstrap.download.wait_for_status(DLSTATUS_METADATA, DLSTATUS_DOWNLOADING)

        infohash = self.config.get_bootstrap_infohash()
        self.assertIsNotNone(self.session.bootstrap)
        self.assertTrue(unhexlify(infohash) in self.session.dlmgr.downloads,
                        "Infohash %s Should be in downloads" % infohash)


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
        for overlay in self.session.ipv8.overlays:
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

        self.session.dlmgr = DownloadManager(self.session)

        fake_tc = MockObject()
        fake_tc.add_listener = lambda *_: None
        self.session.payout_manager = PayoutManager(fake_tc, None)

        self.session.dlmgr.initialize()
        self.session.dlmgr.state_cb_count = 4
        self.session.dlmgr.downloads = {b'aaaa': fake_download}
        await self.session.dlmgr.sesscb_states_callback([dl_state])

        self.assertTrue(self.session.payout_manager.tribler_peers)
