import logging.config
import os

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import threading
import yappi
from Tribler.community.anontunnel.AnonTunnel import AnonTunnel

import sys, getopt


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hy", ["yappi=", "cmd=", "socks5="])
    except getopt.GetoptError:
        print 'Main.py [--yappi]'
        sys.exit(2)

    profile = None

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

    anon_tunnel = AnonTunnel(socks5_port, cmd_port)

    anon_tunnel.start()

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            anon_tunnel.stop()
            break

        if not line:
            break

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
                filename = 'callgrind_%d.yappi' % anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c\n':
            print "========\nCircuits\n========\nid\taddress\t\t\t\thops"
            for circuit in anon_tunnel.tunnel.circuits.values():
                print "%d\t%s\t%d\n" % (circuit.id, circuit.address, len(circuit.hops))

        elif line == 'q\n':
            anon_tunnel.stop()
            break


if __name__ == "__main__":
    main(sys.argv[1:])

