from asyncio import get_event_loop, sleep
from binascii import unhexlify
from unittest.mock import Mock

from _socket import getaddrinfo

from anydex.core.community import MarketCommunity

from ipv8.attestation.trustchain.community import TrustChainCommunity

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_METADATA

from tribler_core.modules.libtorrent.download_manager import DownloadManager
from tribler_core.modules.libtorrent.tests.test_download_manager import create_fake_download_and_state
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
from tribler_core.modules.payout_manager import PayoutManager
from tribler_core.session import IGNORED_ERRORS
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
        mocked_endpoints = {}

        def get_endpoint_mock(name):
            if name in mocked_endpoints:
                return mocked_endpoints[name]
            endpoint = Mock()
            mocked_endpoints[name] = endpoint
            return endpoint

        self.session.api_manager.get_endpoint = get_endpoint_mock

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        self.mock_endpoints()

        mock_events = Mock()
        mock_state = Mock()
        self.session.api_manager.get_endpoint('events').on_tribler_exception = mock_events
        self.session.api_manager.get_endpoint('state').on_tribler_exception = mock_state

        # This indirect method of raising exceptions is necessary
        # to circumvent the test runner catching exceptions by itself
        def function_that_triggers_exception():
            raise Exception("foobar")

        get_event_loop().call_soon(function_that_triggers_exception)
        self.loop._run_once()
        for m in [mock_state, mock_events]:
            self.assertTrue("function_that_triggers_exception" in m.call_args[0][0])
            self.assertTrue("foobar" in m.call_args[0][0])

    async def test_error_observer_ignored_error(self):
        """
        Testing whether some errors are ignored (like socket errors)
        """
        self.mock_endpoints()

        self.session.api_manager.get_endpoint('events').on_tribler_exception = Mock()
        self.session.api_manager.get_endpoint('state').on_tribler_exception = Mock()

        def generate_exception_on_reactor(exception):

            def gen_except():
                raise exception

            get_event_loop().call_soon(gen_except)

        exceptions_list = [exc_class(errno, "exc message") for exc_class, errno in IGNORED_ERRORS.keys()]
        exceptions_list.append(RuntimeError(0, "invalid info-hash"))

        for exception in exceptions_list:
            generate_exception_on_reactor(exception)

        # Even though we could have used _run_once instead of a sleep, it seems that _run_once does not always
        # immediately clean the reactor, leading to a possibility that the test starts to shut down before the exception
        # is raised.
        await sleep(0.05)

        self.session.api_manager.get_endpoint('state').on_tribler_exception.assert_not_called()
        self.session.api_manager.get_endpoint('events').on_tribler_exception.assert_not_called()

        # This is a "canary" to test that we can handle true exceptions
        get_event_loop().call_soon(getaddrinfo, "dfdfddfd23424fdfdf", 2323)

        await sleep(0.05)

        self.session.api_manager.get_endpoint('state').on_tribler_exception.assert_not_called()
        self.session.api_manager.get_endpoint('events').on_tribler_exception.assert_not_called()

        # This is a "canary" to test to catch false negative tests
        def real_raise():
            raise Exception()

        get_event_loop().call_soon(real_raise)
        await sleep(0.05)
        self.session.api_manager.get_endpoint('state').on_tribler_exception.assert_called_once()
        self.session.api_manager.get_endpoint('events').on_tribler_exception.assert_called_once()


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
