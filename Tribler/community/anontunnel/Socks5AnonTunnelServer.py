"""
Created on 3 jun. 2013

@author: Chris
"""

import logging

logger = logging.getLogger(__name__)

import socket
from Tribler.community.anontunnel.ConnectionHandlers.TcpConnectionHandler import TcpConnectionHandler
from traceback import print_exc
from threading import Thread, Event
from Tribler.Core.RawServer.RawServer import RawServer
from ConnectionHandlers.UdpRelayTunnelHandler import UdpRelayTunnelHandler

import Socks5.structs


class Socks5AnonTunnelServer(object):
    @property
    def tunnel(self):
        return self._tunnel

    @tunnel.setter
    def tunnel(self, value):
        self._tunnel = value
        self._tunnel.subscribe("on_data", self.on_tunnel_data)
        self._tunnel.socket_server = self


    def __init__(self, raw_server, socks5_port=1080, timeout=10.0):
        #Thread.__init__(self)
        #self.setDaemon(False)
        #self.setName('Socks5Server' + self.getName())
        self.socks5_port = socks5_port

        self.udp_relay_socket = None

        self.connection_handler = TcpConnectionHandler()
        self.connection_handler.server = self

        self.destination_address = None

        self._tunnel = None

        self.server_done_flag = Event()
        self.raw_server = raw_server




        try:
            port = self.raw_server.find_and_bind(self.socks5_port, self.socks5_port, self.socks5_port + 10, ['0.0.0.0'],
                                                 reuse=True)
            logger.info("Socks5Proxy binding to %s:%s", "0.0.0.0", port)
        except socket.error:
            logger.error("Cannot listen on SOCK5 port %s:%d, perhaps another instance is running?", "0.0.0.0",
                         socks5_port)


    def shutdown(self):
        self.connection_handler.shutdown()
        self.server_done_flag.set()

    def start(self):
        pass

    def run(self):
        try:
            try:
                self.raw_server.listen_forever(self)
            except Exception, e:
                if not isinstance(e, SystemExit):
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
        :rtype : socket.socket
        """
        return self.raw_server.create_udpsocket(0, "0.0.0.0")

    def create_udp_relay(self):
        """
        Initializes an UDP relay by listening to a newly created socket and attaching a UdpRelayHandler
        :rtype : socket.socket
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
        # We are not an endpoint of the tunnel so bail out
        if self.udp_relay_socket is None:
            msg = event.data
            logger.error("NOT ROUTABLE: Got an UDP packet from %s to %s", event.sender, msg.destination)
            return

        packet = event.data

        source_address = packet.origin

        destination_address = self.destination_address

        encapsulated = Socks5.structs.encode_udp_packet(0, 0, Socks5.structs.ADDRESS_TYPE_IPV4, source_address[0],
                                                        source_address[1], packet.data)
        if self.udp_relay_socket.sendto(encapsulated, destination_address) < len(encapsulated):
            logger.error("Not sending package!")

        logger.info("Returning UDP packets from %s to %s using proxy port %d", source_address, destination_address,
                    self.udp_relay_socket.getsockname()[1])
