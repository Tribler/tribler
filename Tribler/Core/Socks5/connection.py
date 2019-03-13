from __future__ import absolute_import

import logging

from twisted.internet.protocol import Protocol, connectionDone

from Tribler.Core.Socks5 import conversion
from Tribler.Core.Socks5.conversion import SOCKS_VERSION
from Tribler.Core.Socks5.udp_connection import SocksUDPConnection


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
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socksserver = socksserver

        self._udp_socket = None
        self.state = ConnectionState.BEFORE_METHOD_REQUEST
        self.buffer = ''

        self.destinations = {}

    def get_udp_socket(self):
        """
        Return the UDP socket. This socket is only available if a SOCKS5 ASSOCIATE request is sent.
        """
        return self._udp_socket

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
                self._logger.error("Throwing away buffer, not in CONNECTED or BEFORE_METHOD_REQUEST state")
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

    def connectionLost(self, reason=connectionDone):
        self.socksserver.connectionLost(self)

    def close(self, reason='unspecified'):
        self._logger.info("Closing session, reason %s", reason)
        exit_value = True
        if self._udp_socket:
            exit_value = self._udp_socket.close()
            self._udp_socket = None

        self.transport.loseConnection()
        return exit_value
