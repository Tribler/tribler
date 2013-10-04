__author__ = 'chris'

import logging.config

logger = logging.getLogger(__name__)

from traceback import print_exc
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ConnectionHandlers.CommandHandler import CommandHandler
from Tribler.community.anontunnel.DispersyTunnelProxy import DispersyTunnelProxy
from Tribler.community.anontunnel.ProxyCommunity import ProxyCommunity
from Tribler.community.anontunnel.Socks5Server import Socks5Server
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import RawserverEndpoint
from threading import Event, Thread


class AnonTunnel(Thread):

    @property
    def tunnel(self):
        """


        :return:
        :rtype: DispersyTunnelProxy
        """
        return [c for c in self.dispersy.get_communities() if isinstance(c, ProxyCommunity)][0].socks_server.tunnel;

    def __init__(self, socks5_port, cmd_port):
        Thread.__init__(self)
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    10.0 / 5.0,
                                    10.0,
                                    ipv6_enable=False,
                                    failfunc=lambda (e): print_exc(),
                                    errorfunc=lambda (e): print_exc())

        self.callback = Callback()
        self.socks5_server = Socks5Server()
        self.socks5_server.attach_to(self.raw_server, socks5_port)

        self.endpoint = RawserverEndpoint(self.socks5_server.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")

        self.command_handler = CommandHandler(self)
        self.command_handler.attach_to(self.socks5_server, cmd_port)

        self.community = None

    def run(self):
        self.dispersy.start()
        logger.error("Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        def join_overlay(dispersy):
            dispersy.define_auto_load(ProxyCommunity,
                                     (self.dispersy.get_new_member(), self.socks5_server),
                                     load=True)

        self.community = self.dispersy.callback.call(join_overlay, (self.dispersy,))
        self.raw_server.listen_forever(None)

    def stop(self):
        if self.community:
            pass

        if self.raw_server:
            self.raw_server.shutdown()

        if self.dispersy:
            self.dispersy.stop()
