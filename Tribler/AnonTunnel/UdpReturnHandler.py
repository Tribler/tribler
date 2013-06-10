__author__ = 'Chris'

import Socks5
import logging

logger = logging.getLogger(__name__)


class UdpReturnHandler:
    def __init__(self, server, socket, destination_address):
        self.socket = socket
        self.destination_address = destination_address
        self.server = server

    def data_came_in(self,packets):
        for source_address, packet in packets:
            logger.info("Returning UDP packets from %s to %s using proxy port %d",source_address, self.destination_address, self.socket.getsockname()[1])

            encapsulated = Socks5.structs.encode_udp_packet(0, 0, Socks5.structs.ATYP_IPV4, source_address[0],source_address[1], packet)

            self.socket.sendto(encapsulated, self.destination_address)