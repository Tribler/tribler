import logging

from twisted.internet import reactor
from twisted.internet.defer import DeferredList, maybeDeferred
from twisted.internet.protocol import Protocol, DatagramProtocol, connectionDone, Factory

from Tribler.community.tunnel import CIRCUIT_STATE_READY, CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP, CIRCUIT_ID_PORT
from Tribler.community.tunnel.Socks5 import conversion


class ConnectionState(object):

    """
    Enumeration of possible SOCKS5 connection states
    """

    BEFORE_METHOD_REQUEST = 'BEFORE_METHOD_REQUEST'
    METHOD_REQUESTED = 'METHOD_REQUESTED'
    CONNECTED = 'CONNECTED'
    PROXY_REQUEST_RECEIVED = 'PROXY_REQUEST_RECEIVED'
    PROXY_REQUEST_ACCEPTED = 'PROXY_REQUEST_ACCEPTED'
    TCP_RELAY = 'TCP_RELAY'


class SocksUDPConnection(DatagramProtocol):

    def __init__(self, socksconnection, remote_udp_address):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksconnection = socksconnection

        if remote_udp_address != ("0.0.0.0", 0):
            self.remote_udp_address = remote_udp_address
        else:
            self.remote_udp_address = None

        self.listen_port = reactor.listenUDP(0, self)

    def get_listen_port(self):
        return self.listen_port.getHost().port

    def sendDatagram(self, data):
        if self.remote_udp_address:
            self.transport.write(data, self.remote_udp_address)
        else:
            self._logger.error("cannot send data, no clue where to send it to")

    def datagramReceived(self, data, source):
        # if remote_address was not set before, use first one
        if self.remote_udp_address is None:
            self.remote_udp_address = source

        if self.remote_udp_address == source:
            try:
                request = conversion.decode_udp_packet(data)
            except conversion.IPV6AddrError:
                self._logger.warning("Received an IPV6 udp datagram, dropping it (Not implemented yet)")
                return

            if request.frag == 0:
                circuit = self.socksconnection.select(request.destination)

                if not circuit:
                    self._logger.debug(
                        "No circuits available, dropping %d bytes to %s", len(request.payload), request.destination)
                elif circuit.state != CIRCUIT_STATE_READY:
                    self._logger.debug(
                        "Circuit is not ready, dropping %d bytes to %s", len(request.payload), request.destination)
                else:
                    self._logger.debug("Sending data over circuit destined for %r:%r", *request.destination)
                    circuit.tunnel_data(request.destination, request.payload)
            else:
                self._logger.debug("No support for fragmented data, dropping")
        else:
            self._logger.debug("Ignoring data from %s:%d, is not %s:%d",
                               source[0], source[1], self.remote_udp_address[0], self.remote_udp_address[1])

    def close(self):
        if self.listen_port:
            self.listen_port.stopListening()
            self.listen_port = None


