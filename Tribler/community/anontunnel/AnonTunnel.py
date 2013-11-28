import time
from Tribler.community.anontunnel.HackyEndpoint import HackyEndpoint

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

        self.endpoint = HackyEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")
        self.tunnel = DispersyTunnelProxy(self.raw_server)
        self.socks5_server.tunnel = self.tunnel

        if cmd_port:
            self.command_handler = CommandHandler(self)
            self.command_handler.attach_to(self.raw_server, cmd_port)

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
            bytes_exit = 0
            bytes_enter = 0
            bytes_relay = 0

            while True:
                tunnel = self.socks5_server.tunnel

                t2 = time.time()
                if tunnel and t1 and t2 > t1:
                    speed_exit = (tunnel.stats['bytes_exit'] - bytes_exit) / (t2 - t1)
                    bytes_exit = tunnel.stats['bytes_exit']

                    speed_enter = (tunnel.stats['bytes_enter'] - bytes_enter) / (t2 - t1)
                    bytes_enter = tunnel.stats['bytes_enter']

                    relay_2 = sum([r.bytes[1] for r in tunnel.relay_from_to.values()])

                    speed_relay = (relay_2 - bytes_relay) / (t2 - t1)
                    bytes_relay = relay_2
                    active_circuits = len(tunnel.active_circuits)
                    num_routes = len(tunnel.relay_from_to) / 2

                    print "\r%s EXIT %.2f KB/s ENTER %.2f KB/s RELAY %.2f KB/s using %d circuits and %d duplex routing rules. Average data packet size is %s bytes" % ("ONLINE" if tunnel.online else "OFFLINE", speed_exit / 1024.0, speed_enter/ 1024.0, speed_relay / 1024.0, active_circuits, num_routes, tunnel.stats['packet_size']),

                t1 = t2
                yield 1.0

        self.callback.register(speed_stats)
        self.raw_server.listen_forever(None)

    def stop(self):
        if self.dispersy:
            self.dispersy.stop()

        self.server_done_flag.set()

        if self.raw_server:
            self.raw_server.shutdown()