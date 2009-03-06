#!/usr/bin/python

from traceback import print_exc
import optparse
import os
import random
import shutil
import sys
import tempfile
import time
import re

from Tribler.Core.API import *

if __name__ == "__main__":

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--quick-connect", action="store", type="string", help="Immediately make an overlay connection to the supplied k.l.m.n:o address")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    # what types of crawlers do we have?
    options = ["database", "seedingstats", "friendship", "natcheck", "videoplayback"]
    options.sort()

    # at least on crawler type should be started
    if not filter(lambda type_:type_ in args, options):
        print "Usage: python Tribler/Main/crawler.py"
        print "  --statedir STATEDIR                    (optional)"
        print "  --port PORT                            (optional)"
        print "  --quick-connect IPADDRESS:PORT         (optional)"
        for option in options:
            print "  %-38s (optional)" % option
        sys.exit()

    print "Press Ctrl-C to stop the crawler"

    sscfg = SessionStartupConfig()
    if opt.statedir:
        sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port:
        sscfg.set_listen_port(opt.port)
    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    sscfg.set_torrent_collecting(False)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    s = Session(sscfg)

    # 22/10/08. Boudewijn: connect to a specific peer
    # connect to a specific peer using the overlay
    if opt.quick_connect:
        match = re.match("([0-9]+)[.]([0-9]+)[.]([0-9]+)[.]([0-9]+)(?::([0-9]+))?", opt.quick_connect)
        if match:
            groups = list(match.groups())
            if not groups[4]:
                groups[4] = "7762"
            def after_connect(*args):
                print args
            from Tribler.Core.Overlay.SecureOverlay import SecureOverlay

            ip = ".".join(groups[0:4])
            port = int(groups[4])

            print "Creating an overlay connection to", ip, port
            overlay = SecureOverlay.getInstance()
            overlay.connect_dns((ip, port), after_connect)

        else:
            print "Could not decipher the --quick-connect address"
            raise SystemExit

    # condition variable would be prettier, but that don't listen to 
    # KeyboardInterrupt
    #time.sleep(sys.maxint/2048)
    try:
        while True:
            x = sys.stdin.read()
    except:
        print_exc()
    
    s.shutdown()
    time.sleep(3)    

    
