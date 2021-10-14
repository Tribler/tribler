import logging
from asyncio import DatagramProtocol, get_event_loop

from ipv8.messaging.serialization import PackError

from tribler_core.components.socks_servers.socks5.conversion import UdpPacket, socks5_serializer


class SocksUDPConnection(DatagramProtocol):

    def __init__(self, socksconnection, remote_udp_address):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksconnection = socksconnection
        self.transport = None
        self.remote_udp_address = remote_udp_address if remote_udp_address != ("0.0.0.0", 0) else None

    async def open(self):
        self.transport, _ = await get_event_loop().create_datagram_endpoint(lambda: self,
                                                                            local_addr=('0.0.0.0', 0))

    def get_listen_port(self):
        _, port = self.transport.get_extra_info('sockname')
        return port

    def send_datagram(self, data):
        if self.remote_udp_address:
            self.transport.sendto(data, self.remote_udp_address)
            return True
        self._logger.error("cannot send data, no clue where to send it to")
        return False

    def datagram_received(self, data, source):
        # If remote_address was not set before, use first one
        if self.remote_udp_address is None:
            self.remote_udp_address = source

        if self.remote_udp_address == source:
            try:
                request, _ = socks5_serializer.unpack_serializable(UdpPacket, data)
            except PackError:
                self._logger.warning("Cannot serialize UDP packet")
                return False

            if request.frag == 0 and request.destination:
                output_stream = self.socksconnection.socksserver.output_stream
                if output_stream is not None:
                    # Swallow the data in case the tunnel community has not started yet
                    return output_stream.on_socks5_udp_data(self, request)
            self._logger.debug("No support for fragmented data or without destination host, dropping")
        else:
            self._logger.debug("Ignoring data from %s:%d, is not %s:%d", *source, *self.remote_udp_address)

        return False

    def close(self):
        if self.transport:
            self.transport.close()
            self.transport = None
