from __future__ import absolute_import

from binascii import unhexlify

from nose.tools import raises

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import SOCKET_BLOCK_ERRORCODE
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


class TestSessionAsServer(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestSessionAsServer, self).setUp()
        self.called = None

    def mock_endpoints(self):
        self.session.lm.api_manager = MockObject()
        self.session.lm.api_manager.stop = lambda: None
        self.session.lm.api_manager.root_endpoint = MockObject()
        self.session.lm.api_manager.root_endpoint.events_endpoint = MockObject()
        self.session.lm.api_manager.root_endpoint.state_endpoint = MockObject()

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        self.mock_endpoints()

        expected_text = ""

        def on_tribler_exception(exception_text):
            self.assertEqual(exception_text, expected_text)

        on_tribler_exception.called = 0
        self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception = on_tribler_exception
        expected_text = "abcd"
        self.session.unhandled_error_observer({'isError': True, 'log_legacy': True, 'log_text': 'abcd'})
        expected_text = "defg"
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'defg'})

    def test_error_observer_ignored_error(self):
        """
        Testing whether some errors are ignored (like socket errors)
        """
        self.mock_endpoints()

        def on_tribler_exception(_):
            raise RuntimeError("This method cannot be called!")

        self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception = on_tribler_exception

        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 113]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 51]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 16]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 11001]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 10053]'})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'socket.error: [Errno 10054]'})
        self.session.unhandled_error_observer({'isError': True,
                                               'log_failure': 'socket.error: [Errno %s]' % SOCKET_BLOCK_ERRORCODE})
        self.session.unhandled_error_observer({'isError': True, 'log_failure': 'exceptions.ValueError: Invalid DNS-ID'})
        self.session.unhandled_error_observer({'isError': True,
                                               'log_failure': 'twisted.web._newclient.ResponseNeverReceived'})
        self.session.unhandled_error_observer({'isError': True,
                                               'log_failure': 'exceptions.RuntimeError: invalid info-hash'})

    def test_load_checkpoint(self):
        self.load_checkpoint_called = False

        def verify_load_checkpoint_call():
            self.load_checkpoint_called = True

        self.session.lm.load_checkpoint = verify_load_checkpoint_call
        self.session.load_checkpoint()
        self.assertTrue(self.load_checkpoint_called)

    @raises(OperationNotEnabledByConfigurationException)
    def test_get_libtorrent_process_not_enabled(self):
        """
        When libtorrent is not enabled, an exception should be thrown when getting the libtorrent instance.
        """
        self.session.config.get_libtorrent_enabled = lambda: False
        self.session.get_libtorrent_process()

    def test_remove_download_by_id_empty(self):
        """
        Remove downloads method when empty.
        """
        self.session.remove_download_by_id("nonexisting_infohash")
        self.assertEqual(len(self.session.get_downloads()), 0)

    def test_remove_download_by_id_nonempty(self):
        """
        Remove an existing download.
        """
        infohash = "abc"
        download = MockObject()
        torrent_def = MockObject()
        torrent_def.get_infohash = lambda: infohash
        download.get_def = lambda: torrent_def
        self.session.get_downloads = lambda: [download]

        self.called = False

        def verify_remove_download_called(*args, **kwargs):
            self.called = True

        self.session.remove_download = verify_remove_download_called
        self.session.remove_download_by_id(infohash)
        self.assertTrue(self.called)

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

    @trial_timeout(10)
    def test_remove_torrent_id(self):
        """
        Test whether removing a torrent id works.
        """
        torrent_def = TorrentDef.load(TORRENT_UBUNTU_FILE)
        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.getDestDir())

        download = self.session.start_download_from_tdef(torrent_def, download_startup_config=dcfg, hidden=True)

        # Create a deferred which forwards the unhexlified string version of the download's infohash
        download_started = download.get_handle().addCallback(lambda handle: unhexlify(str(handle.info_hash())))

        return download_started.addCallback(self.session.remove_download_by_id)
