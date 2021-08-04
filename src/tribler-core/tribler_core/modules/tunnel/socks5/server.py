import logging
from asyncio import get_event_loop
from typing import Optional

from tribler_core.modules.tunnel.community.dispatcher import TunnelDispatcher
from tribler_core.modules.tunnel.socks5.connection import Socks5Connection


class Socks5Server:
    """
    This object represents a Socks5 server.
    """

    def __init__(self, port=None, output_stream: Optional[TunnelDispatcher] = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.port = port
        self.output_stream = output_stream
        self.server = None
        self.sessions = []

    async def start(self):
        """
        Start the socks5 server by listening on the specified TCP ports.
        """
        def build_protocol():
            socks5connection = Socks5Connection(self)
            self.sessions.append(socks5connection)
            return socks5connection
        self.server = await get_event_loop().create_server(build_protocol, '127.0.0.1', self.port)
        server_socket = self.server.sockets[0]
        _, bind_port = server_socket.getsockname()[:2]
        self.port = bind_port
        self._logger.info("Started SOCKS5 server on port %i", self.port)

    async def stop(self):
        """
        Stop the socks5 server.
        """
        [s.close('stopping') for s in self.sessions]
        self.sessions = []

        if self.server:
            self.server.close()
            await self.server.wait_closed()

    def connection_lost(self, socks5connection):
        self._logger.debug("SOCKS5 TCP connection lost")
        if socks5connection in self.sessions:
            self.sessions.remove(socks5connection)

        socks5connection.close()
