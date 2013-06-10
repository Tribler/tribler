import struct
import Socks5.structs
import socket
import logging
from UdpReturnHandler import UdpReturnHandler

logger = logging.getLogger(__name__)

__author__ = 'Chris'

class UdpRelayHandler:
    def __init__(self, single_socket, server):
        logger.info("UDP relay handler created")
        self.single_socket = single_socket
        self.server = server
        """:type : Socks5Handler"""

    def data_came_in(self,packets):
        for source_address, packet in packets:
            request = Socks5.structs.decode_udp_packet(packet)

            destination = (request.destination_address, request.destination_port)
            logger.info("Relaying UDP packets from %s:%d to %s:%d", source_address[0], source_address[1], request.destination_address, request.destination_port)

            outgoing = self.server.create_udp_socket()
            self.server.start_listening_udp(outgoing, UdpReturnHandler(self.server,self.single_socket, source_address))
            outgoing.sendto( request.payload, destination)