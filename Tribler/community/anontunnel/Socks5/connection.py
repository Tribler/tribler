"""
Created on 3 jun. 2013

@author: Chris
"""
import logging
from Tribler.community.anontunnel.Socks5 import conversion


class ConnectionState:
    def __init__(self):
        pass

    BEFORE_METHOD_REQUEST = 1
    METHOD_REQUESTED = 2
    CONNECTED = 3
    PROXY_REQUEST_RECEIVED = 4
    PROXY_REQUEST_ACCEPTED = 5
    TCP_RELAY = 6


class TcpRelay:
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
        if request.version != 0x05 or len(
                {0x00, 0x01, 0x02}.difference(request.methods)) == 2:
            self._logger.info("Client has sent INVALID METHOD REQUEST")
            self.buffer = ''
            self.close()
            return

        self._logger.info("Client {0} has sent METHOD REQUEST".format(
            (self.single_socket.get_ip(), self.single_socket.get_port())
        ))

        # Respond that we would like to use NO AUTHENTICATION (0x00)
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
                socket = self.udp_associate()

                # We use same IP as the single socket, but the port number comes
                # from the newly created UDP listening socket
                ip = self.single_socket.get_myip()
                port = socket.getsockname()[1]

                self._logger.warning(
                    "Accepting UDP ASSOCIATE request from %s:%d, "
                    "direct client to %s:%d",
                    self.single_socket.get_ip(), self.single_socket.get_port(),
                    ip, port)

                response = conversion.encode_reply(
                    0x05, 0x00, 0x00, conversion.ADDRESS_TYPE_IPV4, ip, port)
                self.write(response)
            else:
                # We will deny all other requests (BIND, and INVALID requests);
                response = conversion.encode_reply(
                    0x05, conversion.REP_COMMAND_NOT_SUPPORTED, 0x00,
                    conversion.ADDRESS_TYPE_IPV4, "0.0.0.0", 0)
                self.write(response)
                self._logger.error(
                    "DENYING SOCKS5 Request from {0}".format(
                        (self.single_socket.get_ip(),
                         self.single_socket.get_port())
                    )
                )
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

    def _guess_state(self):
        if len(self.buffer) < 3:
            return self.state

        buffer = self.buffer
        is_version = ord(buffer[0]) == 0x05
        if is_version and buffer[1] == chr(0x01) and chr(0x00) == buffer[2]:
            self._logger.error("State GUESSING here!")
            return ConnectionState.BEFORE_METHOD_REQUEST

        has_valid_command = ord(buffer[1]) in {0x01, 0x02, 0x03}
        has_valid_address = ord(buffer[2]) in {0x01, 0x03, 0x04}

        if is_version and has_valid_command and has_valid_address:
            return ConnectionState.CONNECTED

        return self.state

    def write(self, data):
        if self.single_socket is not None:
            self.single_socket.write(data)

    def close(self):
        if self.single_socket is not None:
            self.single_socket.close()
            self.socks5_server.connection_lost(self.single_socket)
            self.single_socket = None
            ''' :type : SingleSocket '''

            if self.tcp_relay:
                self.tcp_relay.close()
