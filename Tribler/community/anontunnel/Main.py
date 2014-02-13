import logging.config
import threading
import os
from Tribler.community.anontunnel.stats import StatsCrawler

logging.config.fileConfig(
    os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import sys
import argparse
import re
from threading import Thread, Event
from traceback import print_exc
import time
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel import exitstrategies
from Tribler.community.anontunnel.Socks5 import Socks5Server
from Tribler.community.anontunnel.community import ProxyCommunity, \
    ProxySettings
from Tribler.community.anontunnel.endpoint import DispersyBypassEndpoint
from Tribler.community.privatesemantic.crypto.elgamalcrypto import \
    ElgamalCrypto
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.community.anontunnel.extendstrategies import TrustThyNeighbour, \
    NeighbourSubset
from Tribler.community.anontunnel.lengthstrategies import \
    RandomCircuitLengthStrategy, ConstantCircuitLengthStrategy
from Tribler.community.anontunnel.selectionstrategies import \
    RandomSelectionStrategy, LengthSelectionStrategy

try:
    import yappi
except:
    pass


class AnonTunnel(Thread):
    def __init__(self, socks5_port, settings=None, crawl=False):
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

        self.endpoint = DispersyBypassEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".",
                                 u":memory:", crypto=ElgamalCrypto())

        self.community = None
        ''' @type: ProxyCommunity '''

    def run(self):
        self.dispersy.start()
        logger.error(
            "Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        def join_overlay(raw_server, dispersy):
            proxy_community = dispersy.define_auto_load(
                ProxyCommunity, (
                    self.dispersy.get_new_member(u"NID_secp160k1"),
                    self.settings,
                    False
                ),
                load=True)[0]
            ''' @type: ProxyCommunity '''


            self.socks5_server.tunnel = proxy_community
            self.socks5_server.start()

            self.community = proxy_community
            exitstrategies.DefaultExitStrategy(raw_server, self.community)

            if self.crawl:
                self.community.add_observer(StatsCrawler(self.raw_server))

            return proxy_community

        proxy_args = self.raw_server, self.dispersy
        self.community = self.dispersy.callback.call(join_overlay, proxy_args)
        '" :type : Tribler.community.anontunnel.community.ProxyCommunity "'

        def speed_stats():
            t1 = None
            bytes_exit = 0
            bytes_enter = 0
            bytes_relay = 0

            while True:
                t2 = time.time()
                if self.community and t1 and t2 > t1:
                    speed_exit = (self.community.global_stats.stats[
                                      'bytes_exit'] - bytes_exit) / (t2 - t1)
                    bytes_exit = self.community.global_stats.stats[
                        'bytes_exit']

                    speed_enter = (self.community.global_stats.stats[
                                       'bytes_enter'] - bytes_enter) / (
                                  t2 - t1)
                    bytes_enter = self.community.global_stats.stats[
                        'bytes_enter']

                    relay_2 = 0  #sum([r.bytes[1] for r in self.community.relay_from_to.values()])

                    speed_relay = (relay_2 - bytes_relay) / (t2 - t1)
                    bytes_relay = relay_2
                    active_circuits = len(self.community.active_circuits)
                    num_routes = len(self.community.relay_from_to) / 2

                    print "%s EXIT %.2f KB/s ENTER %.2f KB/s RELAY %.2f KB/s using %d circuits and %d duplex routing rules.\n" % (
                        "ONLINE" if self.community.online else "OFFLINE",
                        speed_exit / 1024.0, speed_enter / 1024.0,
                        speed_relay / 1024.0, active_circuits, num_routes),

                t1 = t2
                yield 2.0

        # self.callback.register(speed_stats)
        self.raw_server.listen_forever(None)

    def stop(self):
        if self.dispersy:
            self.dispersy.stop()

        self.server_done_flag.set()

        if self.raw_server:
            self.raw_server.shutdown()


def main(argv):
    parser = argparse.ArgumentParser(
        description='Anonymous Tunnel CLI interface')

    try:
        parser.add_argument('-p', '--socks5', help='Socks5 port')
        parser.add_argument('-y', '--yappi',
                            help="Yappi profiling mode, 'wall' and 'cpu' are valid values")
        parser.add_argument('-l', '--length-strategy', default=[], nargs='*',
                            help='Circuit length strategy')
        parser.add_argument('-s', '--select-strategy', default=[], nargs='*',
                            help='Circuit selection strategy')
        parser.add_argument('-e', '--extend-strategy', default='subset',
                            help='Circuit extend strategy')
        parser.add_argument('--max-circuits', nargs=1, default=10,
                            help='Maximum number of circuits to create')
        parser.add_argument('--record-on-incoming',
                            help='Record stats from the moment the first data enters the tunnel')
        parser.add_argument('--crawl', default=False,
                            help='Record stats from others in results.db')
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    cmd_port = None
    socks5_port = None

    if args.yappi == 'wall':
        profile = "wall"
    elif args.yappi == 'cpu':
        profile = "cpu"
    else:
        profile = None

    if args.socks5:
        socks5_port = int(args.socks5)

    if profile:
        yappi.set_clock_type(profile)
        yappi.start(builtins=True)
        print "Profiling using %s time" % yappi.get_clock_type()['type']

    crawl = True if args.crawl else False

    if args.record_on_incoming:
        raise ValueError("not working anymore")
        # def on_enter_tunnel_data_head(ultimate_destination, payload):
        #     anon_tunnel.community.record_stats = True
        # anon_tunnel.socks5_server.once("enter_tunnel_data", on_enter_tunnel_data_head)

    proxy_settings = ProxySettings()

    # Set extend strategy
    if args.extend_strategy == 'delegate':
        logger.error(
            "EXTEND STRATEGY DELEGATE: We delegate the selection of hops to the rest of the circuit")
        proxy_settings.extend_strategy = TrustThyNeighbour
    elif args.extend_strategy == 'subset':
        logger.error(
            "SUBSET STRATEGY DELEGATE: We delegate the selection of hops to the rest of the circuit")
        proxy_settings.extend_strategy = NeighbourSubset
    else:
        raise ValueError("extend_strategy must be either random or delegate")

    # Circuit length strategy
    if args.length_strategy[:1] == ['random']:
        strategy = RandomCircuitLengthStrategy(*args.length_strategy[1:])
        proxy_settings.length_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s" % (
        ', '.join(args.length_strategy[1:])))

    elif args.length_strategy[:1] == ['constant']:
        strategy = ConstantCircuitLengthStrategy(*args.length_strategy[1:])
        proxy_settings.length_strategy = strategy
        logger.error(
            "Using ConstantCircuitLengthStrategy with arguments %s" % (
            ', '.join(args.length_strategy[1:])))

    # Circuit selection strategies
    if args.select_strategy[:1] == ['random']:
        strategy = RandomSelectionStrategy(*args.select_strategy[1:])
        proxy_settings.selection_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s" % (
        ', '.join(args.select_strategy[1:])))

    elif args.select_strategy[:1] == ['length']:
        strategy = LengthSelectionStrategy(*args.select_strategy[1:])
        proxy_settings.selection_strategy = strategy
        logger.error("Using LengthSelectionStrategy with arguments %s" % (
        ', '.join(args.select_strategy[1:])))

    anon_tunnel = AnonTunnel(socks5_port, proxy_settings, crawl)
    ''' @type: AnonTunnel '''

    anon_tunnel.start()
    regex_cmd_extend_circuit = re.compile("e ?([0-9]+)\n")

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            anon_tunnel.stop()
            os._exit(0)
            break

        if not line:
            break

        if line == 'threads\n':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name, thread.ident)
        elif line == 'p\n':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (
                    func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P\n':
            if profile:
                filename = 'callgrindc_%d.yappi' % \
                           anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c\n':
            print "========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)"
            for circuit in anon_tunnel.community.circuits.values():
                print "%d\t%s:%d\t%d\t%d\t\t%.2f\t\t%.2f" % (
                    circuit.circuit_id, circuit.candidate.sock_addr[0],
                    circuit.candidate.sock_addr[1],
                    circuit.goal_hops, len(circuit.hops),
                    circuit.bytes_downloaded / 1024.0 / 1024.0,
                    circuit.bytes_uploaded / 1024.0 / 1024.0
                )

                for hop in circuit.hops[1:]:
                    print "\t%s:%d" % (hop.host, hop.port)
        elif line == 'q\n':
            anon_tunnel.stop()
            os._exit(0)
            break

        elif line == 'reserve\n':
            print "We will try to reserve a circuit now!"

            def on_ready(circuit):
                print "Got circuit {0}".format(circuit.circuit_id)

            deferred = anon_tunnel.community.reserve_circuit()
            deferred.addCallback(on_ready)

        elif line == 'r\n':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)"

            from_to = anon_tunnel.community.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f" % (
                    (key[0], key[1]),
                    (relay.sock_addr, relay.circuit_id),
                    relay.bytes[1] / 1024.0 / 1024.0,
                )


if __name__ == "__main__":
    main(sys.argv[1:])

