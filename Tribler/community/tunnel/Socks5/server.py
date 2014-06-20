import logging
import socket

from .session import Socks5Session
from .connection import Socks5Connection

__author__ = 'chris'


class Socks5Server(object):
    """
    The SOCKS5 server which allows clients to proxy UDP over Circuits in the
    ProxyCommunity

    @param ProxyCommunity community: the ProxyCommunity to request circuits from
    @param RawServer raw_server: the RawServer instance to bind on
    @param int socks5_port: the port to listen on
    """
    def __init__(self, community, raw_server, socks5_port=1080, num_circuits=4, min_circuits=4, min_session_circuits=4):
        self._logger = logging.getLogger(__name__)

        self.community = community
        self.socks5_port = socks5_port
        self.raw_server = raw_server
        self.reserved_circuits = []
        self.awaiting_circuits = 0
        self.tcp2session = {}
        self.min_circuits = min_circuits
        self.min_session_circuits = min_session_circuits

        raw_server.add_task(self.__start_anon_session, 5.0)

    def __start_anon_session(self):
        made_session = False

        if len(self.community.circuits) >= self.min_circuits:
            try:
                from Tribler.Core.Libtorrent.LibtorrentMgr import LibtorrentMgr
                if LibtorrentMgr.hasInstance():
                    self._logger.info("Creating ANON session")
                    LibtorrentMgr.getInstance().create_anonymous_session()
                    made_session = True

            except ImportError:
                self._logger.exception("Cannot create anonymous session!")

        if not made_session:
            self.raw_server.add_task(self.__start_anon_session, delay=1.0)

        return made_session

    def start(self):
        try:
            self.raw_server.bind(self.socks5_port, reuse=True, handler=self)
            self._logger.info("SOCKS5 listening on port %d", self.socks5_port)
        except socket.error:
            self._logger.error("Cannot listen on SOCK5 port %s:%d, perhaps another instance is running?",
                               "0.0.0.0", self.socks5_port)
        except:
            self._logger.exception("Exception trying to reserve circuits")

    def external_connection_made(self, single_socket):
        """
        Called by the RawServer when a new connection has been made

        @param SingleSocket single_socket: the new connection
        """
        self._logger.info("accepted SOCKS5 new connection")
        s5con = Socks5Connection(single_socket, self)

        try:
            session = Socks5Session(self.raw_server, s5con, self, self.community, min_circuits=self.min_session_circuits)
            self.tcp2session[single_socket] = session
        except:
            self._logger.exception("Error while accepting SOCKS5 connection")
            s5con.close()

    def connection_flushed(self, single_socket):
        pass

    def connection_lost(self, single_socket):
        self._logger.info("SOCKS5 TCP connection lost")

        if single_socket not in self.tcp2session:
            return

        session = self.tcp2session[single_socket]
        s5con = session.connection
        del self.tcp2session[single_socket]

        try:
            s5con.close()
        except:
            pass

    def data_came_in(self, single_socket, data):
        """
        Data is in the READ buffer, depending on MODE the Socks5 or
        Relay mechanism will be used

        :param single_socket:
        :param data:
        :return:
        """
        tcp_connection = self.tcp2session[single_socket].connection
        try:
            tcp_connection.data_came_in(data)
        except:
            self._logger.exception("Error while handling incoming TCP data")

    def circuit_ready(self, circuit):
        for session in self.tcp2session.values():
            session.circuit_ready(circuit)

    def circuit_dead(self, circuit):
        if circuit in self.reserved_circuits:
            self.reserved_circuits.remove(circuit)

        for session in self.tcp2session.values():
            session.circuit_dead(circuit)

    def on_incoming_from_tunnel(self, community, circuit, origin, data):
        for session in self.tcp2session.values():
            session.on_incoming_from_tunnel(community, circuit, origin, data)
