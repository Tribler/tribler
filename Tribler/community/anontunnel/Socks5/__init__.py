"""
Created on 3 jun. 2013

@author: Chris
"""

import logging
from twisted.internet import defer
from Tribler.Core.RawServer.SocketHandler import SingleSocket
from Tribler.community.anontunnel.Socks5.session import Socks5Session
from Tribler.community.anontunnel.community import TunnelObserver
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY
import structs
from connection import Socks5Connection

logger = logging.getLogger(__name__)

import session
import socket
from traceback import print_exc


class Socks5Server(object, TunnelObserver):
    def __init__(self):
        super(Socks5Server, self).__init__()

        self._tunnel = None
        self._accept_incoming = False
        # self.socket2connection = {}
        self.socks5_port = None
        self.raw_server = None
        self.udp_relay_socket = None
        self.bound = False
        self.routes = {}
        self.udp_relays = {}
        self.reserved_circuits = []
        self.awaiting_circuits = 0

        self.tcp2session = {}
        ''' @type : dict[Socks5Connection, Socks5Session] '''


    @property
    def tunnel(self):
        """ :rtype : Tribler.community.anontunnel.community.ProxyCommunity """
        return self._tunnel

    @tunnel.setter
    def tunnel(self, value):
        self._tunnel = value
        self.tunnel.add_observer(self)

    def attach_to(self, raw_server, socks5_port=1080):
        self.socks5_port = socks5_port
        self.raw_server = raw_server

    def start(self):
        if self.socks5_port:
            try:
                port = self.raw_server.find_and_bind(self.socks5_port,
                                                     self.socks5_port,
                                                     self.socks5_port + 10,
                                                     ['0.0.0.0'],
                                                     reuse=True, handler=self)

                logger.info("Socks5Proxy binding to %s:%s", "0.0.0.0", port)
            except socket.error:
                logger.error(
                    "Cannot listen on SOCK5 port %s:%d, perhaps another "
                    "instance is running?",
                    "0.0.0.0",
                    self.socks5_port)

    def start_connection(self, dns):
        return self.raw_server.start_connection_raw(
            dns, handler=self.connection_handler)

    def _reserve_circuits(self, count):
        lacking = max(0, count - len(self.reserved_circuits))

        def _on_reserve(c):
            self.reserved_circuits.append(c)

        def _finally(result):
            self.awaiting_circuits -= 1
            return result

        if lacking > 0:
            new = lacking - self.awaiting_circuits

            logger.warning(
                "Trying to reserve %d circuits, have %d, waiting %d, new %d",
                       count, len(self.reserved_circuits),
                       self.awaiting_circuits, new)

            self.awaiting_circuits += new

            for i in range(new):
                self.tunnel.reserve_circuit()\
                    .addCallback(_on_reserve)\
                    .addBoth(_finally)

            raise ValueError("Not enough circuits available, requestin new ones")
        else:
            circuits = self.reserved_circuits[0:count]
            del self.reserved_circuits[0:count]

            return circuits

    def external_connection_made(self, s):
        assert isinstance(s, SingleSocket)
        logger.info("accepted a socket on port %d", s.get_myport())
        s5con = Socks5Connection(s, self)

        try:
            circuits = self._reserve_circuits(4)
            session = Socks5Session(self.raw_server, s5con, circuits)
            self.tunnel.add_observer(session)

            self.tcp2session[s] = session
        except:
            s5con.close()

    def connection_flushed(self, s):
        pass

    def connection_lost(self, s):
        logger.info("SOCKS5 TCP connection lost")

        if s not in self.tcp2session:
            return

        session = self.tcp2session[s]
        self.tunnel.remove_observer(session)

        # Reclaim good circuits
        good_circuits = [c for c in session.circuits
                         if c.state == CIRCUIT_STATE_READY]

        logger.warning("Reclaiming %d good circuits", len(good_circuits))

        self.reserved_circuits = good_circuits + self.reserved_circuits
        s5con = session.connection
        del self.tcp2session[s]

        try:
            s5con.close()
        except:
            pass

    def data_came_in(self, s, data):
        """
        Data is in the READ buffer, depending on MODE the Socks5 or Relay mechanism will be used

        :param s:
        :param data:
        :return:
        """
        tcp_connection = self.tcp2session[s].connection
        try:
            tcp_connection.data_came_in(data)
        except:
            print_exc()

    def shutdown(self):
        for session in self.tcp2session.values():
            session.connection.shutdown()

    def on_break_circuit(self, circuit):
        if circuit in self.reserved_circuits:
            self.reserved_circuits.remove(circuit)