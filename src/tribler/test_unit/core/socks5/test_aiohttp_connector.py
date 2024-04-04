from __future__ import annotations

import asyncio
import socket
import sys
from unittest.mock import Mock, patch

from aiohttp import ClientRequest, ClientTimeout
from ipv8.test.base import TestBase
from yarl import URL

from tribler.core.socks5.client import Socks5Client


class MockSocks5Client(Socks5Client):
    """
    Mocks a Socks5Client's TCP connection call.
    """

    instance = None

    async def connect_tcp(self, target_addr: tuple[str, int]) -> None:
        """
        Fake a TCP connection establishment.
        """
        MockSocks5Client.instance = self
        await asyncio.sleep(0)  # Give the parent some time to process the timeout check
        self.connected_to = target_addr
        self.transport = Mock()


class TestSocks5Connector(TestBase):
    """
    Tests for the Socks5Connector class.
    """

    async def setUp(self) -> None:
        """
        Create a patched connector.
        """
        super().setUp()
        self.connection = None
        # Make sure are imports are clean (note: these may have been imported in other TestCases).
        for module_name in list(sys.modules.keys()):
            if module_name.startswith("tribler.core.socks5.") and module_name != "tribler.core.socks5.client":
                del sys.modules[module_name]
        # Patch the module.
        with patch(target="tribler.core.socks5.client.Socks5Client", new=MockSocks5Client) as self.client:
            from tribler.core.socks5.aiohttp_connector import Socks5Connector
            self.connector = Socks5Connector(None)

    async def tearDown(self) -> None:
        """
        Close any connection and the connector.
        """
        if self.connection is not None:
            self.connection.close()
        await self.connector.close()
        await super().tearDown()

    async def test_connect_without_timeout(self) -> None:
        """
        Test if connect can be called without a timeout.
        """
        self.connection = await self.connector.connect(ClientRequest("GET", URL("http://localhost/")), [],
                                                       ClientTimeout())

        self.assertEqual(("localhost", 80), self.client.instance.connected_to)

    async def test_connect_with_timeout(self) -> None:
        """
        Test if connect can be called with a timeout.
        """
        self.connection = await self.connector.connect(ClientRequest("GET", URL("http://localhost/")), [],
                                                       ClientTimeout(sock_connect=1.0))

        self.assertEqual(("localhost", 80), self.client.instance.connected_to)

    async def test_connect_pass_timeout(self) -> None:
        """
        Test if connect correctly times out.
        """
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.connection = await self.connector.connect(ClientRequest("GET", URL("http://localhost/")), [],
                                                           ClientTimeout(sock_connect=0.0))

    async def test_resolver(self) -> None:
        """
        Test if the resolver creates a correctly resolved dict.
        """
        from tribler.core.socks5.aiohttp_connector import FakeResolver
        resolver = FakeResolver()
        resolved, = await resolver.resolve("testhostname", 8, socket.AF_INET6)

        self.assertEqual("testhostname", resolved["hostname"])
        self.assertEqual("testhostname", resolved["host"])
        self.assertEqual(8, resolved["port"])
        self.assertEqual(socket.AF_INET6, resolved["family"])
        self.assertEqual(0, resolved["proto"])
        self.assertEqual(0, resolved["flags"])
