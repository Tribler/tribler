from asyncio import sleep
from unittest.mock import Mock, call

from ipv8.test.base import TestBase

from tribler.core.socks5.connection import ConnectionState, Socks5Connection


class TestSocks5Connection(TestBase):
    """
    Tests for the Socks5Connection class.
    """

    def test_connection_made(self) -> None:
        """
        Test if the transport is updated when a connection is made.
        """
        connection = Socks5Connection(None)
        transport = Mock()

        connection.connection_made(transport)

        self.assertEqual(transport, connection.transport)

    def test_data_received_incomplete_handshake(self) -> None:
        """
        Test if the buffer is not consumed when an incomplete handshake is received.
        """
        connection = Socks5Connection(None)

        connection.data_received(b"\x05")  # Just the version

        self.assertEqual(b"\x05", connection.buffer)
        self.assertEqual(ConnectionState.BEFORE_METHOD_REQUEST, connection.state)

    def test_data_received_complete_handshake(self) -> None:
        """
        Test if the buffer is consumed and a no-authentication method is chosen when a handshake is received.
        """
        connection = Socks5Connection(None)
        connection.connection_made(Mock())

        connection.data_received(b"\x05\x01\x00")  # Version 5, 1 method(s): [0]

        self.assertEqual(b"", connection.buffer)
        self.assertEqual(ConnectionState.CONNECTED, connection.state)
        self.assertEqual(call(b"\x05\x00"), connection.transport.write.call_args)  # Version 5, no authentication

    def test_data_received_incomplete_request(self) -> None:
        """
        Test if the buffer is not consumed when an incomplete request is received.
        """
        connection = Socks5Connection(None)
        connection.connection_made(Mock())
        connection.state = ConnectionState.CONNECTED

        connection.data_received(b"\x05")  # Just the version

        self.assertEqual(b"\x05", connection.buffer)

    async def test_data_received_complete_associate_request(self) -> None:
        """
        Test if associate requests are properly responded to.
        """
        connection = Socks5Connection(Mock())
        connection.socksserver.rust_endpoint.create_udp_associate = Mock(return_value=1337)
        connection.connection_made(Mock(get_extra_info=Mock(return_value=("127.0.0.1", 1337))))
        connection.state = ConnectionState.CONNECTED

        connection.data_received(b"\x05\x03\x00\x01\x7f\x00\x00\x01\x059")  # Version 5, associate, rsv 0
        await sleep(0)

        self.assertEqual(b"", connection.buffer)
        self.assertEqual(call(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x059"),  # Version 5, succeeded, rsv 0, localhost:1337
                         connection.transport.write.call_args)

    def test_data_received_complete_bind_request(self) -> None:
        """
        Test if bind requests are properly responded to.
        """
        connection = Socks5Connection(Mock())
        connection.connection_made(Mock(get_extra_info=Mock(return_value=("127.0.0.1", 1337))))
        connection.state = ConnectionState.CONNECTED

        connection.data_received(b"\x05\x02\x00\x01\x7f\x00\x00\x01\x059")  # Version 5, bind, rsv 0, localhost:1337

        self.assertEqual(b"", connection.buffer)
        self.assertEqual(ConnectionState.PROXY_REQUEST_ACCEPTED, connection.state)
        self.assertEqual(call(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x049"),  # Version 5, succeeded, rsv 0, localhost:1081
                         connection.transport.write.call_args)

    def test_data_received_complete_connect_request(self) -> None:
        """
        Test if connect requests are properly responded to.
        """
        connection = Socks5Connection(Mock())
        connection.connection_made(Mock(get_extra_info=Mock(return_value=("127.0.0.1", 1337))))
        connection.state = ConnectionState.CONNECTED

        connection.data_received(b"\x05\x01\x00\x01\x7f\x00\x00\x01\x059")  # Version 5, connect, rsv 0, localhost:1337

        self.assertEqual(b"", connection.buffer)
        self.assertEqual(("127.0.0.1", 1337), connection.connect_to)
        self.assertEqual(call(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x049"),  # Version 5, succeeded, rsv 0, localhost:1081
                         connection.transport.write.call_args)

    def test_data_received_complete_unknown_request(self) -> None:
        """
        Test if connect requests are actively refused if the command is unknown.
        """
        connection = Socks5Connection(Mock())
        connection.connection_made(Mock(get_extra_info=Mock(return_value=("127.0.0.1", 1337))))
        connection.state = ConnectionState.CONNECTED

        connection.data_received(b"\x05\xAA\x00\x01\x7f\x00\x00\x01\x059")  # Version 5, ????

        self.assertEqual(b"", connection.buffer)
        self.assertEqual(call(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00"),  # Version 5, unsupported, rsv 0, 0.0.0.0:0
                         connection.transport.write.call_args)

    def test_connection_lost(self) -> None:
        """
        Test if the socks server is informed of connection losses.
        """
        connection = Socks5Connection(Mock())

        connection.connection_lost(None)

        self.assertEqual(call(connection), connection.socksserver.connection_lost.call_args)

    def test_close(self) -> None:
        """
        Test if the udp connection and transport are closed when the connection is closed.
        """
        connection = Socks5Connection(Mock())
        udp_connection = Mock()
        transport = Mock()
        connection.udp_connection = udp_connection
        connection.transport = transport

        connection.close("test")

        self.assertIsNone(connection.transport)
        self.assertIsNone(connection.udp_connection)
        self.assertEqual(call(), udp_connection.close.call_args)
        self.assertEqual(call(), transport.close.call_args)
