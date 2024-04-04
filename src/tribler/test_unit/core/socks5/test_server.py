from __future__ import annotations

import socket
from asyncio import Transport, get_event_loop, sleep
from asyncio.base_events import Server
from typing import Callable
from unittest.mock import Mock, patch

from ipv8.test.base import TestBase

from tribler.core.socks5.client import Socks5Client, Socks5Error
from tribler.core.socks5.conversion import UdpPacket, socks5_serializer
from tribler.core.socks5.server import Socks5Server


class MockTransport(Transport):
    """
    Mocked Transport that offloads to a callback.
    """

    def __init__(self, callback: Callable[[bytes], None]) -> None:
        """
        Create a new MockTransport.
        """
        super().__init__()
        self.callback = callback

    def write(self, data: bytes) -> None:
        """
        Pretend to write, actually just call the callback.
        """
        self.callback(data)

    def sendto(self, data: bytes, _: tuple) -> None:
        """
        Pretend to write, actually just call the callback.
        """
        self.callback(data)

    def close(self) -> None:
        """
        Pretend to close.
        """

    def get_extra_info(self, key: str) -> dict:
        """
        Fake extra info.
        """
        if key == "socket":
            return Mock(getsockname=Mock(return_value=('0.0.0.0', 0)))
        return ('0.0.0.0', 0)


class MockServer(Server):
    """
    A Server with a mocked close method.
    """

    def close(self) -> None:
        """
        Pretend to close.
        """
        self._sockets = []
        super().close()


class TestSocks5Server(TestBase):
    """
    Tests for the Socks5Server class.
    """

    def setUp(self) -> None:
        """
        Create a new server.
        """
        self.socks5_server = Socks5Server(1, output_stream=Mock())
        self.client_connection = None
        self.client_transport = None
        self.mock_server = None

    async def tearDown(self) -> None:
        """
        Stop the server.
        """
        await self.socks5_server.stop()
        await super().tearDown()

    def deliver_to_client(self, data: bytes) -> None:
        """
        Fake a Server sending to a client.
        """
        self.client_connection.queue.put_nowait(data)

    async def create_server(self, protocol_factory, host=None, port=None, *,  # noqa: ANN001, PLR0913
                            family=socket.AF_UNSPEC, flags=socket.AI_PASSIVE, sock=None, backlog=100,  # noqa: ANN001
                            ssl=None, reuse_address=None, reuse_port=None, ssl_handshake_timeout=None,  # noqa: ANN001
                            start_serving=True) -> Server:  # noqa: ANN001
        """
        Mock the event loop's create_server call.
        """
        sockets = [Mock(getsockname=Mock(return_value=('0.0.0.0', 0)))]
        self.mock_server = MockServer(get_event_loop(), sockets, protocol_factory, ssl, backlog, ssl_handshake_timeout)
        connection = protocol_factory()
        connection.transport = MockTransport(self.deliver_to_client)
        return self.mock_server

    async def create_connection(self, protocol_factory, host=None, port=None, *, ssl=None,  # noqa: ANN001, PLR0913
                                family=0, proto=0, flags=0, sock=None, local_addr=None,  # noqa: ANN001
                                server_hostname=None, ssl_handshake_timeout=None,  # noqa: ANN001
                                happy_eyeballs_delay=None, interleave=None) -> tuple[Transport, None]:  # noqa: ANN001
        """
        Mock the event loop's create_connection call.
        """
        self.client_connection = protocol_factory()
        self.client_transport = MockTransport(self.socks5_server.sessions[0].data_received)
        return self.client_transport, None

    async def create_datagram_endpoint(self, protocol_factory, local_addr=None,  # noqa: ANN001, PLR0913
                                       remote_addr=None, *, family=0, proto=0, flags=0,  # noqa: ANN001
                                       reuse_address=None, reuse_port=None, allow_broadcast=None,  # noqa: ANN001
                                       sock=None) -> tuple[Transport, None]:  # noqa: ANN001
        """
        Mock the event loop's create_datagram_endpoint call.
        """
        protocol_factory().transport = self.client_transport
        return self.client_transport, None

    async def create_server_and_client(self) -> Socks5Client:
        """
        Create a server and an associated client.
        """
        with patch.object(get_event_loop(), "create_server", self.create_server):
            await self.socks5_server.start()
        with patch.object(get_event_loop(), "create_connection", self.create_connection),\
                patch.object(get_event_loop(), "create_datagram_endpoint", self.create_datagram_endpoint):
            return Socks5Client(('127.0.0.1', self.socks5_server.port), Mock())

    async def test_socks5_udp_associate(self) -> None:
        """
        Test if sending a UDP associate request to the server succeeds.
        """
        client = await self.create_server_and_client()
        with patch.object(get_event_loop(), "create_connection", self.create_connection):
            await client.associate_udp()

        self.assertTrue(client.associated)

    async def test_socks5_sendto_fail(self) -> None:
        """
        Test if sending a UDP packet without a successful association fails.
        """
        client = await self.create_server_and_client()
        with patch.object(get_event_loop(), "create_connection", self.create_connection), \
                self.assertRaises(Socks5Error):
            client.sendto(b'\x00', ('127.0.0.1', 123))

    async def test_socks5_sendto_success(self) -> None:
        """
        Test if sending/receiving a UDP packet works correctly.
        """
        client = await self.create_server_and_client()
        with patch.object(get_event_loop(), "create_connection", self.create_connection):
            await client.associate_udp()

            packet = socks5_serializer.pack_serializable(UdpPacket(0, 0, ('127.0.0.1', 123), b'\x00'))
            self.client_connection.connection.datagram_received(packet, None)
            await sleep(0)
            client.callback.assert_called_once_with(b'\x00', ('127.0.0.1', 123))

    async def test_socks5_tcp_connect(self) -> None:
        """
        Test if sending a TCP connect request to the server succeeds.
        """
        client = await self.create_server_and_client()
        with patch.object(get_event_loop(), "create_connection", self.create_connection):
            await client.connect_tcp(('127.0.0.1', 123))
            assert client.transport is not None
            assert client.connection is None

    async def test_socks5_write(self) -> None:
        """
        Test if sending a TCP data to the server succeeds.
        """
        client = await self.create_server_and_client()
        with patch.object(get_event_loop(), "create_connection", self.create_connection):
            await client.connect_tcp(('127.0.0.1', 123))
            client.write(b' ')
            await sleep(.1)
            self.socks5_server.output_stream.on_socks5_tcp_data.assert_called_once_with(self.socks5_server.sessions[0],
                                                                                        ('127.0.0.1', 123), b' ')
