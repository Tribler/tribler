import logging
from asyncio import Protocol, ensure_future

from ipv8.messaging.serialization import PackError

from tribler_core.modules.tunnel.socks5.conversion import (
    CommandRequest,
    CommandResponse,
    MethodsRequest,
    MethodsResponse,
    REP_COMMAND_NOT_SUPPORTED,
    REP_SUCCEEDED,
    REQ_CMD_BIND,
    REQ_CMD_CONNECT,
    REQ_CMD_UDP_ASSOCIATE,
    SOCKS_VERSION,
    socks5_serializer,
)
from tribler_core.modules.tunnel.socks5.udp_connection import SocksUDPConnection


class ConnectionState(object):
    """
    Enumeration of possible SOCKS5 connection states
    """

    BEFORE_METHOD_REQUEST = 'BEFORE_METHOD_REQUEST'
    METHOD_REQUESTED = 'METHOD_REQUESTED'
    CONNECTED = 'CONNECTED'
    PROXY_REQUEST_RECEIVED = 'PROXY_REQUEST_RECEIVED'
    PROXY_REQUEST_ACCEPTED = 'PROXY_REQUEST_ACCEPTED'


class Socks5Connection(Protocol):
    """
    SOCKS5 TCP Connection handler

    Supports a subset of the SOCKS5 protocol, no authentication and no support for TCP BIND requests
    """

    def __init__(self, socksserver):
        super(Socks5Connection, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksserver = socksserver
        self.transport = None
        self.connect_to = None

        self.udp_connection = None
        self.state = ConnectionState.BEFORE_METHOD_REQUEST
        self.buffer = b''

        self.destinations = {}

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
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
            elif self.connect_to:
                self.socksserver.output_stream.on_socks5_tcp_data(self, self.connect_to, self.buffer)
                self.buffer = b''
            else:
                self._logger.error("Throwing away buffer, not in CONNECTED or BEFORE_METHOD_REQUEST state")
                self.buffer = b''

    def _try_handshake(self):
        """
        Try to read a HANDSHAKE request

        :return: False if command could not been processes due to lack of bytes, True otherwise
        """
        try:
            request, offset = socks5_serializer.unpack_serializable(MethodsRequest, self.buffer)
        except PackError:
            # No (complete) HANDSHAKE received, so dont do anything
            return False

        # Consume the buffer
        self.buffer = self.buffer[offset:]

        # Only accept NO AUTH
        if request.version != SOCKS_VERSION or 0x00 not in request.methods:
            self._logger.error("Client has sent INVALID METHOD REQUEST")
            self.buffer = ''
            self.close()
        else:
            self._logger.info("Client has sent METHOD REQUEST")

            # Respond that we would like to use NO AUTHENTICATION (0x00)
            if self.state is not ConnectionState.CONNECTED:
                response = socks5_serializer.pack_serializable(MethodsResponse(SOCKS_VERSION, 0))
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

        try:
            request, offset = socks5_serializer.unpack_serializable(CommandRequest, self.buffer)
        except PackError:
            return False

        self.buffer = self.buffer[offset:]

        self.state = ConnectionState.PROXY_REQUEST_RECEIVED

        try:
            if request.cmd == REQ_CMD_UDP_ASSOCIATE:
                ensure_future(self.on_udp_associate_request(request))

            elif request.cmd == REQ_CMD_BIND:
                payload = CommandResponse(SOCKS_VERSION, REP_SUCCEEDED, 0, ("127.0.0.1", 1081))
                response = socks5_serializer.pack_serializable(payload)
                self.transport.write(response)
                self.state = ConnectionState.PROXY_REQUEST_ACCEPTED

            elif request.cmd == REQ_CMD_CONNECT:
                self._logger.info("Accepting TCP CONNECT request to %s:%d", *request.destination)
                self.connect_to = request.destination
                payload = CommandResponse(SOCKS_VERSION, REP_SUCCEEDED, 0, ("127.0.0.1", 1081))
                response = socks5_serializer.pack_serializable(payload)
                self.transport.write(response)

            else:
                self.deny_request(request, "CMD not recognized")
        except:
            payload = CommandResponse(SOCKS_VERSION, REP_COMMAND_NOT_SUPPORTED, 0, ("0.0.0.0", 0))
            response = socks5_serializer.pack_serializable(payload)
            self.transport.write(response)
            self._logger.exception("Exception thrown, returning unsupported command response")

        return True

    def deny_request(self, request, reason):
        """
        Deny SOCKS5 request
        @param Request request: the request to deny
        """
        self.state = ConnectionState.CONNECTED

        payload = CommandResponse(SOCKS_VERSION, REP_COMMAND_NOT_SUPPORTED, 0, ("0.0.0.0", 0))
        response = socks5_serializer.pack_serializable(payload)
        self.transport.write(response)
        self._logger.error("DENYING SOCKS5 request, reason: %s" % reason)

    async def on_udp_associate_request(self, request):
        # The DST.ADDR and DST.PORT fields contain the address and port that the client expects
        # to use to send UDP datagrams on for the association.  The server MAY use this information
        # to limit access to the association.
        self.udp_connection = SocksUDPConnection(self, request.destination)
        await self.udp_connection.open()
        ip, _ = self.transport.get_extra_info('sockname')
        port = self.udp_connection.get_listen_port()

        self._logger.info("Accepting UDP ASSOCIATE request to %s:%d (BIND addr %s:%d)", ip, port, *request.destination)
        payload = CommandResponse(SOCKS_VERSION, REP_SUCCEEDED, 0, (ip, port))
        response = socks5_serializer.pack_serializable(payload)
        self.transport.write(response)

    def circuit_dead(self, broken_circuit):
        """
        When a circuit breaks and it affects our operation we should re-add the peers when a new circuit is available

        @param Circuit broken_circuit: the circuit that has been broken
        @return Set with destinations using this circuit
        """
        affected_destinations = set(destination for destination, tunnel_circuit
                                    in self.destinations.items() if tunnel_circuit == broken_circuit)
        counter = 0
        for destination in affected_destinations:
            if destination in self.destinations:
                del self.destinations[destination]
                counter += 1

        if counter > 0:
            self._logger.debug("Deleted %d peers from destination list", counter)

        return affected_destinations

    def connection_lost(self, _):
        self.socksserver.connection_lost(self)

    def close(self, reason='unspecified'):
        self._logger.info("Closing session, reason %s", reason)
        if self.udp_connection:
            self.udp_connection.close()
            self.udp_connection = None

        if self.transport:
            self.transport.close()
