from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Socks5.udp_connection import SocksUDPConnection
from Tribler.Test.test_as_server import AbstractServer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestSocks5UDPConnection(AbstractServer):
    """
    Test the basic functionality of the socks5 UDP connection.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestSocks5UDPConnection, self).setUp(annotate=annotate)

        self.connection = SocksUDPConnection(None, ("1.1.1.1", 1234))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.connection.close()
        yield super(TestSocks5UDPConnection, self).tearDown(annotate=annotate)

    def test_datagram_received(self):
        """
        Test whether the right operations happen when a datagram is received
        """

        # We don't support IPV6 data
        self.assertFalse(self.connection.datagramReceived('aaa\x04', ("1.1.1.1", 1234)))

        # We don't support fragmented data
        self.assertFalse(self.connection.datagramReceived('aa\x01aaa', ("1.1.1.1", 1234)))

        # Receiving data from somewhere that is not our remote address
        self.assertFalse(self.connection.datagramReceived('aaaaaa', ("1.2.3.4", 1234)))

    def test_send_diagram(self):
        """
        Test sending a diagram over the SOCKS5 UDP connection
        """
        self.assertTrue(self.connection.sendDatagram('a'))
        self.connection.remote_udp_address = None
        self.assertFalse(self.connection.sendDatagram('a'))
