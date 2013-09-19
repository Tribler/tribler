from traceback import print_exc
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ConnectionHandlers.CommandHandler import CommandHandler

__author__ = 'chris'

import logging.config

logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.DispersyTunnelProxy import DispersyTunnelProxy
from Tribler.community.anontunnel.ProxyCommunity import ProxyCommunity
from Tribler.community.anontunnel.Socks5AnonTunnelServer import Socks5AnonTunnelServer
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import RawserverEndpoint
from threading import Event


class AnonTunnel:

    @property
    def tunnel(self):
        """


        :return:
        :rtype: DispersyTunnelProxy
        """
        return [c for c in self.dispersy.get_communities() if isinstance(c, ProxyCommunity)][0].socks_server.tunnel;

    def __init__(self, socks5_port, cmd_port):
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    10.0 / 5.0,
                                    10.0,
                                    ipv6_enable=False,
                                    failfunc=lambda (e): print_exc(),
                                    errorfunc=lambda (e): print_exc())

        self.callback = Callback()
        self.socket_server = Socks5AnonTunnelServer(self.raw_server, socks5_port)

        self.endpoint = RawserverEndpoint(self.socket_server.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")

        self.command_handler = CommandHandler(self)
        self.command_handler.attach_to(self.socket_server, cmd_port)

        self.community = None

    def start(self):
        self.dispersy.start()
        logger.info("Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        def join_overlay(dispersy):
            dispersy.define_auto_load(ProxyCommunity,
                                     (self.dispersy.get_new_member(), self.socket_server),
                                     load=True)

        self.community = self.dispersy.callback.call(join_overlay, (self.dispersy,))
        self.socket_server.start()

    def stop(self):
        if self.community:
            pass

        if self.socket_server:
            self.socket_server.shutdown()

        if self.dispersy:
            self.dispersy.stop()
