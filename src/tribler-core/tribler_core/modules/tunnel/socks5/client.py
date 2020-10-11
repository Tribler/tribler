import logging
import socket
from asyncio import DatagramProtocol, Protocol, Queue, get_event_loop

from tribler_core.modules.tunnel.socks5.conversion import (
    ADDRESS_TYPE_DOMAIN_NAME,
    ADDRESS_TYPE_IPV4,
    CommandRequest,
    CommandResponse,
    MethodsRequest,
    MethodsResponse,
    REQ_CMD_CONNECT,
    REQ_CMD_UDP_ASSOCIATE,
    SOCKS_AUTH_ANON,
    SOCKS_VERSION,
    UdpPacket,
    socks5_serializer,
)


class Socks5Error(Exception):
    pass


class Socks5ClientUDPConnection(DatagramProtocol):

    def __init__(self, callback):
        self.callback = callback
        self.transport = None
        self.proxy_udp_addr = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, _):
        request, _ = socks5_serializer.unpack_serializable(UdpPacket, data)
        self.callback(request.data, request.destination)

    def sendto(self, data, target_addr):
        packet = socks5_serializer.pack_serializable(UdpPacket(0, 0, target_addr, data))
        self.transport.sendto(packet, self.proxy_udp_addr)


class Socks5Client(Protocol):
    """
    This object represents a minimal Socks5 client. Both TCP and UDP are supported.
    """

    def __init__(self, proxy_addr, callback):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.proxy_addr = proxy_addr
        self.callback = callback
        self.transport = None
        self.connection = None
        self.connected_to = None
        self.queue = Queue(maxsize=1)

    def data_received(self, data):
        if self.connected_to:
            self.callback(data)
        elif self.queue.empty():
            self.queue.put_nowait(data)

    def connection_lost(self, _):
        self.transport = None

    async def _send(self, data):
        self.transport.write(data)
        return await self.queue.get()

    async def _login(self):
        self.transport, _ = await get_event_loop().create_connection(lambda: self, *self.proxy_addr)

        request = MethodsRequest(SOCKS_VERSION, [SOCKS_AUTH_ANON])
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(MethodsResponse, data)

        if response.version != SOCKS_VERSION or response.method != SOCKS_AUTH_ANON:
            raise Socks5Error('Unsupported proxy server')

    async def _associate_udp(self, local_addr=None):
        local_addr = local_addr or ('127.0.0.1', 0)
        connection = Socks5ClientUDPConnection(self.callback)
        transport, _ = await get_event_loop().create_datagram_endpoint(lambda: connection, local_addr=local_addr)
        sock = transport.get_extra_info("socket")

        request = CommandRequest(SOCKS_VERSION, REQ_CMD_UDP_ASSOCIATE, 0, sock.getsockname())
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(CommandResponse, data)
        connection.proxy_udp_addr = response.bind

        if response.version != SOCKS_VERSION:
            raise Socks5Error('Unsupported proxy server')

        if response.reply > 0:
            raise Socks5Error('UDP associate failed')

        self.connection = connection

    async def _connect_tcp(self, target_addr):
        try:
            socket.inet_aton(target_addr[0])
            address_type = ADDRESS_TYPE_IPV4
        except (ValueError, OSError):
            address_type = ADDRESS_TYPE_DOMAIN_NAME

        request = CommandRequest(SOCKS_VERSION, REQ_CMD_CONNECT, 0, (address_type, *target_addr))
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(CommandResponse, data)

        if response.version != SOCKS_VERSION:
            raise Socks5Error('Unsupported proxy server')

        if response.reply > 0:
            raise Socks5Error('TCP connect failed')

        self.connected_to = target_addr

    @property
    def connected(self):
        return self.transport is not None and self.connected_to is not None

    @property
    def associated(self):
        return self.transport is not None and self.connection is not None

    async def associate_udp(self):
        if self.connected:
            raise Socks5Error(f'Client already used for connecting to {self.connected_to[0]}:{self.connected_to[1]}')

        if not self.associated:
            await self._login()
            await self._associate_udp()

    def sendto(self, data, target_addr):
        if not self.associated:
            raise Socks5Error('Not associated yet. First call associate_udp.')
        self.connection.sendto(data, target_addr)

    async def connect_tcp(self, target_addr):
        if self.associated:
            raise Socks5Error('Client already used for UDP communication')

        if not self.connected:
            await self._login()
            await self._connect_tcp(target_addr)

    def write(self, data):
        if not self.connected:
            raise Socks5Error('Not connected yet. First call connect_tcp.')
        return self.transport.write(data)
