#!/usr/bin/python

from traceback import print_exc
import optparse
import os
import sys
import time

from Tribler.Core.API import SessionStartupConfig, Session

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name", default="Booster")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not opt.statedir:
        command_line_parser.print_help()
        print "\nExample: python", sys.argv[0], "--statedir /home/tribler/booster --nickname Booster"
        sys.exit()

    print "Press Ctrl-C to stop the booster"

    sscfg = SessionStartupConfig()
    if opt.statedir: sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port: sscfg.set_listen_port(opt.port)
    if opt.nickname: sscfg.set_nickname(opt.nickname)

    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    # turn torrent collecting on. this will cause torrents to be distributed
    sscfg.set_torrent_collecting(True)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    session = Session(sscfg)

    # KeyboardInterrupt
    try:
        while True:
            sys.stdin.read()
    except:
        print_exc()

    session.shutdown()
    print "Shutting down..."
    time.sleep(5)

if __name__ == "__main__":
    main()
