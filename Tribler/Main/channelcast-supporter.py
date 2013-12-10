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
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT

def define_communities(session):
    from Tribler.community.allchannel.community import AllChannelCommunity
    from Tribler.community.channel.community import ChannelCommunity

    dispersy.define_auto_load(AllChannelCommunity,
                                   (session.dispersy_member,),
                                   {"auto_join_channel": True},
                                   load=True)
    dispersy.define_auto_load(ChannelCommunity, load=True)
    print >> sys.stderr, "tribler: Dispersy communities are ready"

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    print "Press Ctrl-C to stop the channelcast-supporter"

    sscfg = SessionStartupConfig()
    if opt.statedir:
        sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port:
        sscfg.set_listen_port(opt.port)
    if opt.nickname:
        sscfg.set_nickname(opt.nickname)

    sscfg.set_megacache(True)
    sscfg.set_dispersy(True)
    sscfg.set_torrent_collecting(True)

    session = Session(sscfg)
    session.start()

    dispersy = s.get_dispersy_instance()
    dispersy.callback.call(define_communities, args=(session,))

    def on_incoming_torrent(subject, type_, infohash):
        print >> sys.stdout, "Incoming torrent:", infohash.encode("HEX")
    session.add_observer(on_incoming_torrent, NTFY_TORRENTS, [NTFY_INSERT])

    try:
        while True:
            x = sys.stdin.readline()
            print >> sys.stderr, x
            if x.strip() == 'Q':
                break
    except:
        print_exc()

    session.shutdown()
    print "Shutting down..."
    time.sleep(5)

if __name__ == "__main__":
    main()
