from twisted.internet.defer import inlineCallbacks

from nose.tools import raises
from nose.twistedtools import deferred

from Tribler.Core.TFTP.exception import FileNotFound
from Tribler.Core.TFTP.handler import TftpHandler
from Tribler.Core.TFTP.packet import OPCODE_OACK, OPCODE_ERROR
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTFTPHandler(TriblerCoreTest):
    """
    This class contains tests for the TFTP handler class.
    """

    def setUp(self, annotate=True):
        TriblerCoreTest.setUp(self, annotate=annotate)
        self.handler = TftpHandler(None, None, None)

    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield TriblerCoreTest.tearDown(self, annotate=annotate)
        self.handler.cancel_all_pending_tasks()

    @deferred(timeout=10)
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_download_file_not_running(self):
        """
        Testing whether we do nothing if we are not running a session
        """
        def mocked_add_new_session(_):
            raise RuntimeError("_add_new_session not be called")

        self.handler._add_new_session = mocked_add_new_session
        yield self.handler.download_file("test", "127.0.0.1", 1234)

    @deferred(timeout=5)
    @inlineCallbacks
    def test_check_session_timeout(self):
        """
        Testing whether we fail if we exceed our maximum amount of retries
        """
        mock_session = MockObject()
        mock_session.retries = 2
        mock_session.timeout = 1
        mock_session.last_contact_time = 2
        self.handler._max_retries = 1
        timedout = yield self.handler._check_session_timeout(mock_session)
        self.assertTrue(timedout)

    def test_schedule_callback_processing(self):
        """
        Testing whether we do not register a tftp process task again
        """
        self.assertFalse(self.handler.is_pending_task_active("tftp_process_callback"))
        self.handler._schedule_callback_processing()
        self.assertTrue(self.handler._callback_scheduled)
        self.handler.cancel_all_pending_tasks()
        self.handler._schedule_callback_processing()
        self.assertFalse(self.handler.is_pending_task_active("tftp_process_callback"))

    def test_cleanup_session(self):
        """
        Testing whether a tftp session is correctly cleaned up
        """
        self.handler._session_id_dict["c"] = 1
        self.handler._session_dict = {"abc": "test"}
        self.handler._cleanup_session("abc")
        self.assertFalse('c' in self.handler._session_id_dict)

    @deferred(timeout=10)
    @inlineCallbacks
    def test_data_came_in(self):
        """
        Testing whether we do nothing when data comes in and the handler is not running
        """
        def mocked_process_packet(_dummy1, _dummy2):
            raise RuntimeError("_process_packet may not be called")

        self.handler._process_packet = mocked_process_packet
        self.handler._is_running = False
        yield self.handler.data_came_in(None, None)

    @raises(FileNotFound)
    def test_load_metadata_not_found(self):
        """
        Testing whether a FileNotFound exception is raised when metadata cannot be found
        """
        self.handler.session = MockObject()
        self.handler.session.lm = MockObject()
        self.handler.session.lm.metadata_store = MockObject()
        self.handler.session.lm.metadata_store.get = lambda _: None
        self.handler._load_metadata("abc")

    @raises(FileNotFound)
    def test_load_torrent_not_found(self):
        """
        Testing whether a FileNotFound exception is raised when a torrent cannot be found
        """
        self.handler.session = MockObject()
        self.handler.session.lm = MockObject()
        self.handler.session.lm.torrent_store = MockObject()
        self.handler.session.lm.torrent_store.get = lambda _: None
        self.handler._load_torrent("abc")

    @deferred(timeout=10)
    @inlineCallbacks
    def test_handle_packet_as_receiver(self):
        """
        Testing the handle_packet_as_receiver method
        """
        def mocked_handle_error(_dummy1, _dummy2, error_msg=None):
            mocked_handle_error.called = True

        mocked_handle_error.called = False
        self.handler._handle_error = mocked_handle_error

        mock_session = MockObject()
        mock_session.last_received_packet = None
        mock_session.block_size = 42
        mock_session.timeout = 44
        packet = {'opcode': OPCODE_OACK, 'options': {'blksize': 43, 'timeout': 45}}
        yield self.handler._handle_packet_as_receiver(mock_session, packet)
        self.assertTrue(mocked_handle_error.called)

        mocked_handle_error.called = False
        packet['options']['blksize'] = 42
        yield self.handler._handle_packet_as_receiver(mock_session, packet)
        self.assertTrue(mocked_handle_error.called)

        mock_session.last_received_packet = True
        mocked_handle_error.called = False
        yield self.handler._handle_packet_as_receiver(mock_session, packet)
        self.assertTrue(mocked_handle_error.called)

        packet['options']['timeout'] = 44
        packet['opcode'] = OPCODE_ERROR
        mocked_handle_error.called = False
        yield self.handler._handle_packet_as_receiver(mock_session, packet)
        self.assertTrue(mocked_handle_error.called)

    @deferred(timeout=10)
    @inlineCallbacks
    def test_handle_packet_as_sender(self):
        """
        Testing the handle_packet_as_sender method
        """
        def mocked_handle_error(_dummy1, _dummy2, error_msg=None):
            mocked_handle_error.called = True

        mocked_handle_error.called = False
        self.handler._handle_error = mocked_handle_error

        packet = {'opcode': OPCODE_ERROR}
        yield self.handler._handle_packet_as_sender(None, packet)
        self.assertTrue(mocked_handle_error.called)

    @deferred(timeout=10)
    @inlineCallbacks
    def test_handle_error(self):
        """
        Testing the error handling of a tftp handler
        """
        mock_session = MockObject()
        mock_session.is_failed = False
        self.handler._send_error_packet = lambda _dummy1, _dummy2, _dummy3: None
        yield self.handler._handle_error(mock_session, None)
        self.assertTrue(mock_session.is_failed)

    def test_send_error_packet(self):
        """
        Testing whether a correct error message is sent in the tftp handler
        """
        def mocked_send_packet(_, packet):
            self.assertEqual(packet['session_id'], 42)
            self.assertEqual(packet['error_code'], 43)
            self.assertEqual(packet['error_msg'], "test")

        self.handler._send_packet = mocked_send_packet
        mock_session = MockObject()
        mock_session.session_id = 42
        self.handler._send_error_packet(mock_session, 43, "test")
