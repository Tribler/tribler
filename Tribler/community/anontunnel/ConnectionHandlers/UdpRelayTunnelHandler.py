import logging
logger = logging.getLogger(__name__)

__author__ = 'Chris'


class UdpRelayTunnelHandler(object):
    """
    Unwraps incoming SOCKS5 UDP packets and sends them over the DispersyTunnel
    """

    def __init__(self, single_socket, server):
        logger.info("UDP relay handler created")
        self.single_socket = single_socket
        self.server = server
        """:type : Socks5Server"""

    def data_came_in(self, packets):
        self.server.on_client_udp_packets(self.single_socket, packets)