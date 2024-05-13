from __future__ import annotations

import ipaddress
import logging
import socket
from asyncio import BaseTransport, DatagramProtocol, DatagramTransport, Protocol, Queue, WriteTransport, get_event_loop
from typing import Callable, cast

from ipv8.messaging.interfaces.udp.endpoint import DomainAddress
from ipv8.messaging.serialization import PackError

from tribler.core.socks5.conversion import (
    REQ_CMD_CONNECT,
    REQ_CMD_UDP_ASSOCIATE,
    SOCKS_AUTH_ANON,
    SOCKS_VERSION,
    CommandRequest,
    CommandResponse,
    MethodsRequest,
    MethodsResponse,
    UdpPacket,
    socks5_serializer,
)


class Socks5Error(Exception):
    """
    Errors with the SOCKS5 protocol.
    """


class Socks5ClientUDPConnection(DatagramProtocol):
    """
    A datagram protocol for Socks5 connections.
    """

    def __init__(self, callback: Callable[[bytes, DomainAddress | tuple], None]) -> None:
        """
        Create a new Socks5 udp connection.
        """
        self.callback = callback
        self.transport: DatagramTransport | None = None
        self.proxy_udp_addr = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def connection_made(self, transport: BaseTransport) -> None:
        """
        Callback for when a transport is available.
        """
        self.transport = cast(DatagramTransport, transport)

    def datagram_received(self, data: bytes, _: tuple) -> None:
        """
        Callback for when data is received over our transport.
        """
        try:
            request, _ = socks5_serializer.unpack_serializable(UdpPacket, data)
        except PackError:
            self.logger.warning("Error while decoding packet", exc_info=True)
        else:
            self.callback(request.data, request.destination)

    def sendto(self, data: bytes, target_addr: DomainAddress | tuple) -> None:
        """
        Attempt to send the given data to the given address.
        """
        if self.transport is None:
            return
        try:
            ipaddress.IPv4Address(target_addr[0])
        except ipaddress.AddressValueError:
            target_addr = DomainAddress(*target_addr)
        packet = socks5_serializer.pack_serializable(UdpPacket(0, 0, target_addr, data))
        self.transport.sendto(packet, self.proxy_udp_addr)


class Socks5Client(Protocol):
    """
    This object represents a minimal Socks5 client. Both TCP and UDP are supported.
    """

    def __init__(self, proxy_addr: tuple, callback: Callable[[bytes, DomainAddress | tuple], None]) -> None:
        """
        Create a client for the given proxy address and call the given callback with incoming data.
        """
        self.proxy_addr = proxy_addr
        self.callback = callback
        self.transport: WriteTransport | None = None
        self.connection: Socks5ClientUDPConnection | None = None
        self.connected_to: DomainAddress | tuple | None = None
        self.queue: Queue[bytes] = Queue(maxsize=1)

    def data_received(self, data: bytes) -> None:
        """
        Callback for when data comes in. Call our registered callback or save the incoming save for calling back later.
        """
        if self.connected_to:
            self.callback(data, self.connected_to)
        elif self.queue.empty():
            self.queue.put_nowait(data)

    def connection_lost(self, _: Exception | None) -> None:
        """
        Callback for when the connection is dropped.
        """
        self.transport = None

    async def _send(self, data: bytes) -> bytes:
        """
        Send data to the remote and wait for an answer.
        """
        cast(WriteTransport, self.transport).write(data)
        return await self.queue.get()

    async def _login(self) -> None:
        """
        Send a login.

        :raises Socks5Error: If the proxy server is unsupported.
        """
        self.transport, _ = await get_event_loop().create_connection(lambda: self, *self.proxy_addr)

        request = MethodsRequest(SOCKS_VERSION, [SOCKS_AUTH_ANON])
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(MethodsResponse, data)

        if response.version != SOCKS_VERSION or response.method != SOCKS_AUTH_ANON:
            msg = "Unsupported proxy server"
            raise Socks5Error(msg)

    async def _associate_udp(self, local_addr: tuple | None = None) -> None:
        """
        Send an associate request to the connection.
        """
        local_addr = local_addr or ('127.0.0.1', 0)
        connection = Socks5ClientUDPConnection(self.callback)
        transport, _ = await get_event_loop().create_datagram_endpoint(lambda: connection, local_addr=local_addr)
        sock = transport.get_extra_info("socket")

        request = CommandRequest(SOCKS_VERSION, REQ_CMD_UDP_ASSOCIATE, 0, sock.getsockname())
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(CommandResponse, data)
        connection.proxy_udp_addr = response.bind

        if response.version != SOCKS_VERSION:
            msg = "Unsupported proxy server"
            raise Socks5Error(msg)

        if response.reply > 0:
            msg = "UDP associate failed"
            raise Socks5Error(msg)

        self.connection = connection

    async def _connect_tcp(self, target_addr: tuple) -> None:
        """
        Connect to the given address using TCP.
        """
        try:
            socket.inet_aton(target_addr[0])
        except (ValueError, OSError):
            target_addr = DomainAddress(*target_addr)

        request = CommandRequest(SOCKS_VERSION, REQ_CMD_CONNECT, 0, target_addr)
        data = await self._send(socks5_serializer.pack_serializable(request))
        response, _ = socks5_serializer.unpack_serializable(CommandResponse, data)

        if response.version != SOCKS_VERSION:
            msg = "Unsupported proxy server"
            raise Socks5Error(msg)

        if response.reply > 0:
            msg = "TCP connect failed"
            raise Socks5Error(msg)

        self.connected_to = target_addr

    @property
    def connected(self) -> bool:
        """
        Whether this client is connected over TCP.
        """
        return self.transport is not None and self.connected_to is not None

    @property
    def associated(self) -> bool:
        """
        Whether this client is associated over UDP.
        """
        return self.transport is not None and self.connection is not None

    async def associate_udp(self) -> None:
        """
        Login and associate with the proxy.
        """
        if self.connected:
            connection = cast(tuple, self.connected_to)
            msg = f"Client already used for connecting to {connection[0]}:{connection[1]}"
            raise Socks5Error(msg)

        if not self.associated:
            await self._login()
            await self._associate_udp()

    def sendto(self, data: bytes, target_addr: tuple) -> None:
        """
        Attemp to send data to the given address.

        :raises Socks5Error: If we have not associated UDP yet.
        """
        if not self.associated:
            msg = "Not associated yet. First call associate_udp."
            raise Socks5Error(msg)
        cast(Socks5ClientUDPConnection, self.connection).sendto(data, target_addr)

    async def connect_tcp(self, target_addr: tuple) -> None:
        """
        Login and connect to the proxy using TCP.

        :raises Socks5Error: If we have not associated UDP yet.
        """
        if self.associated:
            msg = "Client already used for UDP communication"
            raise Socks5Error(msg)

        if not self.connected:
            await self._login()
            await self._connect_tcp(target_addr)

    def write(self, data: bytes) -> None:
        """
        Write to whatever transport we have.
        """
        if not self.connected:
            msg = "Not connected yet. First call connect_tcp."
            raise Socks5Error(msg)
        cast(WriteTransport, self.transport).write(data)
