__author__ = 'chris'

import logging
import socket
from traceback import print_exc
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from Tribler.community.anontunnel.community import TunnelObserver
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY
from .session import Socks5Session
from .connection import Socks5Connection


logger = logging.getLogger()


class Socks5Server(object, TunnelObserver):
    """
    The SOCKS5 server which allows clients to proxy UDP over Circuits in the
    ProxyCommunity

    @param ProxyCommunity tunnel: the ProxyCommunity to request circuits from
    @param RawServer raw_server: the RawServer instance to bind on
    @param int socks5_port: the port to listen on
    """
    def __init__(self, tunnel, raw_server, socks5_port=1080):
        super(Socks5Server, self).__init__()

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

    def start(self):
        try:
            port = self.raw_server.bind(
                self.socks5_port, reuse=True, handler=self)

            logger.info("Socks5Proxy bound to %s:%s", "0.0.0.0", port)

            self.tunnel.observers.append(self)

            self._reserve_circuits(4)
        except socket.error:
            logger.error(
                "Cannot listen on SOCK5 port %s:%d, perhaps another "
                "instance is running?",
                "0.0.0.0", self.socks5_port)
        except:
            logger.exception("Exception trying to reserve circuits")

    def _reserve_circuits(self, count):
        lacking = max(0, count - len(self.reserved_circuits))

        def __on_reserve(circuit):
            self.reserved_circuits.append(circuit)

            return circuit

        def __finally(result):
            self.awaiting_circuits -= 1
            if self.awaiting_circuits == 0:
                from Tribler.Core.Libtorrent import LibtorrentMgr
                logger.error("Going to set anon tunnel utp only")
                LibtorrentMgr.LibtorrentMgr.getInstance().set_anon_tunnel()
            return result

        if lacking > 0:
            new = lacking - self.awaiting_circuits

            logger.warning(
                "Require %d circuits, have %d, waiting %d, new %d",
                count, len(self.reserved_circuits),
                self.awaiting_circuits, new)

            self.awaiting_circuits += new

            for _ in range(new):
                self.tunnel.reserve_circuit() \
                    .addCallback(__on_reserve) \
                    .addBoth(__finally)

            raise ValueError("Not enough circuits, requesting new ones")
        else:
            circuits = self.reserved_circuits[0:count]
            del self.reserved_circuits[0:count]

            return circuits

    def external_connection_made(self, single_socket):
        """
        Called by the RawServer when a new connection has been made

        @param SingleSocket single_socket: the new connection
        """
        logger.info("accepted SOCKS5 new connection")
        s5con = Socks5Connection(single_socket, self)

        try:
            circuits = self._reserve_circuits(1)
            session = Socks5Session(self.raw_server, s5con, circuits)
            self.tunnel.observers.append(session)

            self.tcp2session[single_socket] = session
        except:
            s5con.close()

    def connection_flushed(self, single_socket):
        pass

    def connection_lost(self, single_socket):
        logger.info("SOCKS5 TCP connection lost")

        if single_socket not in self.tcp2session:
            return

        session = self.tcp2session[single_socket]
        self.tunnel.observers.remove(session)

        # Reclaim good circuits
        good_circuits = [c for c in session.circuits
                         if c.state == CIRCUIT_STATE_READY]

        logger.warning("Reclaiming %d good circuits", len(good_circuits))

        self.reserved_circuits = good_circuits + self.reserved_circuits
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
            print_exc()

    def on_break_circuit(self, circuit):
        if circuit in self.reserved_circuits:
            self.reserved_circuits.remove(circuit)