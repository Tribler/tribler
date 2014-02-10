"""
Created on 3 jun. 2013

@author: Chris
"""

import logging
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from Tribler.community.anontunnel.community import TunnelObserver
import structs
from connection import Socks5Connection

logger = logging.getLogger(__name__)

import socket
from traceback import print_exc


class Socks5Server(object, TunnelObserver):

    def __init__(self):
        self._tunnel = None
        self._accept_incoming = False

        self.socket2connection = {}
        self.socks5_port = None
        self.raw_server = None

        self.udp_relay_socket = None
        self.bound = False

        self.routes = {}
        self.udp_relays = {}

    @property
    def accept_incoming(self):
        return self._accept_incoming

    @accept_incoming.setter
    def accept_incoming(self, value):
        if value and not self._accept_incoming:
            logger.info("Accepting SOCKS5 connections now!")

        if not value:
            logger.info("DISCONNECTING SOCKS5 !")

            for key in self.socket2connection.keys():
                self.socket2connection[key].close()

                if key in self.socket2connection:
                    del self.socket2connection[key]

        self._accept_incoming = value

    @property
    def tunnel(self):
        ''' :rtype : Tribler.community.anontunnel.community.ProxyCommunity '''
        return self._tunnel

    @tunnel.setter
    def tunnel(self, value):
        self._tunnel = value
        self.tunnel.add_observer(self)

    def attach_to(self, raw_server, socks5_port=1080):
        self.socks5_port = socks5_port
        self.raw_server = raw_server

    def start(self):
        if self.socks5_port:
            try:
                port = self.raw_server.find_and_bind(self.socks5_port, self.socks5_port, self.socks5_port + 10, ['0.0.0.0'],
                                                     reuse=True, handler=self)

                logger.info("Socks5Proxy binding to %s:%s", "0.0.0.0", port)
            except socket.error:
                logger.error("Cannot listen on SOCK5 port %s:%d, perhaps another instance is running?", "0.0.0.0",
                             self.socks5_port)

    def start_connection(self, dns):
        return self.raw_server.start_connection_raw(dns, handler=self.connection_handler)

    def create_udp_relay(self):
        """
        Initializes an UDP relay by listening to a newly created socket and attaching a UdpRelayHandler
        :rtype : socket.socket
        """

        server = self
        udp_relay_socket = self.raw_server.create_udpsocket(0, "0.0.0.0")

        class UdpRelayTunnelHandler:
            def data_came_in(self, packets):
                server.on_client_udp_packets(udp_relay_socket, packets)

        self.raw_server.start_listening_udp(udp_relay_socket, UdpRelayTunnelHandler())

        return udp_relay_socket

    def on_client_udp_packets(self, socket, packets):
        for source_address, packet in packets:
            request = structs.decode_udp_packet(packet)

            self.udp_relays[source_address] = socket

            logger.debug("Relaying UDP packets from %s:%d to %s:%d", source_address[0], source_address[1],
                        request.destination_address, request.destination_port)

            self.routes[(request.destination_address, request.destination_port)] = source_address
            self.tunnel.send_data(
                ultimate_destination=(request.destination_address, request.destination_port),
                payload=request.payload
            )

    def on_incoming_from_tunnel(self, community, circuit_id, source_address, data):
        # Some tricky stuff goes on here to figure out to which SOCKS5 client to return the data

        # First we get the origin (outside the tunnel) of the packet, we map this to the SOCKS5 clients IP
            # All will break if clients send data to the same peer, since we cant distinguish where the return packets
            # must go....

        # Now that we have the SOCKS5 client's address we can find the corresponding UDP socks5 relay used. This is
        # relay is created in response to UDP_ASSOCIATE request during the SOCKS5 initiation

        # The socket together with the destination address is enough to return the data
        destination_address = self.routes.get(source_address, None)

        if destination_address is None:
            logger.error("Unknown peer, dont know what to do with it!")
            return

        socks5_socket = self.udp_relays.get(destination_address, None)

        if socks5_socket is None:
            logger.error("Dont know over which socket to return the data!")
            return

        encapsulated = structs.encode_udp_packet(0, 0, structs.ADDRESS_TYPE_IPV4, source_address[0],
                                                        source_address[1], data)

        if socks5_socket.sendto(encapsulated, destination_address) < len(encapsulated):
            logger.error("Not sending package!")

        logger.info("Returning UDP packets from %s to %s using proxy port %d", source_address, destination_address,
                    socks5_socket.getsockname()[1])

    def external_connection_made(self, s):
        if not self.accept_incoming:
            s.close()
            return

        assert isinstance(s, SingleSocket)
        logger.info("accepted a socket on port %d", s.get_myport())

        self.socket2connection[s] = Socks5Connection(s, self)

    def connection_flushed(self, s):
        pass

    def connection_lost(self, s):
        logger.info("Connection lost")

        tcp_connection = self.socket2connection[s]

        destinations = self.routes.keys()
        self.tunnel.unlink_destinations(destinations)

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

    def on_state_change(self, community, state):
        self.accept_incoming = state
