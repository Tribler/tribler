from Tribler.community.anontunnel.events import TunnelObserver

import logging
import socket
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY
from Tribler.community.anontunnel.routing import CircuitPool
from .session import Socks5Session
from .connection import Socks5Connection

__author__ = 'chris'


class Socks5Server(TunnelObserver):
    """
    The SOCKS5 server which allows clients to proxy UDP over Circuits in the
    ProxyCommunity

    @param ProxyCommunity tunnel: the ProxyCommunity to request circuits from
    @param RawServer raw_server: the RawServer instance to bind on
    @param int socks5_port: the port to listen on
    """
    def __init__(self, tunnel, raw_server, socks5_port=1080, num_circuits=4, min_circuits=4, min_session_circuits=4):
        super(Socks5Server, self).__init__()
        self._logger = logging.getLogger(__name__)

        self.tunnel = tunnel
        self.socks5_port = socks5_port
        self.raw_server = raw_server
        ''' @type : RawServer '''
        self.reserved_circuits = []
        ''' @type : list[Circuit] '''
        self.awaiting_circuits = 0
        ''' @type : int '''
        self.tcp2session = {}
        ''' @type : dict[Socks5Connection, Socks5Session] '''

        self.circuit_pool = CircuitPool(num_circuits, "SOCKS5(master)")
        self.tunnel.observers.append(self.circuit_pool)
        self.tunnel.circuit_pools.append(self.circuit_pool)

        self.min_circuits = min_circuits
        self.min_session_circuits = min_session_circuits

        raw_server.add_task(self.__start_anon_session, 5.0)

    def __start_anon_session(self):
        made_session = False

        if len(self.circuit_pool.available_circuits) >= self.min_circuits:
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
            self.tunnel.observers.append(self)
        except socket.error:
            self._logger.error(
                "Cannot listen on SOCK5 port %s:%d, perhaps another "
                "instance is running?",
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
            session_pool = CircuitPool(4, "SOCKS5(%s:%d)" % (single_socket.get_ip(), single_socket.get_port()))
            session = Socks5Session(self.raw_server, s5con, self, session_pool, min_circuits=self.min_session_circuits)
            self.tunnel.observers.append(session)
            self.tunnel.observers.append(session_pool)
            self.tunnel.circuit_pools.insert(0, session_pool)

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
        self.tunnel.observers.remove(session)
        self.tunnel.circuit_pools.remove(session.circuit_pool)

        # Reclaim good circuits
        good_circuits = [circuit for circuit in session.circuit_pool.available_circuits if circuit.state == CIRCUIT_STATE_READY]

        self._logger.warning(
            "Reclaiming %d good circuits due to %s:%d",
            len(good_circuits),
            single_socket.get_ip(), single_socket.get_port())

        for circuit in good_circuits:
            self.circuit_pool.fill(circuit)

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

    def on_break_circuit(self, circuit):
        if circuit in self.reserved_circuits:
            self.reserved_circuits.remove(circuit)
