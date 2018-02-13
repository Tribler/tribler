import logging

from Tribler.Core.Socks5 import conversion
from Tribler.community.tunnel import CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP, CIRCUIT_ID_PORT, CIRCUIT_STATE_READY


class TunnelDispatcher(object):
    """
    This class is responsible for dispatching SOCKS5 traffic to the right circuits and vice versa.
    This dispatcher acts as a "secondary" proxy between the SOCKS5 UDP session and the tunnel community.
    """

    def __init__(self, tunnel_community):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tunnel_community = tunnel_community
        self.socks_servers = []

        # Map to keep track of the circuits associated with each destination.
        self.destinations = {}

    def set_socks_servers(self, socks_servers):
        self.socks_servers = socks_servers
        self.destinations = {(ind + 1): {} for ind, _ in enumerate(self.socks_servers)}

    def on_incoming_from_tunnel(self, community, circuit, origin, data, force=False):
        """
        We received some data from the tunnel community. Dispatch it to the right UDP SOCKS5 socket.
        """
        if circuit.ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
            origin = (community.circuit_id_to_ip(circuit.circuit_id), CIRCUIT_ID_PORT)
        session_hops = circuit.goal_hops if circuit.ctype != CIRCUIT_TYPE_RENDEZVOUS else circuit.goal_hops - 1

        if session_hops > len(self.socks_servers):
            self._logger.error("No socks server found for %d hops", session_hops)
            return False

        sock_server = self.socks_servers[session_hops - 1]

        destinations = self.destinations[session_hops]
        if circuit in destinations.values() or force:
            destinations[origin] = circuit

            for session in sock_server.sessions:
                if session._udp_socket:
                    socks5_data = conversion.encode_udp_packet(
                        0, 0, conversion.ADDRESS_TYPE_IPV4, origin[0], origin[1], data)
                    self._logger.debug(
                        "    ??? ->    %s:%d  %d bytes local ('%s', %d) circuit_id %d",
                        session._udp_socket.remote_udp_address[0], session._udp_socket.remote_udp_address[1],
                        len(data),
                        session._udp_socket.transport.getHost().host,
                        session._udp_socket.transport.getHost().port,
                        circuit.circuit_id)
                    return session._udp_socket.sendDatagram(socks5_data)
                else:
                    self._logger.error("UDP socket for socks server not available!")

        return False

    def on_socks5_udp_data(self, udp_connection, request):
        """
        We received some data from the SOCKS5 server (from libtorrent). This methods selects a circuit to
        send this data over to the final destination.
        """
        hops = self.socks_servers.index(udp_connection.socksconnection.socksserver) + 1

        destination = request.destination
        if destination not in self.destinations[hops]:
            selected_circuit = self.tunnel_community.selection_strategy.select(destination, hops)
            if not selected_circuit:
                return False

            self.destinations[hops][destination] = selected_circuit
            self._logger.info("SELECT circuit %d for %s", self.destinations[hops][destination].circuit_id,
                              destination)
        circuit = self.destinations[hops][destination]

        if circuit.state != CIRCUIT_STATE_READY:
            self._logger.debug(
                "Circuit is not ready, dropping %d bytes to %s", len(request.payload), request.destination)
            return False

        self._logger.debug("Sending data over circuit destined for %r:%r", *request.destination)
        self._logger.debug("    ??? <-    %s:%d  %d bytes local ('%s', %d) circuit_id %d",
                           udp_connection.remote_udp_address[0],
                           udp_connection.remote_udp_address[1],
                           len(request.payload),
                           udp_connection.transport.getHost().host,
                           udp_connection.transport.getHost().port,
                           circuit.circuit_id)
        circuit.tunnel_data(request.destination, request.payload)
        return True

    def circuit_dead(self, broken_circuit):
        """
        When a circuit dies, we update the destinations dictionary and remove all peers that are affected.
        """
        counter = 0
        affected_destinations = set()
        for hops, destinations in self.destinations.iteritems():
            new_affected_destinations = set(destination for destination, tunnel_circuit in destinations.iteritems()
                                            if tunnel_circuit == broken_circuit)
            for destination in new_affected_destinations:
                if destination in self.destinations[hops]:
                    del self.destinations[hops][destination]
                    counter += 1

            affected_destinations.update(new_affected_destinations)

        if counter > 0:
            self._logger.debug("Deleted %d peers from destination list", counter)

        return affected_destinations