class Socks5Connection(Protocol):

    """
    SOCKS5 TCP Connection handler

    Supports a subset of the SOCKS5 protocol, no authentication and no support
    for TCP BIND requests
    """

    def __init__(self, socksserver, selection_strategy, hops):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksserver = socksserver
        self.selection_strategy = selection_strategy
        self.hops = hops

        self._udp_socket = None
        self.state = ConnectionState.BEFORE_METHOD_REQUEST
        self.buffer = ''

        self.destinations = {}

    def dataReceived(self, data):
        self.buffer = self.buffer + data
        while len(self.buffer) > 0:
            # We are at the initial state, so we expect a handshake request.
            if self.state == ConnectionState.BEFORE_METHOD_REQUEST:
                if not self._try_handshake():
                    break  # Not enough bytes so wait till we got more

            # We are connected so the
            elif self.state == ConnectionState.CONNECTED:
                if not self._try_request():
                    break  # Not enough bytes so wait till we got more
            else:
                self.logger.error("Throwing away buffer, not in CONNECTED or BEFORE_METHOD_REQUEST state")
                self.buffer = ''

    def _try_handshake(self):
        """
        Try to read a HANDSHAKE request

        :return: False if command could not been processes due to lack of bytes, True otherwise
        """
        offset, request = conversion.decode_methods_request(0, self.buffer)

        # No (complete) HANDSHAKE received, so dont do anything
        if request is None:
            return False

        assert isinstance(request, conversion.MethodRequest), request

        # Consume the buffer
        self.buffer = self.buffer[offset:]

        # Only accept NO AUTH
        if request.version != 0x05 or 0x00 not in request.methods:
            self._logger.error("Client has sent INVALID METHOD REQUEST")
            self.buffer = ''
            self.close()

        else:
            self._logger.info("Client has sent METHOD REQUEST")

            # Respond that we would like to use NO AUTHENTICATION (0x00)
            if self.state is not ConnectionState.CONNECTED:
                response = conversion.encode_method_selection_message(conversion.SOCKS_VERSION, 0x00)
                self.transport.write(response)

            # We are connected now, the next incoming message will be a REQUEST
            self.state = ConnectionState.CONNECTED
            return True

    def _try_request(self):
        """
        Try to consume a REQUEST message and respond whether we will accept the
        request.

        Will setup a TCP relay or an UDP socket to accommodate TCP RELAY and
        UDP ASSOCIATE requests. After a TCP relay is set up the handler will
        deactivate itself and change the Connection to a TcpRelayConnection.
        Further data will be passed on to that handler.

        :return: False if command could not been processes due to lack of bytes, True otherwise
        """
        self._logger.debug("Client has sent PROXY REQUEST")

        offset, request = conversion.decode_request(0, self.buffer)

        if request is None:
            return False

        self.buffer = self.buffer[offset:]

        assert isinstance(request, conversion.Request)
        self.state = ConnectionState.PROXY_REQUEST_RECEIVED

        try:
            if request.cmd == conversion.REQ_CMD_UDP_ASSOCIATE:
                self.on_udp_associate_request(self, request)

            elif request.cmd == conversion.REQ_CMD_BIND:
                response = conversion.encode_reply(0x05, conversion.REP_SUCCEEDED, 0x00,
                                                   conversion.ADDRESS_TYPE_IPV4, "127.0.0.1", 1081)

                self.transport.write(response)
                self.state = ConnectionState.PROXY_REQUEST_ACCEPTED

            elif request.cmd == conversion.REQ_CMD_CONNECT:
                self._logger.info("TCP req to %s:%d support it. Returning HOST UNREACHABLE",
                                  *request.destination)

                response = conversion.encode_reply(0x05, conversion.REP_HOST_UNREACHABLE, 0x00,
                                                   conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)
                self.transport.write(response)

            else:
                self.deny_request(request, "CMD not recognized")

        except:
            response = conversion.encode_reply(0x05, conversion.REP_COMMAND_NOT_SUPPORTED, 0x00,
                                               conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)
            self.transport.write(response)
            self._logger.exception("Exception thrown, returning unsupported command response")

        return True

    def deny_request(self, request, reason):
        """
        Deny SOCKS5 request
        @param Request request: the request to deny
        """
        self.state = ConnectionState.CONNECTED

        response = conversion.encode_reply(0x05, conversion.REP_COMMAND_NOT_SUPPORTED, 0x00,
                                           conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)

        self.transport.write(response)
        self._logger.error("DENYING SOCKS5 request, reason: %s" % reason)

    def on_udp_associate_request(self, connection, request):
        # The DST.ADDR and DST.PORT fields contain the address and port that the client expects
        # to use to send UDP datagrams on for the association.  The server MAY use this information
        # to limit access to the association.
        self._udp_socket = SocksUDPConnection(self, request.destination)
        ip = self.transport.getHost().host
        port = self._udp_socket.get_listen_port()

        self._logger.info("Accepting UDP ASSOCIATE request to %s:%d", ip, port)

        response = conversion.encode_reply(
            0x05, conversion.REP_SUCCEEDED, 0x00, conversion.ADDRESS_TYPE_IPV4, ip, port)
        self.transport.write(response)

    def select(self, destination):
        if destination not in self.destinations:
            selected_circuit = self.selection_strategy.select(destination, self.hops)
            if not selected_circuit:
                return None

            self.destinations[destination] = selected_circuit
            self._logger.info("SELECT circuit {0} for {1}".format(self.destinations[destination].circuit_id,
                                                                  destination))
        return self.destinations[destination]

    def circuit_dead(self, broken_circuit):
        """
        When a circuit breaks and it affects our operation we should re-add the
        peers when a new circuit is available

        @param Circuit broken_circuit: the circuit that has been broken
        @return Set with destinations using this circuit
        """
        affected_destinations = set(
            destination for destination, tunnel_circuit in self.destinations.iteritems() if tunnel_circuit == broken_circuit)
        counter = 0
        for destination in affected_destinations:
            if destination in self.destinations:
                del self.destinations[destination]
                counter += 1

        if counter > 0:
            self._logger.debug("Deleted %d peers from destination list", counter)

        return affected_destinations

    def on_incoming_from_tunnel(self, community, circuit, origin, data, force=False):
        if circuit in self.destinations.values() or force:
            self.destinations[origin] = circuit

            if self._udp_socket:
                socks5_data = conversion.encode_udp_packet(
                    0, 0, conversion.ADDRESS_TYPE_IPV4, origin[0], origin[1], data)
                self._udp_socket.sendDatagram(socks5_data)
                return True
        return False

    def connectionLost(self, reason=connectionDone):
        self.socksserver.connectionLost(self)

    def close(self, reason='unspecified'):
        self._logger.info("Closing session, reason %s", reason)
        if self._udp_socket:
            self._udp_socket.close()
            self._udp_socket = None

        self.transport.loseConnection()


