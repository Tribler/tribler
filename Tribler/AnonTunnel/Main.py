import glob
import os
import logging.config
import pstats
import threading
import yappi
from Tribler.AnonTunnel.ProxyCommunity import ProxyCommunity
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import time
from DispersyTunnelProxy import DispersyTunnelProxy
from Socks5AnonTunnel import Socks5AnonTunnel

import sys, getopt



def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hsy", ["start", "yappi"])
    except getopt.GetoptError:
        print 'Main.py [--start]'
        sys.exit(2)

    should_start = False
    profile = False

    for opt, arg in opts:
        if opt == '-h':
            print 'Main.py [--start]'
            sys.exit()
        elif opt in ("-s", "--start"):
            should_start = True
        elif opt in( "-y", "--yappi"):
            profile = True

    if profile:
        yappi.start()

    callback = Callback()
    endpoint = StandaloneEndpoint(10000)
    dispersy = Dispersy(callback, endpoint, u".", u":memory:")
    dispersy.start()
    logger.info("Dispersy is listening on port %d" % dispersy.lan_address[1])

    def join_overlay(dispersy):
        master_member = dispersy.get_temporary_member_from_id("-PROXY-OVERLAY-HASH-")
        my_member = dispersy.get_new_member()
        return ProxyCommunity.join_community(dispersy, master_member, my_member)

    community = dispersy.callback.call(join_overlay,(dispersy,))

    tunnel = DispersyTunnelProxy()

    if should_start:
        tunnel.start(community)

    s5tunnel = Socks5AnonTunnel(tunnel, 1080)
    s5tunnel.start()

    def stop():
        dispersy.stop()
        s5tunnel.shutdown()

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            stop()

        if not line:
            break

        if line == 'threads\n':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name,  thread.ident)
        elif line == 'p\n':
            if profile:

                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name


                filename = 'callgrind.yappi'
                yappi.get_func_stats().save(filename, type='callgrind')

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't\n':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"
        elif line == 'q\n':
            stop()
            break;



if __name__ == "__main__":
    main(sys.argv[1:])

