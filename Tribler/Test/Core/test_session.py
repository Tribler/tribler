from binascii import unhexlify

from nose.tools import raises

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Session import SOCKET_BLOCK_ERRORCODE
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import succeed
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


class TestSessionAsServer(TestAsServer):

    async def setUp(self):
        await super(TestSessionAsServer, self).setUp()
        self.called = None

    def mock_endpoints(self):
        self.session.lm.api_manager = MockObject()
        self.session.lm.api_manager.stop = lambda: succeed(None)
        endpoint = MockObject()
        self.session.lm.api_manager.get_endpoint = lambda _: endpoint

    def test_unhandled_error_observer(self):
        """
        Test the unhandled error observer
        """
        self.mock_endpoints()

        expected_text = ""

        def on_tribler_exception(exception_text):
            self.assertEqual(exception_text, expected_text)

        on_tribler_exception.called = 0
        self.session.lm.api_manager.get_endpoint('events').on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.get_endpoint('state').on_tribler_exception = on_tribler_exception
        expected_text = "abcd"
        self.session.unhandled_error_observer(None, {'message': 'abcd'})

    def test_error_observer_ignored_error(self):
        """
        Testing whether some errors are ignored (like socket errors)
        """
        self.mock_endpoints()

        def on_tribler_exception(_):
            raise RuntimeError("This method cannot be called!")

        self.session.lm.api_manager.get_endpoint('events').on_tribler_exception = on_tribler_exception
        self.session.lm.api_manager.get_endpoint('state').on_tribler_exception = on_tribler_exception

        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 113]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 51]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 16]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 11001]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 10053]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno 10054]'})
        self.session.unhandled_error_observer(None, {'message': 'socket.error: [Errno %s]' % SOCKET_BLOCK_ERRORCODE})
        self.session.unhandled_error_observer(None, {'message': 'exceptions.RuntimeError: invalid info-hash'})

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

    def temporary_directory(self, suffix=''):
        return super(TestSessionWithLibTorrent, self).temporary_directory(suffix,
                                                                          exist_ok=suffix == u'_tribler_test_session_')

    @timeout(10)
    async def test_remove_torrent_id(self):
        """
        Test whether removing a torrent id works.
        """
        torrent_def = TorrentDef.load(TORRENT_UBUNTU_FILE)
        dcfg = DownloadConfig()
        dcfg.set_dest_dir(self.getDestDir())

        download = self.session.start_download_from_tdef(torrent_def, download_config=dcfg, hidden=True)

        # Create a deferred which forwards the unhexlified string version of the download's infohash
        handle = await download.get_handle()
        await self.session.remove_download_by_id(unhexlify(str(handle.info_hash())))
