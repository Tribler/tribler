from Tribler.Core.Socks5.udp_connection import SocksUDPConnection
from Tribler.Test.test_as_server import AbstractServer


class TestSocks5UDPConnection(AbstractServer):
    """
    Test the basic functionality of the socks5 UDP connection.
    """

    async def setUp(self):
        await super(TestSocks5UDPConnection, self).setUp()
        self.connection = SocksUDPConnection(None, ("1.1.1.1", 1234))
        await self.connection.open()

    async def tearDown(self):
        self.connection.close()
        await super(TestSocks5UDPConnection, self).tearDown()

    def test_datagram_received(self):
        """
        Test whether the right operations happen when a datagram is received
        """

        # We don't support IPV6 data
        self.assertFalse(self.connection.datagram_received(b'aaa\x04', ("1.1.1.1", 1234)))

        # We don't support fragmented data
        self.assertFalse(self.connection.datagram_received(b'aa\x01aaa', ("1.1.1.1", 1234)))

        # Receiving data from somewhere that is not our remote address
        self.assertFalse(self.connection.datagram_received(b'aaaaaa', ("1.2.3.4", 1234)))

        # Receiving data from an invalid destination address
        invalid_udp_packet = b'\x00\x00\x00\x03\x1etracker1.invalid-tracker\xc4\xe95\x11$\x00\x1f\x940x000'
        self.assertFalse(self.connection.datagram_received(invalid_udp_packet, ("1.1.1.1", 1234)))

    def test_send_diagram(self):
        """
        Test sending a diagram over the SOCKS5 UDP connection
        """
        self.assertTrue(self.connection.sendDatagram(b'a'))
        self.connection.remote_udp_address = None
        self.assertFalse(self.connection.sendDatagram(b'a'))
