import logging

import Socks5.structs


logger = logging.getLogger(__name__)

__author__ = 'Chris'


class UdpRelayTunnelHandler(object):
    def __init__(self, single_socket, server):
        logger.info("UDP relay handler created")
        self.single_socket = single_socket
        self.server = server
        """:type : Socks5Handler"""

    def data_came_in(self, packets):
        for source_address, packet in packets:
            request = Socks5.structs.decode_udp_packet(packet)

            self.server.destination_address = source_address

            logger.info("Relaying UDP packets from %s:%d to %s:%d", source_address[0], source_address[1],
                        request.destination_address, request.destination_port)

            self.server.tunnel.send_data(
                ultimate_destination=(request.destination_address, request.destination_port),
                payload=request.payload
            )
