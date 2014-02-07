import time
from Tribler.community.anontunnel.endpoint import HackyEndpoint
from Tribler.community.anontunnel.StatsCrawler import StatsCrawler
from Tribler.community.privatesemantic.elgamalcrypto import  ElgamalCrypto, NoElgamalCrypto

__author__ = 'chris'

import logging

logger = logging.getLogger(__name__)

from traceback import print_exc
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ConnectionHandlers.CommandHandler import CommandHandler
from Tribler.community.anontunnel.community import ProxyCommunity
from Tribler.community.anontunnel.Socks5Server import Socks5Server
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from threading import Event, Thread

class AnonTunnel(Thread):
    def __init__(self, socks5_port, cmd_port, settings=None, crawl=False):
        Thread.__init__(self)
        self.crawl = crawl
        self.settings = settings
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    1,
                                    600.0,
                                    ipv6_enable=False,
                                    failfunc=lambda (e): print_exc(),
                                    errorfunc=lambda (e): print_exc())

        self.callback = Callback()
        self.socks5_server = Socks5Server()

        self.socks5_server.attach_to(self.raw_server, socks5_port)

        self.endpoint = HackyEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:", crypto=ElgamalCrypto())

        if cmd_port:
            self.command_handler = CommandHandler(self)
            self.command_handler.attach_to(self.raw_server, cmd_port)


        self.community = None

    def run(self):
        self.dispersy.start()
        logger.error("Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        def join_overlay(dispersy):
            proxy_community = dispersy.define_auto_load(ProxyCommunity,
                                     (self.dispersy.get_new_member(u"NID_secp160k1"), self.raw_server, self.settings, False),
                                     load=True)
            
            self.socks5_server.tunnel = proxy_community[0]
            self.socks5_server.start()

            self.community = proxy_community[0]

            if self.crawl:
                self.community.add_observer(StatsCrawler(self.raw_server))

            return proxy_community[0]

        self.community = self.dispersy.callback.call(join_overlay, (self.dispersy,))
        '" :type : Tribler.community.anontunnel.community.ProxyCommunity "'

        def speed_stats():
            t1 = None
            bytes_exit = 0
            bytes_enter = 0
            bytes_relay = 0

            while True:
                t2 = time.time()
                if self.community and t1 and t2 > t1:
                    speed_exit = (self.community.stats['bytes_exit'] - bytes_exit) / (t2 - t1)
                    bytes_exit = self.community.stats['bytes_exit']

                    speed_enter = (self.community.stats['bytes_enter'] - bytes_enter) / (t2 - t1)
                    bytes_enter = self.community.stats['bytes_enter']

                    relay_2 = sum([r.bytes[1] for r in self.community.relay_from_to.values()])

                    speed_relay = (relay_2 - bytes_relay) / (t2 - t1)
                    bytes_relay = relay_2
                    active_circuits = len(self.community.active_circuits)
                    num_routes = len(self.community.relay_from_to) / 2

                    print "\r%s EXIT %.2f KB/s ENTER %.2f KB/s RELAY %.2f KB/s using %d circuits and %d duplex routing rules. Average data packet size is %s bytes" % ("ONLINE" if self.community.online else "OFFLINE", speed_exit / 1024.0, speed_enter/ 1024.0, speed_relay / 1024.0, active_circuits, num_routes, self.community.stats['packet_size']),

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