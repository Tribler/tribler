import logging

from Tribler.Core.Socks5 import conversion
from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol


class SocksUDPConnection(DatagramProtocol):

    def __init__(self, socksconnection, remote_udp_address):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksconnection = socksconnection

        if remote_udp_address != ("0.0.0.0", 0):
            self.remote_udp_address = remote_udp_address
        else:
            self.remote_udp_address = None

        self.listen_port = reactor.listenUDP(0, self)

    def get_listen_port(self):
        return self.listen_port.getHost().port

    def sendDatagram(self, data):
        if self.remote_udp_address:
            self.transport.write(data, self.remote_udp_address)
            return True
        else:
            self._logger.error("cannot send data, no clue where to send it to")
            return False

    def datagramReceived(self, data, source):
        # if remote_address was not set before, use first one
        if self.remote_udp_address is None:
            self.remote_udp_address = source

        if self.remote_udp_address == source:
            try:
                request = conversion.decode_udp_packet(data)
            except conversion.IPV6AddrError:
                self._logger.warning("Received an IPV6 udp datagram, dropping it (Not implemented yet)")
                return False

            if request.frag == 0:
                return self.socksconnection.socksserver.udp_output_stream.on_socks5_udp_data(self, request)
            else:
                self._logger.debug("No support for fragmented data, dropping")
        else:
            self._logger.debug("Ignoring data from %s:%d, is not %s:%d",
                               source[0], source[1], self.remote_udp_address[0], self.remote_udp_address[1])

        return False

    def close(self):
        exit_value = self.listen_port.stopListening()
        self.listen_port = None
        return exit_value
