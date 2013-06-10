import logging
from Tribler.Core.RawServer.SocketHandler import SingleSocket

logger = logging.getLogger(__name__)


class TcpRelayConnection(object):
    def __init__(self, source_socket, destination_socket, connection_handler):
        self.source_socket = source_socket
        self.destination_socket = destination_socket
        self.connection_handler = connection_handler
        self.buffer = ''

        self.tcp_relay = None

    def data_came_in(self, data):
        destination_socket = self.destination_socket
        assert isinstance(destination_socket, SingleSocket)

        logger.info("Relaying %d bytes over TCP to %s:%d", len(data), destination_socket.get_ip(),
                    destination_socket.get_port())
        destination_socket.write(data)


    def write(self, data):
        if self.source_socket is not None:
            self.source_socket.write(data)


    def close(self):
        if self.source_socket is not None:
            self.source_socket.close()
            self.connection_handler.connection_lost(self.source_socket)
            self.source_socket = None