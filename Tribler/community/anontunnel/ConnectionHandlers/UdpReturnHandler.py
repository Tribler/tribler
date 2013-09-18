from Tribler.community.anontunnel.Socks5 import structs

__author__ = 'Chris'

import logging

logger = logging.getLogger(__name__)


class UdpReturnHandler(object):
    """
    Returns Dispersy Data Messages to the SOCKS5 client, wrapping the packet into a SOCKS5 packet
    """

    def __init__(self, server, socket, destination_address):
        self.socket = socket
        self.destination_address = destination_address
        self.server = server

    def data_came_in(self, packets):
        for source_address, packet in packets:
            logger.info("Returning UDP packets from %s to %s using proxy port %d", source_address,
                        self.destination_address, self.socket.getsockname()[1])

            encapsulated = structs.encode_udp_packet(0, 0, structs.ADDRESS_TYPE_IPV4, source_address[0],
                                                     source_address[1], packet)

            self.socket.sendto(encapsulated, self.destination_address)