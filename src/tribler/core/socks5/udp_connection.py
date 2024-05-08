from __future__ import annotations

import logging
from asyncio import DatagramProtocol, DatagramTransport, get_event_loop
from typing import TYPE_CHECKING, cast

from ipv8.messaging.serialization import PackError

from tribler.core.socks5.conversion import UdpPacket, socks5_serializer

if TYPE_CHECKING:
    from ipv8.messaging.interfaces.udp.endpoint import DomainAddress
    from ipv8_rust_tunnels.endpoint import RustEndpoint

    from tribler.core.socks5.connection import Socks5Connection


class SocksUDPConnection(DatagramProtocol):
    """
    A datagram protocol for SOCKS5 traffic.
    """

    def __init__(self, socksconnection: Socks5Connection, remote_udp_address: DomainAddress | tuple | None) -> None:
        """
        Create a new socks5 protocol.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksconnection = socksconnection
        self.transport: DatagramTransport | None = None
        self.remote_udp_address = remote_udp_address if remote_udp_address != ("0.0.0.0", 0) else None

    async def open(self) -> None:
        """
        Open a transport for this protocol.
        """
        self.transport, _ = await get_event_loop().create_datagram_endpoint(lambda: self, local_addr=("127.0.0.1", 0))

    def get_listen_port(self) -> int:
        """
        Retrieve the listen port for this protocol.
        """
        if self.transport:
            _, port = self.transport.get_extra_info("sockname")
        else:
            port = 0
        return port

    def send_datagram(self, data: bytes) -> bool:
        """
        Send a datagram to the known remote address. Returns False if there is no remote yet.
        """
        if self.remote_udp_address:
            cast(DatagramTransport, self.transport).sendto(data, self.remote_udp_address)
            return True
        self._logger.error("cannot send data, no clue where to send it to")
        return False

    def datagram_received(self, data: bytes, source: tuple) -> None:
        """
        The callback for when data is handed to our protocol.
        """
        self.cb_datagram_received(data, source)

    def cb_datagram_received(self, data: bytes, source: tuple) -> bool:
        """
        The callback for when data is handed to our protocol and whether the handling succeeded.
        """
        # If remote_address was not set before, use first one
        if self.remote_udp_address is None:
            self.remote_udp_address = source

        if self.remote_udp_address == source:
            try:
                request, _ = socks5_serializer.unpack_serializable(UdpPacket, data)
            except PackError:
                self._logger.warning("Cannot serialize UDP packet")
                return False

            if request.frag == 0:
                output_stream = self.socksconnection.socksserver.output_stream
                if output_stream is not None:
                    # Swallow the data in case the tunnel community has not started yet
                    return output_stream.on_socks5_udp_data(self, request)
            self._logger.debug("No support for fragmented data or without destination host, dropping")
        else:
            self._logger.debug("Ignoring data from %s:%d, is not %s:%d", *source, *self.remote_udp_address)

        return False

    def close(self) -> None:
        """
        Close the transport associated with this protocol.
        """
        if self.transport:
            self.transport.close()
            self.transport = None


class RustUDPConnection:
    """
    A UDP connection that is offloaded to IPv8 Rust.
    """

    def __init__(self, rust_endpoint: RustEndpoint, hops: int) -> None:
        """
        Create a new connection.
        """
        self.rust_endpoint = rust_endpoint
        self.hops = hops
        self.port: int | None = None
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def remote_udp_address(self) -> None:
        """
        Ensure this connection doesn't get picked up by the dispatcher.
        """
        return

    @remote_udp_address.setter
    def remote_udp_address(self, address: tuple) -> None:
        """
        Set the remote address for this connection.
        """
        self.rust_endpoint.set_udp_associate_default_remote(address)

    async def open(self) -> None:
        """
        Allow connections to be established.
        """
        if self.port is not None:
            self.logger.error("UDP connection is already open on port %s", self.port)
            return

        self.port = self.rust_endpoint.create_udp_associate(0, self.hops)

    def get_listen_port(self) -> int:
        """
        Get the claimed port for this connection.
        """
        return self.port or 0

    def close(self) -> None:
        """
        Close the underlying connection.
        """
        if self.port is not None:
            self.rust_endpoint.close_udp_associate(self.port)
            self.port = None
