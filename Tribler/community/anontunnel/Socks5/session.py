import logging
from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
from Tribler.community.anontunnel.CircuitPool import NotEnoughCircuitsException
from Tribler.community.anontunnel.Socks5 import conversion
from Tribler.community.anontunnel.Socks5.connection import \
    Socks5ConnectionObserver
from Tribler.community.anontunnel.events import TunnelObserver
from Tribler.community.anontunnel.selectionstrategies import RoundRobin


class Socks5Session(TunnelObserver, Socks5ConnectionObserver):
    """
    A SOCKS5 session, composed by a TCP connection, an UDP proxy port and a
    list of circuits where data can be tunneled over

    @param Socks5Connection connection: the Socks5Connection
    @param RawServer raw_server: The raw server, used to create and listen on
    UDP-sockets
    @param CircuitPool circuit_pool:  the circuit pool
    """
    def __init__(self, raw_server, connection, server, circuit_pool):
        TunnelObserver.__init__(self)
        self.raw_server = raw_server
        self._logger = logging.getLogger(__name__)
        self.connection = connection
        self.connection.observers.append(self)
        self.circuit_pool = circuit_pool

        self.server = server

        self.destinations = {}
        ''' :type: dict[(str, int), Circuit] '''

        self.selection_strategy = RoundRobin()

        self.remote_udp_address = None
        self._udp_socket = None

    def on_udp_associate_request(self, connection, request):
        """
        @param Socks5Connection connection: the connection
        @param request:
        @return:
        """
        if not self.circuit_pool.available_circuits:
            try:
                circuit = self.server.circuit_pool.allocate()

                # Move from main pool to session pool
                self.server.circuit_pool.remove_circuit(circuit)
                self.circuit_pool.fill(circuit)
            except NotEnoughCircuitsException:
                self.close_session("not enough circuits")
                connection.deny_request(request)
                return

        self._udp_socket = self.raw_server.create_udpsocket(0, "0.0.0.0")
        self.raw_server.start_listening_udp(self._udp_socket, self)
        connection.accept_udp_associate(request, self._udp_socket)

    def close_session(self, reason='unspecified'):
        """
        Closes the session and the linked TCP connection
        @param str reason: the reason why the session should be closed
        """
        self._logger.error("Closing session, reason = {0}".format(reason))
        self.connection.close()

    def on_break_circuit(self, circuit):
        if circuit in {circuit for dest, circuit in self.destinations.iteritems()}:
            self._logger.error(
                "A circuit has died, to enforce 3-way swift handshake "
                "we are signalling swift by closing TCP connection")
            self.close_session()

    def _select(self, destination):
        if not destination in self.destinations:
            selected_circuit = self.selection_strategy.select(self.circuit_pool.available_circuits)
            self.destinations[destination] = selected_circuit

            self._logger.error("SELECT circuit {0} for {1}".format(
                self.destinations[destination].circuit_id,
                destination
            ))

        return self.destinations[destination]

    def data_came_in(self, packets):
        for source_address, packet in packets:
            if self.remote_udp_address and \
                    self.remote_udp_address != source_address:
                self.close_session('invalid source_address!')
                return

            self.remote_udp_address = source_address

            request = conversion.decode_udp_packet(packet)

            circuit = self._select(request.destination)
            self._logger.info(
                "Relaying UDP packets from {0} to {1}".format(
                    self.remote_udp_address, request.destination
                )
            )

            circuit.tunnel_data(request.destination, request.payload)

    def on_incoming_from_tunnel(self, community, circuit, origin, data):
        if circuit not in self.circuit_pool.circuits:
            return

        if not self.remote_udp_address:
            self._logger.warning("No return address yet, dropping packet!")
            return

        self.destinations[origin] = circuit

        socks5_udp = conversion.encode_udp_packet(
            0, 0, conversion.ADDRESS_TYPE_IPV4, origin[0], origin[1], data)

        bytes_written = self._udp_socket.sendto(socks5_udp,
                                                self.remote_udp_address)
        if bytes_written < len(socks5_udp):
            self._logger.error("Packet drop on return!")

        self._logger.info(
            "Returning UDP packets from %s to %s using proxy port %d",
            origin, self.remote_udp_address,
            self._udp_socket.getsockname()[1])
