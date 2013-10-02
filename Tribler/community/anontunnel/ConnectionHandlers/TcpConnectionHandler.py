import logging
from Tribler.community.anontunnel.ConnectionHandlers.Socks5Connection import Socks5Connection
from Tribler.community.anontunnel.ConnectionHandlers.TcpRelayConnection import TcpRelayConnection

logger = logging.getLogger(__name__)

from traceback import print_exc
from Tribler.Core.RawServer.SocketHandler import SingleSocket

__author__ = 'chris'


class TcpConnectionHandler(object):
    """
    The TCP Connection handler which responds on events fired by the server.

    It distinguishes two connection types (and its associated handlers). The Socks5Connection and the TcpRelayConnection.
    The first and default mode implements the SOCKS5 protocol where the latter just acts as a man in the middle PROXY for a
    TCP connection.
    """
    def __init__(self):
        self.socket2connection = {}
        self.socks5_server = None
        """ :type : Tribler.community.anontunnel.Socks5Server.Socks5Server """

    def external_connection_made(self, s):
        # Extra check in case bind() no work

        assert isinstance(s, SingleSocket)
        logger.info("accepted a socket on port %d", s.get_myport())

        tcp_connection = Socks5Connection(s, self)
        self.socket2connection[s] = tcp_connection

    def switch_to_tcp_relay(self, source_socket, destination_socket):
        """
        Switch the connection mode to RELAY, any incoming and outgoing data will be relayed

        :param source_socket:
        :param destination_socket:
        """
        self.socket2connection[source_socket] = TcpRelayConnection(source_socket, destination_socket, self)
        self.socket2connection[destination_socket] = TcpRelayConnection(destination_socket, source_socket, self)


    def connection_flushed(self, s):
        pass

    def connection_lost(self, s):
        logger.info("Connection lost")

        tcp_connection = self.socket2connection[s]
        try:
            tcp_connection.close()
        except:
            pass

        del self.socket2connection[s]

    def data_came_in(self, s, data):
        """
        Data is in the READ buffer, depending on MODE the Socks5 or Relay mechanism will be used

        :param s:
        :param data:
        :return:
        """
        tcp_connection = self.socket2connection[s]
        try:
            tcp_connection.data_came_in(data)
        except:
            print_exc()

    def shutdown(self):
        for tcp_connection in self.socket2connection.values():
            tcp_connection.shutdown()

    def start_connection(self, dns):
        s = self.socks5_server.start_connection(dns)
        return s
