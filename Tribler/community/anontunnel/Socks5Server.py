"""
Created on 3 jun. 2013

@author: Chris
"""

import logging

logger = logging.getLogger(__name__)

import socket
from Tribler.community.anontunnel.ConnectionHandlers.TcpConnectionHandler import TcpConnectionHandler
from traceback import print_exc
from ConnectionHandlers.UdpRelayTunnelHandler import UdpRelayTunnelHandler

import Socks5.structs


class Socks5Server(object):
    @property
    def tunnel(self):
        return self._tunnel

    @tunnel.setter
    def tunnel(self, value):
        self._tunnel = value
        self._tunnel.subscribe("on_data", self.on_tunnel_data)

        if self.bound:
            self.bind_events()

    def bind_events(self):
        def accept_incoming(event):
            self.connection_handler.accept_incoming = True

        def disconnect_socks(event):
                self.connection_handler.accept_incoming = False

        self._tunnel.subscribe("on_ready", accept_incoming)
        self._tunnel.subscribe("on_down", disconnect_socks)


    def __init__(self, ):
        self.socks5_port = None
        self.raw_server = None

        self.udp_relay_socket = None

        self.connection_handler = TcpConnectionHandler()
        self.connection_handler.socks5_server = self

        self._tunnel = None
        self.bound = False

        self.routes = {}
        self.udp_relays = {}

    def attach_to(self, raw_server, socks5_port=1080):
        self.socks5_port = socks5_port
        self.raw_server = raw_server


    def start(self):
        if self.socks5_port:
            try:
                port = self.raw_server.find_and_bind(self.socks5_port, self.socks5_port, self.socks5_port + 10, ['0.0.0.0'],
                                                     reuse=True, handler=self)
                if self.tunnel:
                    self.bind_events()

                logger.error("Socks5Proxy binding to %s:%s", "0.0.0.0", port)
            except socket.error:
                logger.error("Cannot listen on SOCK5 port %s:%d, perhaps another instance is running?", "0.0.0.0",
                             self.socks5_port)

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
        :rtype : socket.socket
        """
        return self.raw_server.create_udpsocket(0, "0.0.0.0")

    def create_udp_relay(self):
        """
        Initializes an UDP relay by listening to a newly created socket and attaching a UdpRelayHandler
        :rtype : socket.socket
        """

        udp_relay_socket = self.create_udp_socket()
        handler = UdpRelayTunnelHandler(udp_relay_socket, self)
        self.start_listening_udp(udp_relay_socket, handler)

        return udp_relay_socket

    def start_listening_udp(self, udp_socket, handler):
        """
        Start listening on an UDP socket by attaching an event handler

        :param udp_socket: the socket to listen on
        :param handler: the handler to call when new packets are received on the UDP socket
        :return: None
        """

        self.raw_server.start_listening_udp(udp_socket, handler)

    def on_tunnel_data(self, event, data):
        # Some tricky stuff goes on here to figure out to which SOCKS5 client to return the data

        # First we get the origin (outside the tunnel) of the packet, we map this to the SOCKS5 clients IP
            # All will break if clients send data to the same peer, since we cant distinguish where the return packets
            # must go....

        # Now that we have the SOCKS5 client's address we can find the corresponding UDP socks5 relay used. This is
        # relay is created in response to UDP_ASSOCIATE request during the SOCKS5 initiation

        # The socket together with the destination address is enough to return the data

        packet = data

        source_address = packet.origin

        destination_address = self.routes.get(source_address, None)

        if destination_address is None:
            logger.error("Unknown peer, dont know what to do with it!")
            return

        socks5_socket = self.udp_relays.get(destination_address, None)

        if socks5_socket is None:
            logger.error("Dont know over which socket to return the data!")
            return

        encapsulated = Socks5.structs.encode_udp_packet(0, 0, Socks5.structs.ADDRESS_TYPE_IPV4, source_address[0],
                                                        source_address[1], packet.data)

        if socks5_socket.sendto(encapsulated, destination_address) < len(encapsulated):
            logger.error("Not sending package!")

        if __debug__:
            logger.info("Returning UDP packets from %s to %s using proxy port %d", source_address, destination_address,
                        socks5_socket.getsockname()[1])
