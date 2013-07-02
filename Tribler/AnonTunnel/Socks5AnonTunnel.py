"""
Created on 3 jun. 2013

@author: Chris
"""

from traceback import print_exc
from threading import Thread, Event
import logging
from Tribler.AnonTunnel.CommandHandler import CommandHandler

from Tribler.Core.RawServer.RawServer import RawServer
from TcpConnectionHandler import TcpConnectionHandler
from UdpRelayTunnelHandler import UdpRelayTunnelHandler


logger = logging.getLogger(__name__)

import Socks5.structs

class Socks5AnonTunnel(Thread):
    def __init__(self, tunnel, Socks5_port=1080, timeout=300.0):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName('Socks5Server' + self.getName())
        self.Socks5_port = Socks5_port

        self.udp_relay_socket = None

        self.connection_handler = TcpConnectionHandler()
        self.connection_handler.server = self

        self.destination_address = None


        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    timeout / 5.0,
                                    timeout,
                                    ipv6_enable=False,
                                    failfunc=self.raw_server_fatal_error_func,
                                    errorfunc=self.raw_server_non_fatal_error_func)

        try:
            port = self.raw_server.find_and_bind(self.Socks5_port,self.Socks5_port,self.Socks5_port+10, ['0.0.0.0'], reuse=True)
            logger.info("Socks5Proxy binding to %s:%s", "0.0.0.0", port)
        except:
            print_exc()


        self.tunnel = tunnel
        self.tunnel.subscribe("on_data", self.on_tunnel_data)
        tunnel.socket_server = self

        cmd_socket = self.raw_server.create_udpsocket(1081, "127.0.0.1")
        self.start_listening_udp(cmd_socket, CommandHandler(cmd_socket, self.tunnel))

    def shutdown(self):
        self.connection_handler.shutdown()
        self.server_done_flag.set()

    #
    # Following methods are called by Instance2Instance thread
    #
    # noinspection PyUnusedLocal
    def raw_server_fatal_error_func(self, event):
        """ Called by network thread """
        print_exc()

    def raw_server_non_fatal_error_func(self, event):
        """ Called by network thread """

    def run(self):
        try:
            try:
                self.raw_server.listen_forever(self)
            except:
                print_exc()
        finally:
            self.raw_server.shutdown()

    def external_connection_made(self, s):
        try:
            self.connection_handler.external_connection_made(s)
        except:
            print_exc()
            s.close()

    def connection_flushed(self, s):
        self.connection_handler.connection_flushed(s)

    def connection_lost(self, s):
        self.connection_handler.connection_lost(s)

    def data_came_in(self, s, data):
        try:
            self.connection_handler.data_came_in(s, data)
        except:
            print_exc()
            s.close()

    def add_task(self, func, t):
        self.raw_server.add_task(func, t)

    def start_connection(self, dns):
        return self.raw_server.start_connection_raw(dns, handler=self.connection_handler)

    def create_udp_socket(self):
        """
        Creates a UDP socket bound to a free port on all interfaces
        :rtype : socket
        """
        return self.raw_server.create_udpsocket(0, "0.0.0.0")

    def create_udp_relay(self):
        """
        Initializes an UDP relay by listening to a newly created socket and attaching a UdpRelayHandler
        :rtype : socket
        """
        if self.udp_relay_socket is None:
            self.udp_relay_socket = self.create_udp_socket()
            handler = UdpRelayTunnelHandler(self.udp_relay_socket, self)
            self.start_listening_udp(self.udp_relay_socket, handler)

        return self.udp_relay_socket

    def start_listening_udp(self, udp_socket, handler):
        """
        Start listening on an UDP socket by attaching an event handler

        :param udp_socket: the socket to listen on
        :param handler: the handler to call when new packets are received on the UDP socket
        :return: None
        """

        self.raw_server.start_listening_udp(udp_socket, handler)

    def on_tunnel_data(self, event):
        packet = event.data

        source_address = packet.origin

        destination_address = self.destination_address

        encapsulated = Socks5.structs.encode_udp_packet(0, 0, Socks5.structs.ADDRESS_TYPE_IPV4, source_address[0],source_address[1], packet.data)
        self.udp_relay_socket.sendto(encapsulated, destination_address)
        logger.info("Returning UDP packets from %s to %s using proxy port %d",source_address, destination_address, self.udp_relay_socket.getsockname()[1])



