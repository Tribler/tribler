import logging.config
import os
logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import threading
import yappi
from Tribler.AnonTunnel.AnonTunnel import AnonTunnel


import sys, getopt


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hy", ["yappi", "cmd=", "socks5="])
    except getopt.GetoptError:
        print 'Main.py [--yappi]'
        sys.exit(2)

    profile = False

    cmd_port = 1081
    socks5_port = 1080

    for opt, arg in opts:
        if opt == '-h':
            print 'Main.py [--yappi] [--socks5 <port>] [--cmd <port>]'
            sys.exit()
        elif opt in( "-y", "--yappi"):
            profile = True
        elif opt == '--cmd':
            cmd_port = int(arg)
        elif opt == '--socks5':
            socks5_port = int(arg)

    if profile:
        yappi.start()

    anonTunnel = AnonTunnel(socks5_port, cmd_port)

    anonTunnel.start()

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            anonTunnel.stop()
            break

        if not line:
            break

        if line == 'threads\n':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name,  thread.ident)
        elif line == 'p\n':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name


                filename = 'callgrind_%d.yappi' % anonTunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"
        elif line == 'q\n':
            anonTunnel.stop()
            break



if __name__ == "__main__":
    main(sys.argv[1:])

