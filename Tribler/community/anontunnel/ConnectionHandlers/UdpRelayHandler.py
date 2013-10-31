import logging


logger = logging.getLogger(__name__)
__author__ = 'Chris'

from Tribler.community.anontunnel.Socks5 import structs
from UdpReturnHandler import UdpReturnHandler


class UdpRelayHandler(object):
    def __init__(self, single_socket, server):
        logger.info("UDP relay handler created")
        self.single_socket = single_socket
        self.raw_server = server
        """:type : RawServer"""

    def data_came_in(self, packets):
        for source_address, packet in packets:
            request = structs.decode_udp_packet(packet)

            destination = (request.destination_address, request.destination_port)
            logger.info("Relaying UDP packets from %s:%d to %s:%d", source_address[0], source_address[1],
                        request.destination_address, request.destination_port)

            outgoing = self.raw_server.create_udpsocket(0, "0.0.0.0")
            self.raw_server.start_listening_udp(outgoing, UdpReturnHandler(self.raw_server, self.single_socket, source_address))
            outgoing.sendto(request.payload, destination)