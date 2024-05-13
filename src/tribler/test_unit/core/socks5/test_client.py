from __future__ import annotations

from asyncio import sleep
from unittest.mock import Mock, call

from ipv8.test.base import TestBase

from tribler.core.socks5.client import Socks5Client, Socks5ClientUDPConnection, Socks5Error


class MockSocks5Client(Socks5Client):
    """
    A Mocked Socks5Client that does not pull any event loop constructs.

    The following three methods are tested in test_server.
    """

    async def _login(self) -> None:
        """
        Fake a login.
        """
        await sleep(0)
        self.transport = Mock()

    async def _associate_udp(self, local_addr: tuple[str, int] | None = None) -> None:
        """
        Fake a UDP association.
        """
        await sleep(0)
        self.connection = Socks5ClientUDPConnection(self.callback)

    async def _connect_tcp(self, target_addr: tuple[str, int]) -> None:
        """
        Fake a TCP connection.
        """
        await sleep(0)
        self.connected_to = target_addr


class TestSocks5Client(TestBase):
    """
    Tests for the Socks5Client class.
    """

    def test_data_received_connected(self) -> None:
        """
        Test if data is fed to the registered callback when a connection is open.
        """
        callback = Mock()
        client = MockSocks5Client(None, callback)
        client.connected_to = ("localhost", 80)

        client.data_received(b"test")

        self.assertEqual(call(b"test", ("localhost", 80)), callback.call_args)

    async def test_data_received_queue_unconnected(self) -> None:
        """
        Test if data is put in a single-item queue when no connection is open.
        """
        callback = Mock()
        client = MockSocks5Client(None, callback)

        client.data_received(b"test")

        self.assertEqual(None, callback.call_args)
        self.assertTrue(client.queue.full())
        self.assertEqual(b"test", await client.queue.get())

    def test_tcp_connection_lost(self) -> None:
        """
        Test if the tranport is set to None when a TCP connection is lost.
        """
        client = MockSocks5Client(None, None)
        client.connected_to = ("localhost", 80)

        client.connection_lost(None)

        self.assertIsNone(client.transport)
        self.assertFalse(client.connected)

    def test_udp_connection_lost(self) -> None:
        """
        Test if the tranport is set to None when a UDP connection is lost.
        """
        client = MockSocks5Client(None, None)
        client.connection = Socks5ClientUDPConnection(client.callback)

        client.connection_lost(None)

        self.assertIsNone(client.transport)
        self.assertFalse(client.associated)

    async def test_associate_udp(self) -> None:
        """
        Test if a client can associate through UDP.
        """
        client = MockSocks5Client(None, None)

        await client.associate_udp()

        self.assertTrue(client.associated)

    async def test_disallow_associate_udp_on_tcp(self) -> None:
        """
        Test if a client cannot associate through UDP using a pre-established TCP connection.
        """
        client = MockSocks5Client(None, None)
        await client.connect_tcp(("localhost", 80))

        with self.assertRaises(Socks5Error):
            await client.associate_udp()

        self.assertFalse(client.associated)

    async def test_connect_tcp(self) -> None:
        """
        Test if a client can connect through TCP.
        """
        client = MockSocks5Client(None, None)

        await client.connect_tcp(("localhost", 80))

        self.assertTrue(client.connected)

    async def test_disallow_connect_tcp_on_udp(self) -> None:
        """
        Test if a client cannot connect through TCP using a pre-established UDP association.
        """
        client = MockSocks5Client(None, None)
        await client.associate_udp()

        with self.assertRaises(Socks5Error):
            await client.connect_tcp(("localhost", 80))

        self.assertFalse(client.connected)

    async def test_send_to(self) -> None:
        """
        Test if we can send over an established UDP connection.
        """
        client = MockSocks5Client(None, None)
        await client.associate_udp()
        client.connection.transport = Mock()

        client.sendto(b"test", ("localhost", 80))

        self.assertEqual(call(b"\x00\x00\x00\x03\tlocalhost\x00Ptest", None),
                         client.connection.transport.sendto.call_args)

    async def test_send_to_no_connection(self) -> None:
        """
        Test if we cannot send without an established UDP connection.
        """
        client = MockSocks5Client(None, None)

        with self.assertRaises(Socks5Error):
            client.sendto(b"test", ("localhost", 80))

    async def test_write(self) -> None:
        """
        Test if we can write over an established TCP connection.
        """
        client = MockSocks5Client(None, None)
        await client.connect_tcp(("localhost", 80))

        client.write(b"test")

        self.assertEqual(call(b"test"), client.transport.write.call_args)

    async def test_write_no_connection(self) -> None:
        """
        Test if we cannot write without an established TCP connection.
        """
        client = MockSocks5Client(None, None)

        with self.assertRaises(Socks5Error):
            client.write(b"test")
