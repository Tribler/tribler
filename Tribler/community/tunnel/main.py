import os
import sys
import time
import random
import logging
import argparse
import threading

from threading import Thread
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineReceiver
from twisted.internet.threads import blockingCallFromThread
from Tribler.dispersy.logger import get_logger
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.community import TunnelCommunity, TunnelSettings
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.twisted_thread import reactor

logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")
logger = get_logger(__name__)

try:
    import yappi
except ImportError:
    logger.warning("Yappi not installed, profiling options won't be available")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))


class AnonTunnel():
    """
    The standalone AnonTunnel application. Does not depend on Tribler Session
    or LaunchManyCore but creates all dependencies by itself.

    @param int socks5_port: the SOCKS5 port to listen on, or None to disable
    the SOCKS5 server
    @param TunnelSettings settings: the settings to pass to the ProxyCommunity
    """

    def __init__(self, socks5_port, settings=None):
        self.settings = settings
        self.socks5_port = socks5_port or random.randint(1000, 65535)
        self.socks5_server = None

        self.start_tribler()
        self.dispersy = self.session.lm.dispersy
        self.community = None

    def start_tribler(self):
        config = SessionStartupConfig()
        config.set_state_dir(os.path.join(BASE_DIR, ".Tribler-%d") % self.socks5_port)
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_swift_proc(True)
        config.set_mainline_dht(False)
        config.set_torrent_collecting(False)
        config.set_libtorrent(True)
        config.set_dht_torrent_collecting(False)
        config.set_videoplayer(False)
        config.set_dispersy_tunnel_over_swift(True)
        config.set_dispersy_port(-1)  # select random port
        config.set_swift_tunnel_listen_port(-1)
        self.session = Session(config)
        self.session.start()
        print >> sys.stderr, "Using ports %d for dispersy and %d for swift tunnel" % (self.session.get_dispersy_port(), self.session.get_swift_tunnel_listen_port())

    def run(self):
        def start_community():
            member = self.dispersy.get_new_member(u"NID_secp160k1")
            self.community = self.dispersy.define_auto_load(TunnelCommunity, member,
                                                            (self.raw_server, False, self.settings),
                                                            load=True)[0]
        blockingCallFromThread(reactor, start_community)

        self.socks5_server = self.community.socks_server
        raw_server_thread = Thread(target=self.raw_server.listen_forever, args=(None,))
        raw_server_thread.start()

    def stop(self):
        if self.session:
            session_shutdown_start = time.time()
            waittime = 60
            self.session.shutdown()
            while not self.session.has_shutdown():
                diff = time.time() - session_shutdown_start
                assert diff < waittime, "Took too long for Session to shutdown"
                print >> sys.stderr, "ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds" % (waittime - diff)
                time.sleep(1)
            print >> sys.stderr, "Session is shutdown"
            Session.del_instance()


class LineHandler(LineReceiver):
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
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P':
            if profile:
                filename = 'callgrindc_%d.yappi' % anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c':
            print "========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)"
            for circuit_id, circuit in anon_tunnel.community.circuits.items():
                print "%d\t%s:%d\t%d\t%d\t\t%.2f\t\t%.2f" % (circuit_id, circuit.first_hop[0],
                                                             circuit.first_hop[1], circuit.goal_hops,
                                                             len(circuit.hops),
                                                             circuit.bytes_down / 1024.0 / 1024.0,
                                                             circuit.bytes_up / 1024.0 / 1024.0)
        elif line == 'q':
            anon_tunnel.stop()
            os._exit(0)
            return
        elif line == 'r':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)"

            from_to = anon_tunnel.community.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f" % ((key[0], key[1]), (relay.sock_addr, relay.circuit_id),
                                             relay.bytes[1] / 1024.0 / 1024.0,)

def main(argv):
    parser = argparse.ArgumentParser(description='Anonymous Tunnel CLI interface')

    try:
        parser.add_argument('-p', '--socks5', help='Socks5 port')
        parser.add_argument('-y', '--yappi', help="Profiling mode, either 'wall' or 'cpu'")
        parser.add_argument('--max-circuits', nargs=1, default=10, help='Maximum number of circuits to create')
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

    anon_tunnel = AnonTunnel(socks5_port, TunnelSettings())
    StandardIO(LineHandler(anon_tunnel, profile))
    anon_tunnel.run()

if __name__ == "__main__":
    main(sys.argv[1:])