class Socks5Server(object):

    def __init__(self, community, socks5_ports):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.community = community
        self.socks5_ports = socks5_ports
        self.twisted_ports = []
        self.sessions = []

    def start(self):
        for i, port in enumerate(self.socks5_ports):
            factory = Factory()
            factory.buildProtocol = lambda addr, hops = i + 1: self.buildProtocol(addr, hops)
            self.twisted_ports.append(reactor.listenTCP(port, factory))

    def stop(self):
        deferred_list = []

        if self.twisted_ports:
            for session in self.sessions:
                session.close('stopping')
            self.sessions = []

            for twisted_port in self.twisted_ports:
                deferred_list.append(maybeDeferred(twisted_port.stopListening))
            self.twisted_ports = []

        return DeferredList(deferred_list)

    def buildProtocol(self, addr, hops):
        socks5connection = Socks5Connection(self, self.community.selection_strategy, hops)
        self.sessions.append(socks5connection)
        return socks5connection

    def connectionLost(self, socks5connection):
        self._logger.debug("SOCKS5 TCP connection lost")
        if socks5connection in self.sessions:
            self.sessions.remove(socks5connection)

        socks5connection.close()

    def circuit_dead(self, circuit):
        affected_destinations = set()
        for session in self.sessions:
            affected_destinations.update(session.circuit_dead(circuit))

        return affected_destinations

    def on_incoming_from_tunnel(self, community, circuit, origin, data, force=False):
        if circuit.ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
            origin = (community.circuit_id_to_ip(circuit.circuit_id), CIRCUIT_ID_PORT)
        session_hops = circuit.goal_hops if circuit.ctype != CIRCUIT_TYPE_RENDEZVOUS else circuit.goal_hops - 1

        if not any([session.on_incoming_from_tunnel(community, circuit, origin, data, force)
                    for session in self.sessions if session.hops == session_hops]):
            self._logger.warning("No session accepted this data from %s:%d", *origin)
