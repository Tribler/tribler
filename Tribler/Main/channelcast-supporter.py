#!/usr/bin/python

# used to 'support' .torrent files dissemination of different
# channels.  make sure that it gets an existing megacache where it is
# subscribed to one or more channels.

# modify the sys.stderr and sys.stdout for safe output
import Tribler.Debug.console

from traceback import print_exc
import optparse
import os
import random
import shutil
import sys
import tempfile
import time

from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT

from Tribler.Core.Overlay.permid import permid_for_user

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    print "Press Ctrl-C to stop the metadata-injector"

    sscfg = SessionStartupConfig()
    if opt.statedir: sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port: sscfg.set_listen_port(opt.port)
    if opt.nickname: sscfg.set_nickname(opt.nickname)
    
    # set_moderationcast_promote_own() will ensure your moderations on
    # the RSS feed items are sent to any peer you connect to on the
    # overlay.

    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    # turn torrent collecting on. this will cause torrents to be distributed
    sscfg.set_torrent_collecting(True)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    session = Session(sscfg)

    def on_incoming_torrent(subject, type_, infohash):
        print >>sys.stdout, "Incoming torrent:", infohash.encode("HEX")
    session.add_observer(on_incoming_torrent, NTFY_TORRENTS, [NTFY_INSERT])

    print >>sys.stderr, "permid: ", permid_for_user(session.get_permid())    

    try:
        while True:
            x = sys.stdin.read()
    except:
        print_exc()
    
    session.shutdown()
    print "Shutting down..."
    time.sleep(5)    

if __name__ == "__main__":
    main()
