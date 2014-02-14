import logging
import structs
from Tribler.community.anontunnel.community import ProxyCommunity, Circuit, \
    TunnelObserver

logger = logging.getLogger()


class Socks5Session(TunnelObserver):
    def __init__(self, raw_server, connection, circuits):
        """
        @param Socks5Connection connection: the Socks5Connection
        @param ProxyCommunity tunnel: The proxy community where we will tunnel
            our UDP packets ofver
        @return:
        """

        TunnelObserver.__init__(self)
        self.raw_server = raw_server
        self.connection = connection
        self.circuits = circuits
        ''' :type : list[Circuit] '''
        self.destinations = {}
        ''' :type: dict[(str, int), Circuit] '''
        self.connection.udp_associate = self._udp_associate
        self.remote_udp_address = None
        self._udp_socket = None

        self._select_index = -1

    def _udp_associate(self):
        self._udp_socket = self.raw_server.create_udpsocket(0, "0.0.0.0")
        session = self

        class UdpRelayTunnelHandler:
            @staticmethod
            def data_came_in(packets):
                for source_address, packet in packets:
                    if session.remote_udp_address and \
                            session.remote_udp_address != source_address:
                        session.close_session('invalid source_address!')
                        return

                    session.remote_udp_address = source_address

                    request = structs.decode_udp_packet(packet)
                    session.proxy_udp(
                        (request.destination_host, request.destination_port),
                        request.payload)

        self.raw_server.start_listening_udp(self._udp_socket,
                                            UdpRelayTunnelHandler())

        return self._udp_socket

    def close_session(self, reason='unspecified'):
        logger.error("Closing session, reason = {0}".format(reason))
        self.connection.close()

    def on_break_circuit(self, circuit):
        if circuit in self.circuits:
            logger.error("A circuit has died, to enforce 3-way swift handshake"
                         " we are signalling swift by closing TCP connection")
            self.close_session()

    def _select(self, destination):

        if not destination in self.destinations:
            self._select_index = (self._select_index + 1) % len(self.circuits)
            self.destinations[destination] = self.circuits[self._select_index]

            logger.error("SELECT circuit {0} for {1}".format(
                self.destinations[destination].circuit_id,
                destination
            ))

        return self.destinations[destination]

    def proxy_udp(self, destination, payload):
        circuit = self._select(destination)
        logger.debug("Relaying UDP packets from %s:%d to %s:%d",
                     self.remote_udp_address[0], self.remote_udp_address[1],
                     *destination)

        return circuit.tunnel_data(destination, payload)

    def on_incoming_from_tunnel(self, community, circuit, origin, data):

        # if origin not in self.destinations:
        self.destinations[origin] = circuit

        encapsulated = structs.encode_udp_packet(
            0, 0, structs.ADDRESS_TYPE_IPV4, origin[0], origin[1], data)

        bytes_written = self._udp_socket.sendto(encapsulated,
                                                self.remote_udp_address)
        if bytes_written < len(encapsulated):
            logger.error("Packet drop on return!")

        logger.info("Returning UDP packets from %s to %s using proxy port %d",
                    origin, self.remote_udp_address,
                    self._udp_socket.getsockname()[1])
