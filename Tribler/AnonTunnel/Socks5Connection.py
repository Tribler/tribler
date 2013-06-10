'''
Created on 3 jun. 2013

@author: Chris
'''
from socket import socket
import logging
logger = logging.getLogger(__name__)

import sys
import Socks5
import TcpConnectionHandler
from Socks5.structs import MethodRequest, Request
from Tribler.Core.RawServer.SocketHandler import SingleSocket

DEBUG = True

class ConnectionState:
    (BEFORE_METHOD_REQUEST, METHOD_REQUESTED, CONNECTED, PROXY_REQUEST_RECEIVED, PROXY_REQUEST_ACCEPTED, TCP_RELAY) = range(6)

class Socks5Connection:

    def __init__(self, single_socket, connection_handler):
        self.state = ConnectionState.BEFORE_METHOD_REQUEST
        
        self.singsock = single_socket
        """:type : SingleSocket"""

        self.connection_handler = connection_handler
        """:type : Socks5Handler """

        self.buffer = ''

        self.tcp_relay = None

    def data_came_in(self, data):       
        if len(self.buffer) == 0:
            self.buffer = data
        else:
            self.buffer = self.buffer + data

        logger.info("data_came_in %d bytes", len(data))

        
        self._process_buffer()

    def _try_handshake(self):
        offset, request = Socks5.structs.decode_methods_request(0, self.buffer)
        
        if request is None:
            return None
    
        self.buffer = self.buffer[offset:]
        
        assert isinstance(request, MethodRequest)

        # Only accept NO AUTH
        if request.version != 0x05 or len(set([0x00,0x01,0x02]).difference(request.methods)) == 2:
            logger.info("Client has sent INVALID METHOD REQUEST")
            self.buffer = ''
            self.close()
            return
        
        logger.info("Client has sent METHOD REQUEST")    

        response = Socks5.structs.encode_method_selection_message(Socks5.structs.SOCKS_VERSION, 0x00)
        self.write(response)
        
        self.state = ConnectionState.CONNECTED
        
    def _try_tcp_relay(self):
        logger.info("Relaying TCP data")
        self.tcp_relay.sendall(self.buffer)
        self.buffer = ''
        
    def _try_request(self):
        offset, request = Socks5.structs.decode_request(0, self.buffer)
        
        if request is None:
            return None
        
        self.buffer = self.buffer[offset:]
        
        assert isinstance(request, Request)
        logger.debug("Client has sent PROXY REQUEST")
        
        self.state = ConnectionState.PROXY_REQUEST_RECEIVED
        
        if request.cmd == Socks5.structs.REQ_CMD_CONNECT:
            dns = (request.destination_address, request.destination_port)
            destination_socket = self.connection_handler.start_connection(dns)

            logger.debug("Accepting TCP RELAY request, direct client to %s:%d",self.singsock.get_myip(), self.singsock.get_myport())

            # Switch to TCP relay mode
            self.connection_handler.switch_to_tcp_relay(self.singsock, destination_socket)

            response = Socks5.structs.encode_reply(0x05, 0x00, 0x00, Socks5.structs.ATYP_IPV4, self.singsock.get_myip(), self.singsock.get_myport())
            self.write(response)
        elif request.cmd == Socks5.structs.REQ_CMD_UDP_ASSOCIATE:
            socket = self.connection_handler.server.create_udp_relay()
            ip, port = socket.getsockname()

            ip = "127.0.0.1"

            logger.info("Accepting UDP ASSOCIATE request, direct client to %s:%d",ip,port)

            response = Socks5.structs.encode_reply(0x05,0x00,0x00, Socks5.structs.ATYP_IPV4, ip,port)
            self.write(response)

        
        self.state = ConnectionState.PROXY_REQUEST_ACCEPTED
        

    def _process_buffer(self):

        while len(self.buffer) > 0:
            if self.state == ConnectionState.BEFORE_METHOD_REQUEST:
                if not self._try_handshake():
                    break   # Not enough bytes so wait till we got more

            elif self.state == ConnectionState.CONNECTED:
                if not self._try_request():
                    break   # Not enough bytes so wait till we got more
                

    def write(self, data):
        if self.singsock is not None:
            self.singsock.write(data)

    def close(self):
        if self.singsock is not None:
            self.singsock.close()
            self.connection_handler.connection_lost(self.singsock)
            self.singsock = None

