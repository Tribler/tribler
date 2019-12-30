import logging
from asyncio import DatagramProtocol, get_event_loop

from tribler_core.modules.tunnel.socks5 import conversion


class SocksUDPConnection(DatagramProtocol):

    def __init__(self, socksconnection, remote_udp_address):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksconnection = socksconnection
        self.transport = None

        if remote_udp_address != ("0.0.0.0", 0):
            self.remote_udp_address = remote_udp_address
        else:
            self.remote_udp_address = None

    async def open(self):
        self.transport, _ = await get_event_loop().create_datagram_endpoint(lambda: self,
                                                                            local_addr=('0.0.0.0', 0))

    def get_listen_port(self):
        _, port = self.transport.get_extra_info('sockname')
        return port

    def sendDatagram(self, data):
        if self.remote_udp_address:
            self.transport.sendto(data, self.remote_udp_address)
            return True
        else:
            self._logger.error("cannot send data, no clue where to send it to")
            return False

    def datagram_received(self, data, source):
        # if remote_address was not set before, use first one
        if self.remote_udp_address is None:
            self.remote_udp_address = source

        if self.remote_udp_address == source:
            try:
                request = conversion.decode_udp_packet(data)
            except conversion.IPV6AddrError:
                self._logger.warning("Received an IPV6 udp datagram, dropping it (Not implemented yet)")
                return False
            except conversion.InvalidAddressException as ide:
                self._logger.warning("Received an invalid host address. %r", ide)
                return False

            if request.frag == 0 and request.destination_host:
                return self.socksconnection.socksserver.udp_output_stream.on_socks5_udp_data(self, request)
            else:
                self._logger.debug("No support for fragmented data or without destination host, dropping")
        else:
            self._logger.debug("Ignoring data from %s:%d, is not %s:%d",
                               source[0], source[1], self.remote_udp_address[0], self.remote_udp_address[1])

        return False

    def close(self):
        if self.transport:
            self.transport.close()
            self.transport = None
