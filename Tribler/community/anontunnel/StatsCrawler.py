import logging.config
import os
import re
from threading import Thread, Event
from time import sleep
from traceback import print_exc
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ProxyCommunity import ProxyCommunity
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import RawserverEndpoint

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import threading
import yappi
from Tribler.community.anontunnel.AnonTunnel import AnonTunnel

import sys, getopt


class StatsCrawler(Thread):
    def run(self):
        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    10.0 / 5.0,
                                    10.0,
                                    ipv6_enable=False)

        self.callback = Callback()

        self.endpoint = RawserverEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")

        def join_overlay(dispersy):
            dispersy.define_auto_load(ProxyCommunity,
                                      (self.dispersy.get_new_member(), None, False),
                                      load=True)


        self.dispersy.start()
        self.dispersy.callback.call(join_overlay, (self.dispersy,))

        while True:
            communities = self.dispersy.get_communities()
            proxy_communities = filter(lambda c: isinstance(c, ProxyCommunity), communities)

            if proxy_communities:
                logger.error("Community loaded")
                self.community = proxy_communities[0]
                self.community.subscribe("on_stats", self.on_stats)
                break

            sleep(1)


        self.raw_server.listen_forever(None)
        

    def on_stats(self, e):
        print e.message.payload.stats


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hy", ["yappi=", "cmd=", "socks5="])
    except getopt.GetoptError:
        print 'Main.py [--yappi]'
        sys.exit(2)

    profile = None

    stats_crawler = StatsCrawler()
    stats_crawler.start()

    cmd_port = 1081
    socks5_port = 1080

    for opt, arg in opts:
        if opt == '-h':
            print 'Main.py [--yappi] [--socks5 <port>] [--cmd <port>]'
            sys.exit()
        elif opt in ( "-y", "--yappi"):
            if arg == 'wall':
                profile = "wall"
            else:
                profile = "cpu"

        elif opt == '--cmd':
            cmd_port = int(arg)
        elif opt == '--socks5':
            socks5_port = int(arg)

    if profile:
        yappi.set_clock_type(profile)
        yappi.start(builtins=True)
        print "Profiling using %s time" % yappi.get_clock_type()['type']

    regex_cmd_extend_circuit = re.compile("e ?([0-9]+)\n")

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:

            break

        if not line:
            break

        cmd_extend_match = regex_cmd_extend_circuit.match(line)

        if line == 'threads\n':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name, thread.ident)
        elif line == 'p\n':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P\n':
            if profile:
                filename = 'callgrindc_%d.yappi' % anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c\n':
            print "========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)\tIN (kBps)\tOUT (kBps)"
            for circuit in anon_tunnel.tunnel.circuits.values():
                print "%d\t%s\t%d\t%d\t\t%.2f\t\t%.2f\t\t%.2f\t\t%.2f" % (
                    circuit.id, circuit.candidate, circuit.goal_hops, len(circuit.hops),
                    circuit.bytes_downloaded / 1024.0 / 1024.0,
                    circuit.bytes_uploaded / 1024.0 / 1024.0,
                    (circuit.speed_down[-1] if len(circuit.speed_down) else 0) / 1024.0,
                    (circuit.speed_up[-1] if len(circuit.speed_up) else 0) / 1024.0
                )

                for hop in circuit.hops[1:]:
                    print "\t%s" % (hop,)

        elif cmd_extend_match:
            circuit_id = int(cmd_extend_match.group(1))

            if circuit_id in anon_tunnel.tunnel.circuits:
                circuit = anon_tunnel.tunnel.circuits[circuit_id]
                anon_tunnel.tunnel.extend_circuit(circuit)

        elif line == 'q\n':
            anon_tunnel.stop()
            break

        elif line == 'r\n':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)\tSpeed (kBps)"

            from_to = anon_tunnel.tunnel.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f\t\t%.2f" % (
                    (key[0].sock_addr, key[1]), (relay.candidate.sock_addr, relay.circuit_id),
                    relay.bytes[1] / 1024.0 / 1024.0,
                    relay.speed[-1] if len(relay.speed) else 0
                )


if __name__ == "__main__":
    main(sys.argv[1:])

