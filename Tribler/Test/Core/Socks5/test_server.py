from Tribler.Core.Socks5.server import Socks5Server
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.test_as_server import AbstractServer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks


class TestSocks5Server(AbstractServer):
    """
    Test the basic functionality of the socks5 server.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestSocks5Server, self).setUp(annotate=annotate)
        self.socks5_server = Socks5Server(get_random_port(), None)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.socks5_server.stop()
        yield super(TestSocks5Server, self).tearDown(annotate=annotate)

    def test_start_server(self):
        """
        Test writing an invalid version to the socks5 server
        """
        self.socks5_server.start()
