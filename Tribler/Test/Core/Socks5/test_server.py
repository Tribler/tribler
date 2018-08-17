from Tribler.Core.Socks5.server import Socks5Server
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.test_as_server import AbstractServer
from twisted.internet.defer import inlineCallbacks


class TestSocks5Server(AbstractServer):
    """
    Test the basic functionality of the socks5 server.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestSocks5Server, self).setUp()
        self.socks5_server = Socks5Server(get_random_port(), None)

    @inlineCallbacks
    def tearDown(self):
        yield self.socks5_server.stop()
        yield super(TestSocks5Server, self).tearDown()

    def test_start_server(self):
        """
        Test writing an invalid version to the socks5 server
        """
        self.socks5_server.start()
