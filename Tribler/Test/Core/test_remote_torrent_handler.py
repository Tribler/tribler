from twisted.internet.defer import inlineCallbacks

from Tribler.Core.RemoteTorrentHandler import TftpRequester, RemoteTorrentHandler
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestTftpRequester(TriblerCoreTest):
    """
    This class contains tests for the TFTP requester.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestTftpRequester, self).setUp(annotate=annotate)
        self.mock_session = MockObject()
        self.remote_torrent_handler = RemoteTorrentHandler(self.mock_session)
        self.remote_torrent_handler.running = True
        self.tftp_requester = TftpRequester('test', self.mock_session, self.remote_torrent_handler, 1)

    def test_download_successful_invalid(self):
        """
        Test the callback when a download from a remote peer has finished (with an invalid torrent)
        """
        extra_info = {u'key': 'a' * 20, u'info_hash': 'a' * 20}
        self.tftp_requester._active_request_list.append('a' * 20)
        self.tftp_requester._untried_sources['a' * 20] = 'test'
        self.tftp_requester._tried_sources['a' * 20] = 'test'
        self.tftp_requester._on_download_successful('192.168.1.1', 'test.txt', 'a' * 20, extra_info)
