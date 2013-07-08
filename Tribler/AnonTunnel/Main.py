import os
import logging.config

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import time
from DispersyTunnelProxy import DispersyTunnelProxy
from Socks5AnonTunnel import Socks5AnonTunnel

import sys, getopt


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hs", ["start"])
    except getopt.GetoptError:
        print 'Main.py [--start]'
        sys.exit(2)

    should_start = False

    for opt, arg in opts:
        if opt == '-h':
            print 'Main.py [--start]'
            sys.exit()
        elif opt in ("-s", "--start"):
            should_start = True

    tunnel = DispersyTunnelProxy()

    if should_start:
        tunnel.start()

    Socks5AnonTunnel(tunnel, 1080).run()

    while 1:
        time.sleep(1)


if __name__ == "__main__":
    main(sys.argv[1:])

