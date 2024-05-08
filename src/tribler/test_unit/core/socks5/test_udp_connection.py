from asyncio import get_event_loop
from unittest.mock import AsyncMock, Mock, call, patch

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress
from ipv8.test.base import TestBase

from tribler.core.socks5.udp_connection import RustUDPConnection, SocksUDPConnection


class MockSocksUDPConnection(SocksUDPConnection):
    """
    A SocksUDPConnection with a mocked open method.
    """

    async def open(self) -> None:
        """
        Fake opening a transport.
        """
        self.transport = Mock()


class TestSocksUDPConnection(TestBase):
    """
    Tests for the SocksUDPConnection class.
    """

    async def test_open(self) -> None:
        """
        Test if opening a connection binds on 0.0.0.0:0.
        """
        callback = AsyncMock(return_value=(Mock(), None))
        connection = SocksUDPConnection(None, None)

        with patch.object(get_event_loop(), "create_datagram_endpoint", callback):
            await connection.open()

        self.assertEqual(("127.0.0.1", 0), callback.call_args.kwargs["local_addr"])

    async def test_get_listen_port(self) -> None:
        """
        Test if the listen port is determined from the transport address.
        """
        connection = MockSocksUDPConnection(None, None)
        await connection.open()
        connection.transport.get_extra_info = Mock(return_value=("0.0.0.0", 42))

        self.assertEqual(42, connection.get_listen_port())

    async def test_send_without_remote(self) -> None:
        """
        Test if data cannot be sent without a udp address.
        """
        connection = MockSocksUDPConnection(None, None)
        await connection.open()

        self.assertFalse(connection.send_datagram(b"test"))

    async def test_send_with_remote(self) -> None:
        """
        Test if data is sent to the registered udp address.
        """
        connection = MockSocksUDPConnection(None, ("localhost", 1337))
        await connection.open()

        self.assertTrue(connection.send_datagram(b"test"))
        self.assertEqual(call(b"test", ("localhost", 1337)), connection.transport.sendto.call_args)

    async def test_datagram_received_first(self) -> None:
        """
        Test if the first received data updates the remote properly.
        """
        socks_connection = Mock()
        socks_connection.socksserver.output_stream.on_socks5_udp_data = Mock(return_value=True)
        connection = MockSocksUDPConnection(socks_connection, None)
        await connection.open()

        value = connection.cb_datagram_received(b"\x00\x00\x00\x03\tlocalhost\x0590x000", ("localhost", 1337))
        udp_payload = socks_connection.socksserver.output_stream.on_socks5_udp_data.call_args.args[1]

        self.assertTrue(value)
        self.assertEqual(("localhost", 1337), connection.remote_udp_address)
        self.assertEqual(0, udp_payload.rsv)
        self.assertEqual(0, udp_payload.frag)
        self.assertEqual(DomainAddress(host="localhost", port=1337), udp_payload.destination)
        self.assertEqual(b"0x000", udp_payload.data)

    async def test_datagram_received_wrong_source(self) -> None:
        """
        Test if packets are dropped if they don't come from the remote.
        """
        socks_connection = Mock()
        connection = MockSocksUDPConnection(socks_connection, ("localhost", 1337))
        await connection.open()

        value = connection.cb_datagram_received(b"\x00\x00\x00\x03\tlocalhost\x0590x000", ("notlocalhost", 1337))

        self.assertFalse(value)

    async def test_datagram_received_garbage(self) -> None:
        """
        Test if packets are dropped if they don't contain valid UDP packets.
        """
        socks_connection = Mock()
        connection = MockSocksUDPConnection(socks_connection, ("localhost", 1337))
        await connection.open()

        value = connection.cb_datagram_received(b"\x00", ("localhost", 1337))

        self.assertFalse(value)

    async def test_datagram_received_fragmented(self) -> None:
        """
        Test if packets are dropped if they are fragmented.
        """
        socks_connection = Mock()
        connection = MockSocksUDPConnection(socks_connection, ("localhost", 1337))
        await connection.open()

        value = connection.cb_datagram_received(b"\x00\x00\x01\x03\tlocalhost\x0590x000", ("localhost", 1337))

        self.assertFalse(value)

    async def test_datagram_received_no_destination(self) -> None:
        """
        Test if packets are dropped if they don't specify a destination.
        """
        socks_connection = Mock()
        connection = MockSocksUDPConnection(socks_connection, ("localhost", 1337))
        await connection.open()
        transport = connection.transport

        connection.close()

        self.assertEqual(call(), transport.close.call_args)
        self.assertIsNone(connection.transport)

    async def test_open_rust_endpoint(self) -> None:
        """
        Test if the Rust endpoint is associated when the connection is opened.
        """
        rust_connection = RustUDPConnection(Mock(create_udp_associate=Mock(return_value=1337)), 1)

        await rust_connection.open()

        self.assertEqual(1337, rust_connection.port)
        self.assertEqual(1337, rust_connection.get_listen_port())
        self.assertEqual(call(0, 1), rust_connection.rust_endpoint.create_udp_associate.call_args)

    async def test_open_rust_endpoint_twice(self) -> None:
        """
        Test if the Rust endpoint is not opened twice.
        """
        rust_connection = RustUDPConnection(Mock(create_udp_associate=Mock(return_value=42)), 1)
        rust_connection.port = 1337

        await rust_connection.open()

        self.assertEqual(1337, rust_connection.port)
        self.assertEqual(1337, rust_connection.get_listen_port())

    async def test_close_rust_endpoint(self) -> None:
        """
        Test if the Rust endpoint gets closed with the connection.
        """
        rust_connection = RustUDPConnection(Mock(create_udp_associate=Mock(return_value=1337)), 1)
        await rust_connection.open()
        rust_connection.close()

        self.assertEqual(call(1337), rust_connection.rust_endpoint.close_udp_associate.call_args)

    def test_close_unopened_rust_endpoint(self) -> None:
        """
        Test if the Rust endpoint does not close an unopened connection.
        """
        rust_connection = RustUDPConnection(Mock(), 1)
        rust_connection.close()

        self.assertIsNone(rust_connection.rust_endpoint.close_udp_associate.call_args)
