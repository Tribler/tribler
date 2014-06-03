"""
AnonTunnel CLI interface
"""
import argparse
import logging.config
import os
import sys
import threading
import time
from threading import Thread, Event
from traceback import print_exc
from twisted.conch import stdio
from twisted.internet import reactor
from twisted.internet.stdio import StandardIO

from twisted.internet.task import LoopingCall
import twisted
from twisted.protocols.basic import LineReceiver

from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel import exitstrategies
from Tribler.community.anontunnel.Socks5.server import Socks5Server
from Tribler.community.anontunnel.community import ProxyCommunity, \
    ProxySettings
from Tribler.community.anontunnel.endpoint import DispersyBypassEndpoint
from Tribler.community.anontunnel.extendstrategies import TrustThyNeighbour, \
    NeighbourSubset
from Tribler.community.anontunnel.lengthstrategies import \
    RandomCircuitLengthStrategy, ConstantCircuitLength
from Tribler.community.anontunnel.selectionstrategies import \
    RandomSelectionStrategy, LengthSelectionStrategy
from Tribler.community.anontunnel.stats import StatsCrawler
from Tribler.community.privatesemantic.crypto.elgamalcrypto import \
    ElgamalCrypto
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.util import call_on_reactor_thread


logging.config.fileConfig(
    os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")

logger = logging.getLogger(__name__)

try:
    import yappi
except ImportError:
    logger.warning("Yappi not installed, profiling options won't be available")


class AnonTunnel():
    """
    The standalone AnonTunnel application. Does not depend on Tribler Session
    or LaunchManyCore but creates all dependencies by itself.

    @param int socks5_port: the SOCKS5 port to listen on, or None to disable
    the SOCKS5 server
    @param ProxySettings settings: the settings to pass to the ProxyCommunity
    @param bool crawl: whether to store incoming Stats messages using the
    StatsCrawler
    """

    def __init__(self, socks5_port, settings=None, crawl=False):
        self.crawl = crawl
        self.settings = settings
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    1,
                                    600.0,
                                    ipv6_enable=False,
                                    failfunc=lambda (e): print_exc(),
                                    errorfunc=lambda (e): print_exc())

        self.socks5_port = socks5_port
        self.socks5_server = None

        endpoint = DispersyBypassEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(endpoint, u".", u":memory:",
                                 crypto=ElgamalCrypto())

        self.community = None
        ''' @type: ProxyCommunity '''

    def __calc_diff(self, then, bytes_exit0, bytes_enter0, bytes_relay0):
        now = time.time()

        if not self.community or not then:
            return now, 0, 0, 0, 0, 0, 0

        diff = now - then

        stats = self.community.global_stats.stats
        relay_stats = self.community.global_stats.relay_stats

        speed_exit = (stats['bytes_exit'] - bytes_exit0) / diff if then else 0
        bytes_exit = stats['bytes_exit']

        speed_enter = (stats[
                           'bytes_enter'] - bytes_enter0) / diff if then else 0
        bytes_enter = stats['bytes_enter']

        relay_2 = sum([r.bytes[1] for r in relay_stats.values()])

        speed_relay = (relay_2 - bytes_relay0) / diff if then else 0
        bytes_relay = relay_2

        return now, speed_exit, speed_enter, speed_relay, \
               bytes_exit, bytes_enter, bytes_relay

    def __speed_stats(self):
        tmp = dict()
        tmp['time'] = None
        tmp['bytes_exit'] = 0
        tmp['bytes_enter'] = 0
        tmp['bytes_relay'] = 0

        def speed_stats_lc():
            stats = self.__calc_diff(tmp['time'], tmp['bytes_exit'], tmp['bytes_enter'],
                                     tmp['bytes_relay'] )
            time, speed_exit, speed_enter, speed_relay, bytes_exit, bytes_enter, bytes_relay = stats

            tmp['time'] = time
            tmp['bytes_exit'] = bytes_exit
            tmp['bytes_enter'] = bytes_enter
            tmp['bytes_relay'] = bytes_relay

            active_circuits = len(self.community.circuits)
            num_routes = len(self.community.relay_from_to) / 2

            print "CIRCUITS %d RELAYS %d EXIT %.2f KB/s ENTER %.2f KB/s RELAY %.2f KB/s\n" % (
                active_circuits, num_routes, speed_exit / 1024.0,
                speed_enter / 1024.0, speed_relay / 1024.0),

        lc = LoopingCall(speed_stats_lc)
        lc.start(3, now=True)

    def run(self):
        """
        Start the standalone AnonTunnel
        """

        self.dispersy.start()
        logger.error(
            "Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        member = self.dispersy.get_new_member(u"NID_secp160k1")
        self.community = self.dispersy.define_auto_load(ProxyCommunity, member,
                                                   (False, self.settings, self.raw_server),
                                                   load=True)[0]
        ''' @type: ProxyCommunity '''

        if self.socks5_server:
            self.socks5_server = Socks5Server(
                self.community, self.raw_server, self.socks5_port)
            self.socks5_server.start()

        exit_strategy = exitstrategies.DefaultExitStrategy(self.raw_server, self.community)
        self.community.observers.append(exit_strategy)

        if self.crawl:
            self.community.observers.append(
                StatsCrawler(self.dispersy, self.raw_server))

        ''' :type : Tribler.community.anontunnel.community.ProxyCommunity '''

        self.__speed_stats()
        raw_server_thread = Thread(target=self.raw_server.listen_forever, args=(None,))
        raw_server_thread.start()

    def stop(self):
        """
        Stop the standalone AnonTunnel
        """
        if self.dispersy:
            self.dispersy.stop()

        self.server_done_flag.set()

        if self.raw_server:
            self.raw_server.shutdown()


class LineHandler(LineReceiver):
    from os import linesep as delimiter

    def __init__(self, anon_tunnel, profile):
        self.anon_tunnel = anon_tunnel
        self.profile = profile

    def lineReceived(self, line):
        anon_tunnel = self.anon_tunnel
        profile = self.profile

        if line == 'threads':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name, thread.ident)
        elif line == 'p':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (
                        func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P':
            if profile:
                filename = 'callgrindc_%d.yappi' % \
                           anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c':
            stats = anon_tunnel.community.global_stats.circuit_stats

            print "========\nCircuits\n========\n" \
                  "id\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)"
            for circuit_id, circuit in anon_tunnel.community.circuits.items():
                print "%d\t%s:%d\t%d\t%d\t\t%.2f\t\t%.2f" % (
                    circuit.circuit_id, circuit.first_hop[0],
                    circuit.first_hop[1],
                    circuit.goal_hops, len(circuit.hops),
                    stats[circuit_id].bytes_downloaded / 1024.0 / 1024.0,
                    stats[circuit_id].bytes_uploaded / 1024.0 / 1024.0
                )
        elif line == 'q':
            anon_tunnel.stop()
            os._exit(0)
            return
        elif line == 'r':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)"

            from_to = anon_tunnel.community.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f" % (
                    (key[0], key[1]),
                    (relay.sock_addr, relay.circuit_id),
                    relay.bytes[1] / 1024.0 / 1024.0,
                )

