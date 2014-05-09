import logging
from Tribler.community.anontunnel.Socks5 import conversion
from Tribler.community.anontunnel.Socks5.connection import \
    Socks5ConnectionObserver
from Tribler.community.anontunnel.events import TunnelObserver, \
    CircuitPoolObserver
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY
from Tribler.community.anontunnel.routing import NotEnoughCircuitsException
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
    def __init__(self, raw_server, connection, server, circuit_pool, min_circuits=4):
        TunnelObserver.__init__(self)
        self.raw_server = raw_server
        self._logger = logging.getLogger(__name__)
        self.connection = connection
        self.connection.observers.append(self)
        self.circuit_pool = circuit_pool

        self.min_circuits = min_circuits

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
                for _ in range(self.min_circuits):
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

    def on_break_circuit(self, broken_circuit):
        """
        When a circuit breaks and it affects our operation we should re-add the
        peers when a new circuit is available to reinitiate the 3-way handshake

        @param Circuit broken_circuit: the circuit that has been broken
        @return:
        """
        affected_destinations = set(destination
                                    for destination, tunnel_circuit
                                    in self.destinations.iteritems()
                                    if tunnel_circuit == broken_circuit)

        # We are not affected by the circuit that has been broken, continue
        # without any changes
        if not affected_destinations:
            return

        from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
        mgr = LibtorrentMgr.getInstance()
        anon_session = mgr.ltsession_anon
        ''' :type : libtorrent.session '''

        affected_torrents = dict((download, affected_destinations.intersection(peer.ip for peer in download.handle.get_peer_info()))
                             for infohash, (download, session)
                             in mgr.torrents.items()
                             if session == anon_session
                             )
        ''' :type : dict[LibtorrentDownloadImpl, set[(str, int)] '''

        def _peer_add():
            for destination in affected_destinations:
                if destination in self.destinations:
                    del self.destinations[destination]
                    self._logger.error("Deleting peer %s from destination list", destination)

            for torrent, peers in affected_torrents.items():
                for peer in peers:
                    self._logger.error("Readding peer %s to torrent %s", peer, torrent.tdef.get_infohash().encode("HEX"))
                    torrent.add_peer(peer)

        # Observer that waits for a new circuit before re-adding the peers
        # is used only when there are no other circuits left
        class _peer_adder(CircuitPoolObserver):
            def on_circuit_added(self, pool, circuit):
                _peer_add()
                pool.observers.remove(self)

        # If there are any other circuits we will just map them to any
        # new circuit
        if [circuit for circuit in self.circuit_pool.available_circuits if circuit != broken_circuit]:
            _peer_add()
        else:
            self._logger.warning("Waiting for new circuits before re-adding peers")
            self.circuit_pool.observers.append(_peer_adder())

    def _select(self, destination):
        if not destination in self.destinations:
            selected_circuit = self.selection_strategy.select(self.circuit_pool.available_circuits)
            self.destinations[destination] = selected_circuit

            self._logger.warning("SELECT circuit {0} for {1}".format(
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

            if circuit.state != CIRCUIT_STATE_READY:
                self._logger.error("Circuit is not ready, dropping %d bytes to %s", len(request.payload), request.destination)
            else:
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
