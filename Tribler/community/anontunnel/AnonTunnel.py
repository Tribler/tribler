import time

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
    def __init__(self, socks5_port, cmd_port):
        Thread.__init__(self)
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    600,
                                    10.0,
                                    ipv6_enable=False,
                                    failfunc=lambda (e): print_exc(),
                                    errorfunc=lambda (e): print_exc())

        self.callback = Callback()
        self.socks5_server = Socks5Server()

        self.socks5_server.attach_to(self.raw_server, socks5_port)

        self.endpoint = RawserverEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")
        self.tunnel = DispersyTunnelProxy(self.socks5_server)
        self.socks5_server.tunnel = self.tunnel

        #self.command_handler = CommandHandler(self)
        #self.command_handler.attach_to(self.socks5_server, cmd_port)

        self.community = None


    def run(self):
        self.dispersy.start()
        logger.error("Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        def join_overlay(dispersy):
            def on_ready(proxy_community):
                self.tunnel.start(self.callback, proxy_community)
                self.socks5_server.start()

            dispersy.define_auto_load(ProxyCommunity,
                                     (self.dispersy.get_new_member(), on_ready),
                                     load=True)

        self.community = self.dispersy.callback.call(join_overlay, (self.dispersy,))
        '" :type : Tribler.community.anontunnel.DispersyTunnelProxy.DispersyTunnelProxy "'

        def speed_stats():
            print

            t1 = None
            total_bytes_in_1 = 0
            total_bytes_out_1 = 0

            while True:
                tunnel = self.socks5_server.tunnel

                t2 = time.clock()
                if tunnel and t1 and t2 > t1:

                    total_bytes_in_2 = tunnel.stats['bytes_enter'] \
                                       + sum([c.bytes_downloaded for c in tunnel.get_circuits()]) \
                                       + sum([r.bytes[1] for r in tunnel.relay_from_to.values()])

                    total_bytes_out_2 = tunnel.stats['bytes_exit'] \
                                        + sum([c.bytes_uploaded for c in tunnel.get_circuits()]) \
                                        + sum([r.bytes[1] for r in tunnel.relay_from_to.values()])

                    total_speed_in = (total_bytes_in_2 - total_bytes_in_1) / (t2 - t1)
                    total_speed_out = (total_bytes_out_2 - total_bytes_out_1) / (t2 - t1)

                    active_circuits = len(tunnel.active_circuits)
                    num_routes = len(tunnel.relay_from_to) / 2

                    print "\r%.2f KB/s down %.2f KB/s up using %d circuits and %d duplex routing rules" % (total_speed_in / 1024.0, total_speed_out / 1024.0, active_circuits, num_routes),


                    total_bytes_out_1 = total_bytes_out_2
                    total_bytes_in_1 = total_bytes_in_2

                t1 = t2
                yield 1.0

        self.callback.register(speed_stats)

        self.raw_server.listen_forever(None)



    def stop(self):
        if self.community:
            pass

        if self.dispersy:
            self.dispersy.stop()

        self.server_done_flag.set()

        if self.raw_server:
            self.raw_server.shutdown()