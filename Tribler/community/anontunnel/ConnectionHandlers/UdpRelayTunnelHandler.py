import logging
logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.Socks5 import structs

__author__ = 'Chris'


class UdpRelayTunnelHandler(object):
    """
    Unwraps incoming SOCKS5 UDP packets and sends them over the DispersyTunnel
    """

    def __init__(self, single_socket, server):
        logger.info("UDP relay handler created")
        self.single_socket = single_socket
        self.server = server
        """:type : Socks5Handler"""

    def data_came_in(self, packets):
        for source_address, packet in packets:
            request = structs.decode_udp_packet(packet)

            self.server.udp_relays[source_address] = self.single_socket

            if __debug__:
                logger.info("Relaying UDP packets from %s:%d to %s:%d", source_address[0], source_address[1],
                            request.destination_address, request.destination_port)

            self.server.routes[(request.destination_address, request.destination_port)] = source_address

            if self.server.tunnel:
                self.server.tunnel.send_data(
                    ultimate_destination=(request.destination_address, request.destination_port),
                    payload=request.payload
                )
