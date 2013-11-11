"""
Created on 3 jun. 2013

@author: Chris
"""

import logging
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from Tribler.community.anontunnel.ConnectionHandlers.Socks5Connection import Socks5Connection
from Tribler.community.anontunnel.ConnectionHandlers.TcpRelayConnection import TcpRelayConnection

logger = logging.getLogger(__name__)

import socket
from traceback import print_exc
from ConnectionHandlers.UdpRelayTunnelHandler import UdpRelayTunnelHandler

import Socks5.structs


class Socks5Server(object):
    @property
    def accept_incoming(self):
        return self._accept_incoming

    @accept_incoming.setter
    def accept_incoming(self, value):
        if value and not self._accept_incoming:
            logger.error("Accepting SOCKS5 connections now!")

        if not value:
            logger.error("DISCONNECTING SOCKS5 !")

            for key in self.socket2connection.keys():
                self.socket2connection[key].close()

                if key in self.socket2connection:
                    del self.socket2connection[key]

        self._accept_incoming = value

    @property
    def tunnel(self):
        ''' :rtype : DispersyTunnelProxy '''
        return self._tunnel

    @tunnel.setter
    def tunnel(self, value):
        self._tunnel = value
        self._tunnel.subscribe("on_data", self.on_tunnel_data)

        if self.bound:
            self.bind_events()

    def bind_events(self):
        def accept_incoming(event):
            self.accept_incoming = True

        def disconnect_socks(event):
                self.accept_incoming = False

        self._tunnel.subscribe("on_ready", accept_incoming)
        self._tunnel.subscribe("on_down", disconnect_socks)


    def __init__(self, ):
        self._tunnel = None

        self._accept_incoming = False

        self.socket2connection = {}
        self.socks5_port = None
        self.raw_server = None

        self.udp_relay_socket = None
        self.bound = False

        self.routes = {}
        self.udp_relays = {}

        self.toggle_recording_on_first_enter = False


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


    def add_task(self, func, t):
        self.raw_server.add_task(func, t)

    def start_connection(self, dns):
        return self.raw_server.start_connection_raw(dns, handler=self.connection_handler)

    def create_udp_relay(self):
        """
        Initializes an UDP relay by listening to a newly created socket and attaching a UdpRelayHandler
        :rtype : socket.socket
        """

        udp_relay_socket = self.raw_server.create_udpsocket(0,"0.0.0.0")
        handler = UdpRelayTunnelHandler(udp_relay_socket, self)
        self.raw_server.start_listening_udp(udp_relay_socket, handler)

        return udp_relay_socket

    def on_tunnel_data(self, event, data, sender=None):
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

    def external_connection_made(self, s):
        # Extra check in case bind() no work

        if not self.accept_incoming:
            s.close()
            return

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
        self.tunnel.clear_state()

        try:
            tcp_connection.close()
        except:
            pass

        if s in self.socket2connection:
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

    def enter_tunnel_data(self, ultimate_destination, payload):
        if self.toggle_recording_on_first_enter:
            self.tunnel.record_stats = True

        self.tunnel.send_data(
            ultimate_destination=ultimate_destination,
            payload=payload
        )