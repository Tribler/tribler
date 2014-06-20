import logging

from Tribler.community.tunnel.Socks5 import conversion
from Tribler.community.tunnel.Socks5.connection import Socks5ConnectionObserver
from Tribler.community.tunnel import CIRCUIT_STATE_READY


class RoundRobin(object):
    def __init__(self):
        self.index = -1

    def select(self, circuits):
        if not circuits:
            raise ValueError("Variable circuits  must be a dict of circuits")
        circuit_ids = sorted(circuits.keys())
        self.index = (self.index + 1) % len(circuit_ids)
        circuit_id = circuit_ids[self.index]
        return circuits[circuit_id]


class Socks5Session(Socks5ConnectionObserver):
    """
    A SOCKS5 session, composed by a TCP connection, an UDP proxy port and a
    list of circuits where data can be tunneled over

    @param Socks5Connection connection: the Socks5Connection
    @param RawServer raw_server: The raw server, used to create and listen on
    UDP-sockets
    """
    def __init__(self, raw_server, connection, server, community, min_circuits=4):
        self.raw_server = raw_server
        self._logger = logging.getLogger(__name__)
        self.connection = connection
        self.connection.observers.append(self)
        self.min_circuits = min_circuits
        self.server = server
        self.community = community
        self.destinations = {}
        self.selection_strategy = RoundRobin()
        self.remote_udp_address = None
        self._udp_socket = None
        self.torrents = {}

    def on_udp_associate_request(self, connection, request):
        """
        @param Socks5Connection connection: the connection
        @param request:
        @return:
        """
        if len(self.community.circuits) < self.min_circuits:
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

    def circuit_ready(self, circuit):
        # If no circuits were left before now, re-add the peers.

        for torrent, peers in self.torrents.items():
            for peer in peers:
                self._logger.error("Re-adding peer %s to torrent %s", peer, torrent.tdef.get_infohash().encode("HEX"))
                torrent.add_peer(peer)

    def circuit_dead(self, broken_circuit):
        """
        When a circuit breaks and it affects our operation we should re-add the
        peers when a new circuit is available to re-initiate the 3-way handshake

        @param Circuit broken_circuit: the circuit that has been broken
        @return:
        """
        from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr

        if not LibtorrentMgr.hasInstance():
            return

        affected_destinations = set(destination for destination, tunnel_circuit in self.destinations.iteritems() if tunnel_circuit == broken_circuit)

        # We are not affected by the circuit that has been broken, continue without any changes
        if not affected_destinations:
            return

        for destination in affected_destinations:
            if destination in self.destinations:
                del self.destinations[destination]
                self._logger.error("Deleting peer %s from destination list", destination)

        mgr = LibtorrentMgr.getInstance()
        anon_session = mgr.ltsession_anon
        affected_torrents = dict((download, affected_destinations.intersection(peer.ip for peer in download.handle.get_peer_info()))
                             for (download, session) in mgr.torrents.values() if session == anon_session)

        for download, peers in affected_torrents:
            if download not in self.torrents:
                self.torrents[download] = peers
            elif peers - self.torrents[download]:
                self.torrents[download] = peers | self.torrents[download]

        self._logger.warning("Waiting for new circuits before re-adding peers")

    def _select(self, destination):
        if not destination in self.destinations:
            selected_circuit = self.selection_strategy.select(self.community.active_circuits)
            self.destinations[destination] = selected_circuit

            self._logger.warning("SELECT circuit {0} for {1}".format(self.destinations[destination].circuit_id, \
                                                                     destination))

        return self.destinations[destination]

    def data_came_in(self, packets):
        for source_address, packet in packets:
            if self.remote_udp_address and self.remote_udp_address != source_address:
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
        if circuit not in self.community.circuits.values():
            return

        if not self.remote_udp_address:
            self._logger.warning("No return address yet, dropping packet!")
            return

        self.destinations[origin] = circuit

        socks5_udp = conversion.encode_udp_packet(0, 0, conversion.ADDRESS_TYPE_IPV4, origin[0], origin[1], data)

        bytes_written = self._udp_socket.sendto(socks5_udp, self.remote_udp_address)
        if bytes_written < len(socks5_udp):
            self._logger.error("Packet drop on return!")
