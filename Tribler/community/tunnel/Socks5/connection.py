"""
Created on 3 jun. 2013

@author: Chris
"""
import logging
from socket import socket
from Tribler.community.tunnel.Socks5 import conversion


class ConnectionState:
    """
    Enumeration of possible SOCKS5 connection states
    """
    def __init__(self):
        pass

    BEFORE_METHOD_REQUEST = 'BEFORE_METHOD_REQUEST'
    METHOD_REQUESTED = 'METHOD_REQUESTED'
    CONNECTED = 'CONNECTED'
    PROXY_REQUEST_RECEIVED = 'PROXY_REQUEST_RECEIVED'
    PROXY_REQUEST_ACCEPTED = 'PROXY_REQUEST_ACCEPTED'
    TCP_RELAY = 'TCP_RELAY'


class Socks5ConnectionObserver:
    """
    Socks5 Connection observer
    """

    def __init__(self):
        pass

    def on_udp_associate_request(self, connection, request):
        """

        @param Socks5Connection connection: the Socks5 connection we got the
        request on
        @param Request request: the request received
        """
        pass


class Socks5Connection(object):
    """
    SOCKS5 TCP Connection handler

    Supports a subset of the SOCKS5 protocol, no authentication and no support
    for TCP BIND requests
    """

    def __init__(self, single_socket, socks5_server):
        self.state = ConnectionState.BEFORE_METHOD_REQUEST
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)

        self.observers = []
        ''' :type : list[Socks5ConnectionObserver] '''

        self.single_socket = single_socket
        ''' :type : SingleSocket '''

        self.socks5_server = socks5_server
        """ :type : TcpConnectionHandler """

        self.buffer = ''
        self.tcp_relay = None
        self.udp_associate = None
        ''' :type : (Socks5Connection) -> socket '''

    def data_came_in(self, data):
        """
        Called by the TcpConnectionHandler when new data has been received.

        Processes the incoming buffer by attempting to read messages defined
        in the SOCKS5 protocol

        :param data: the data received
        :return: None
        """

        if len(self.buffer) == 0:
            self.buffer = data
        else:
            self.buffer = self.buffer + data

        if self.tcp_relay:
            self._try_tcp_relay()
        else:
            self._process_buffer()

    def _try_handshake(self):

        # Try to read a HANDSHAKE request
        offset, request = conversion.decode_methods_request(0, self.buffer)

        # No (complete) HANDSHAKE received, so dont do anything
        if request is None:
            return None

        # Consume the buffer
        self.buffer = self.buffer[offset:]

        assert isinstance(request, conversion.MethodRequest)

        # Only accept NO AUTH
        if request.version != 0x05 or 0x00 not in request.methods:
            self._logger.error("Client has sent INVALID METHOD REQUEST")
            self.buffer = ''
            self.close()
            return

        self._logger.info("Client {0} has sent METHOD REQUEST".format(
            (self.single_socket.get_ip(), self.single_socket.get_port())
        ))

        # Respond that we would like to use NO AUTHENTICATION (0x00)
        if self.state is not ConnectionState.CONNECTED:
            response = conversion.encode_method_selection_message(
                conversion.SOCKS_VERSION, 0x00)
            self.write(response)

        # We are connected now, the next incoming message will be a REQUEST
        self.state = ConnectionState.CONNECTED

    def _try_tcp_relay(self):
        """
        Forward the complete buffer to the paired TCP socket

        :return: None
        """
        self._logger.info("Relaying TCP data")
        self.tcp_relay.sendall(self.buffer)
        self.buffer = ''

    def deny_request(self, request, drop_connection=True):
        """
        Deny SOCKS5 request
        @param Request request: the request to deny
        @param bool drop_connection: whether to drop the connection or not
        """
        if self.state != ConnectionState.PROXY_REQUEST_RECEIVED:
            raise ValueError("There must be a request before we can deny it")

        self.state = ConnectionState.CONNECTED

        response = conversion.encode_reply(
            0x05, conversion.REP_COMMAND_NOT_SUPPORTED, 0x00,
            conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)

        self.write(response)

        if self.single_socket:
            self._logger.error(
                "DENYING SOCKS5 Request from {0}".format(
                (self.single_socket.get_ip(),
                 self.single_socket.get_port())
                )
            )

        if drop_connection:
            self.close()

    def accept_udp_associate(self, request, udp_socket):
        """
        Accept the UDP request given and redirect the client to the udp_socket
        @param request:
        @param socket udp_socket: the udp relay socket
        """

        if not isinstance(udp_socket, socket):
            raise ValueError("Parameter udp_socket must be of socket type")

        if self.state != ConnectionState.PROXY_REQUEST_RECEIVED:
            raise ValueError("SOCKS5 connection has not been established yet!")

        # We use same IP as the single socket, but the port number
        # comes from the newly created UDP listening socket
        ip = self.single_socket.get_myip()
        port = udp_socket.getsockname()[1]

        self._logger.warning(
            "Accepting UDP ASSOCIATE request from %s:%d, "
            "direct client to %s:%d",
            self.single_socket.get_ip(), self.single_socket.get_port(),
            ip, port)

        response = conversion.encode_reply(
            0x05, conversion.REP_SUCCEEDED, 0x00,
            conversion.ADDRESS_TYPE_IPV4, ip, port)
        self.write(response)

    def _try_request(self):
        """
        Try to consume a REQUEST message and respond whether we will accept the
        request.

        Will setup a TCP relay or an UDP socket to accommodate TCP RELAY and
        UDP ASSOCIATE requests. After a TCP relay is set up the handler will
        deactivate itself and change the Connection to a TcpRelayConnection.
        Further data will be passed on to that handler.

        :return: None
        """
        self._logger.debug("Client {0} has sent PROXY REQUEST".format(
            (self.single_socket.get_ip(), self.single_socket.get_port())
        ))
        offset, request = conversion.decode_request(0, self.buffer)

        if request is None:
            return None

        self.buffer = self.buffer[offset:]

        assert isinstance(request, conversion.Request)
        self.state = ConnectionState.PROXY_REQUEST_RECEIVED

        accept = True

        try:
            if request.cmd == conversion.REQ_CMD_UDP_ASSOCIATE:
                for observer in self.observers:
                    observer.on_udp_associate_request(self, request)

                accept = False
            elif request.cmd == conversion.REQ_CMD_BIND:
                response = conversion.encode_reply(
                    0x05, conversion.REP_SUCCEEDED, 0x00,
                    conversion.ADDRESS_TYPE_IPV4, "127.0.0.1", 1081)
                self.write(response)
                self.state = ConnectionState.PROXY_REQUEST_ACCEPTED
            elif request.cmd == conversion.REQ_CMD_CONNECT:
                self._logger.warning(
                    "TCP req to %s:%d support it. Returning HOST UNREACHABLE",
                    *request.destination)
                response = conversion.encode_reply(
                    0x05, conversion.REP_HOST_UNREACHABLE, 0x00,
                    conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)
                self.write(response)
                accept = False
            else:
                self.deny_request(request, False)
                accept = False
        except:
            response = conversion.encode_reply(
                    0x05, conversion.REP_COMMAND_NOT_SUPPORTED, 0x00,
                    conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)
            self.write(response)
            self._logger.exception("Exception thrown. Returning unsupported "
                                   "command response")
            accept = False

        if accept:
            self.state = ConnectionState.PROXY_REQUEST_ACCEPTED

        return accept

    def _process_buffer(self):
        """
        Processes the buffer by attempting to messages which are to be expected
        in the current state
        """
        while len(self.buffer) > 0:
            self.state = self._guess_state()

            # We are at the initial state, so we expect a handshake request.
            if self.state == ConnectionState.BEFORE_METHOD_REQUEST:
                if not self._try_handshake():
                    break  # Not enough bytes so wait till we got more

            # We are connected so the
            elif self.state == ConnectionState.CONNECTED:
                if not self._try_request():
                    break  # Not enough bytes so wait till we got more
            else:
                self.buffer = ''

    def _guess_state(self):
        if len(self.buffer) < 3:
            return self.state

        data = self.buffer
        is_version = ord(data[0]) == 0x05
        if is_version and data[1] == chr(0x01) and chr(0x00) == data[2]:
            guessed_state = ConnectionState.BEFORE_METHOD_REQUEST

            if self.state != guessed_state:
                self._logger.error("GUESSING SOCKS5 state %s should be %s!", guessed_state, self.state)

            return guessed_state

        has_valid_command = ord(data[1]) in [0x01, 0x02, 0x03]
        has_valid_address = ord(data[2]) in [0x01, 0x03, 0x04]

        if is_version and has_valid_command and has_valid_address:
            return ConnectionState.CONNECTED

        return self.state

    def write(self, data):
        if self.single_socket is not None:
            self.single_socket.write(data)

    def close(self):
        if self.single_socket is not None:
            self._logger.error(
                "On close() of %s:%d", self.single_socket.get_ip(),
                self.single_socket.get_port())

            self.single_socket.close()
            self.single_socket = None
            ''' :type : SingleSocket '''

            if self.tcp_relay:
                self.tcp_relay.close()
