from __future__ import absolute_import

from Tribler.Core.Socks5.server import Socks5Server
from Tribler.Test.test_as_server import AbstractServer


class TestSocks5Server(AbstractServer):
    """
    Test the basic functionality of the socks5 server.
    """

    async def setUp(self):
        await super(TestSocks5Server, self).setUp()
        self.socks5_server = Socks5Server(self.get_port(), None)

    async def tearDown(self):
        await self.socks5_server.stop()
        await super(TestSocks5Server, self).tearDown()

    async def test_start_server(self):
        """
        Test writing an invalid version to the socks5 server
        """
        await self.socks5_server.start()