def main(argv):
    """
    Start CLI interface of the AnonTunnel
    @param argv: the CLI arguments, except the first
    """
    parser = argparse.ArgumentParser(
        description='Anonymous Tunnel CLI interface')

    try:
        parser.add_argument('-p', '--socks5', help='Socks5 port')
        parser.add_argument('-y', '--yappi',
                            help="Profiling mode, either 'wall' or 'cpu'")
        parser.add_argument('-l', '--length-strategy', default=[], nargs='*',
                            help='Circuit length strategy')
        parser.add_argument('-s', '--select-strategy', default=[], nargs='*',
                            help='Circuit selection strategy')
        parser.add_argument('-e', '--extend-strategy', default='subset',
                            help='Circuit extend strategy')
        parser.add_argument('--max-circuits', nargs=1, default=10,
                            help='Maximum number of circuits to create')
        parser.add_argument('--crawl', default=False,
                            help='Record stats from others in results.db')
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

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
    proxy_settings = ProxySettings()

    # Set extend strategy
    if args.extend_strategy == 'delegate':
        logger.error("EXTEND STRATEGY DELEGATE: We delegate the selection of "
                     "hops to the rest of the circuit")
        proxy_settings.extend_strategy = TrustThyNeighbour
    elif args.extend_strategy == 'subset':
        logger.error("SUBSET STRATEGY DELEGATE: We delegate the selection of "
                     "hops to the rest of the circuit")
        proxy_settings.extend_strategy = NeighbourSubset
    else:
        raise ValueError("extend_strategy must be either random or delegate")

    # Circuit length strategy
    if args.length_strategy[:1] == ['random']:
        strategy = RandomCircuitLengthStrategy(*args.length_strategy[1:])
        proxy_settings.length_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s",
                     ', '.join(args.length_strategy[1:]))

    elif args.length_strategy[:1] == ['constant']:
        strategy = ConstantCircuitLength(*args.length_strategy[1:])
        proxy_settings.length_strategy = strategy
        logger.error(
            "Using ConstantCircuitLength with arguments %s",
            ', '.join(args.length_strategy[1:]))

    # Circuit selection strategies
    if args.select_strategy[:1] == ['random']:
        strategy = RandomSelectionStrategy(*args.select_strategy[1:])
        proxy_settings.selection_strategy = strategy
        logger.error("Using RandomCircuitLengthStrategy with arguments %s"
                     ', '.join(args.select_strategy[1:]))

    elif args.select_strategy[:1] == ['length']:
        strategy = LengthSelectionStrategy(*args.select_strategy[1:])
        proxy_settings.selection_strategy = strategy
        logger.error("Using LengthSelectionStrategy with arguments %s",
                     ', '.join(args.select_strategy[1:]))

    anon_tunnel = AnonTunnel(socks5_port, proxy_settings, crawl)
    ''' @type: AnonTunnel '''



    from twisted.internet import reactor

    StandardIO(LineHandler(anon_tunnel, profile))
    reactor.callWhenRunning(anon_tunnel.run)
    reactor.run()

if __name__ == "__main__":
    main(sys.argv[1:])
