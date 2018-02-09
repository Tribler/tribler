import logging

from Tribler.Core.Socks5.connection import Socks5Connection
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred, DeferredList
from twisted.internet.protocol import Factory


class Socks5Server(object):
    """
    This object represents a Socks5 server.
    """

    def __init__(self, port, udp_output_stream):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.port = port
        self.udp_output_stream = udp_output_stream
        self.twisted_port = None
        self.sessions = []

    def start(self):
        """
        Start the socks5 server by listening on the specified TCP ports.
        """
        def build_protocol(_):
            socks5connection = Socks5Connection(self)
            self.sessions.append(socks5connection)
            return socks5connection

        factory = Factory()
        factory.buildProtocol = build_protocol
        self.twisted_port = reactor.listenTCP(self.port, factory)

    def stop(self):
        """
        Stop the socks5 server.
        """
        deferred_list = []

        for session in self.sessions:
            deferred_list.append(maybeDeferred(session.close, 'stopping'))
        self.sessions = []

        if self.twisted_port:
            deferred_list.append(maybeDeferred(self.twisted_port.stopListening))

        return DeferredList(deferred_list)

    def connectionLost(self, socks5connection):
        self._logger.debug("SOCKS5 TCP connection lost")
        if socks5connection in self.sessions:
            self.sessions.remove(socks5connection)

        socks5connection.close()
