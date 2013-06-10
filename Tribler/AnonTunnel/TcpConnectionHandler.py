'''
Created on 3 jun. 2013

@author: Chris
'''
import socket
import sys
from traceback import print_exc
from Socks5Connection import Socks5Connection

import logging
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from TcpRelayConnection import TcpRelayConnection
from UdpRelayHandler import UdpRelayHandler
from UdpReturnHandler import UdpReturnHandler

logger = logging.getLogger(__name__)


class TcpConnectionHandler:

    @property
    def server(self):
        """


        :rtype : Socks5AnonTunnel
        """
        return self._server

    @server.setter
    def set_server(self, server):
        self._server = server

    def __init__(self):
        self.socket2connection = {}
        self._server = None

    def external_connection_made(self, s):
        # Extra check in case bind() no work

        assert isinstance(s, SingleSocket)
        logger.info("accepted a socket on port %d", s.get_myport())

        tcp_connection = Socks5Connection(s, self)
        self.socket2connection[s] = tcp_connection

    def switch_to_tcp_relay(self, source, destination):
        """

        :param source:
        :param destination:
        """
        self.socket2connection[source] = TcpRelayConnection(source, destination, self)
        self.socket2connection[destination] = TcpRelayConnection(destination, source, self)


    def connection_flushed(self, s):
        pass

    def connection_lost(self, s):
        logger.info("Connection lost")
        del self.socket2connection[s]

    def data_came_in(self, s, data):
        tcp_connection = self.socket2connection[s]
        try:
            tcp_connection.data_came_in(data)
        except:
            print_exc()

    def shutdown(self):
        for tcp_connection in self.socket2connection.values():
            tcp_connection.shutdown()

    def start_connection(self, dns):
        s = self.server.start_connection(dns)
        return s

