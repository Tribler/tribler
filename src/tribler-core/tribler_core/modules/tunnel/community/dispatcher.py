import random
from collections import defaultdict

from ipv8.messaging.anonymization.tunnel import (
    CIRCUIT_ID_PORT,
    CIRCUIT_STATE_READY,
    CIRCUIT_TYPE_DATA,
    CIRCUIT_TYPE_RP_DOWNLOADER,
    CIRCUIT_TYPE_RP_SEEDER,
)
from ipv8.taskmanager import TaskManager, task

from tribler_core.modules.tunnel.socks5.conversion import UdpPacket, socks5_serializer


class TunnelDispatcher(TaskManager):
    """
    This class is responsible for dispatching SOCKS5 traffic to the right circuits and vice versa.
    This dispatcher acts as a "secondary" proxy between the SOCKS5 UDP session and the tunnel community.
    """

    def __init__(self, tunnels):
        super().__init__()
        self.tunnels = tunnels
        self.socks_servers = []

        # Map to keep track of the circuits associated with each destination.
        self.con_to_cir = defaultdict(dict)

        # Map to keep track of the circuit id to UDP connection.
        self.cid_to_con = {}

        self.register_task('check_connections', self.check_connections, interval=30)

    def set_socks_servers(self, socks_servers):
        self.socks_servers = socks_servers

    def on_incoming_from_tunnel(self, community, circuit, origin, data):
        """
        We received some data from the tunnel community. Dispatch it to the right UDP SOCKS5 socket.
        """
        if circuit.ctype in [CIRCUIT_TYPE_RP_DOWNLOADER, CIRCUIT_TYPE_RP_SEEDER]:
            origin = (community.circuit_id_to_ip(circuit.circuit_id), CIRCUIT_ID_PORT)

        try:
            connection = self.cid_to_con[circuit.circuit_id]
        except KeyError:
            session_hops = circuit.goal_hops if circuit.ctype != CIRCUIT_TYPE_RP_DOWNLOADER else circuit.goal_hops - 1
            if session_hops > len(self.socks_servers) or not self.socks_servers[session_hops - 1].sessions:
                self._logger.error("No connection found for %d hops", session_hops)
                return False
            connection = next((s for s in self.socks_servers[session_hops - 1].sessions
                               if s.udp_connection and s.udp_connection.remote_udp_address), None)

        if connection is None or connection.udp_connection is None:
            self._logger.error("Connection has closed or has not gotten an UDP associate")
            self.connection_dead(connection)
            return False

        packet = socks5_serializer.pack_serializable(UdpPacket(0, 0, origin, data))
        connection.udp_connection.send_datagram(packet)
        return True

    def on_socks5_udp_data(self, udp_connection, request):
        """
        We received some data from the SOCKS5 server (from the SOCKS5 client). This method
        selects a circuit to send this data over to the final destination.
        """
        circuit = None
        connection = udp_connection.socksconnection
        try:
            circuit = self.con_to_cir[connection][request.destination]
        except KeyError:
            circuit = circuit or self.select_circuit(connection, request)
            if circuit is None:
                return False

        if circuit.state != CIRCUIT_STATE_READY:
            self._logger.debug("Circuit not ready, dropping %d bytes to %s", len(request.data), request.destination)
            return False

        self._logger.debug("Sending data over circuit %d destined for %r:%r", circuit.circuit_id, *request.destination)
        self.tunnels.send_data(circuit.peer, circuit.circuit_id, request.destination, ('0.0.0.0', 0), request.data)
        return True

    @task
    async def on_socks5_tcp_data(self, tcp_connection, destination, request):
        self._logger.debug("Got request for %s: %s", destination, request)
        hops = self.socks_servers.index(tcp_connection.socksserver) + 1
        try:
            response = await self.tunnels.perform_http_request(destination, request, hops)
            self._logger.debug('Got response from %s: %s', destination, response)
        except RuntimeError as e:
            self._logger.info('Failed to get HTTP response using tunnels: %s', e)
            return

        if response:
            tcp_connection.transport.write(response)
        tcp_connection.transport.close()

    def select_circuit(self, connection, request):
        if request.destination[1] == CIRCUIT_ID_PORT:
            circuit = self.tunnels.circuits.get(self.tunnels.ip_to_circuit_id(request.destination[0]))
            if circuit and circuit.state == CIRCUIT_STATE_READY and circuit.ctype in [CIRCUIT_TYPE_RP_DOWNLOADER,
                                                                                      CIRCUIT_TYPE_RP_SEEDER]:
                return circuit

        hops = self.socks_servers.index(connection.socksserver) + 1
        options = [c for c in self.tunnels.circuits.values()
                   if c.goal_hops == hops and c.state == CIRCUIT_STATE_READY and c.ctype == CIRCUIT_TYPE_DATA
                   and self.cid_to_con.get(c.circuit_id, connection) == connection]
        if not options:
            # We allow each connection to claim at least 1 circuit. If no such circuit exists we'll create one.
            if connection in self.cid_to_con.values():
                self._logger.debug("No circuit for sending data to %s", request.destination)
                return None

            circuit = self.tunnels.create_circuit(goal_hops=hops)
            if circuit is None:
                self._logger.debug("Failed to create circuit for data to %s", request.destination)
                return None
            self._logger.debug("Creating circuit for data to %s. Retrying later..", request.destination)
            self.cid_to_con[circuit.circuit_id] = connection
            circuit.ready.add_done_callback(lambda f, c=connection.udp_connection, r=request:
                                            self.on_socks5_udp_data(c, r) if f.result() else None)
            return None

        circuit = random.choice(options)
        self.cid_to_con[circuit.circuit_id] = connection
        self.con_to_cir[connection][request.destination] = circuit
        self._logger.debug("Select circuit %d for %s", circuit.circuit_id, request.destination)
        return circuit

    def circuit_dead(self, broken_circuit):
        """
        When a circuit dies, we update the destinations dictionary and remove all peers that are affected.
        """
        con = self.cid_to_con.pop(broken_circuit.circuit_id, None)

        destinations = set()
        destination_to_circuit = self.con_to_cir.get(con, {})
        for destination, circuit in list(destination_to_circuit.items()):
            if circuit == broken_circuit:
                destination_to_circuit.pop(destination, None)
                destinations.add(destination)

        self._logger.debug("Deleted %d peers from destination list", len(destinations))
        return destinations

    def connection_dead(self, connection):
        self.con_to_cir.pop(connection, None)
        for cid, con in list(self.cid_to_con.items()):
            if con == connection:
                self.cid_to_con.pop(cid, None)
        self._logger.error("Detected closed connection")

    def check_connections(self):
        for connection in list(self.cid_to_con.values()):
            if not connection.udp_connection:
                self.connection_dead(connection)
