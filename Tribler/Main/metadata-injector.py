#!/usr/bin/python

# injector.py is used to 'inject' .torrent files into the overlay
# network. currently we only support a single .torrent source: rss
# feed.

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
from Tribler.Core.Overlay.OverlayApps import OverlayApps

from Tribler.Core.Overlay.permid import permid_for_user

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--rss", action="store", type="string", help="Url where to fetch rss feed, or several seperated with ';'")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not (opt.rss):
        print "Usage: python Tribler/Main/metadata-injector.py --help"
        print "Example: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja"
        sys.exit()

    print "Press Ctrl-C to stop the metadata-injector"

    sscfg = SessionStartupConfig()
    if opt.statedir: sscfg.set_state_dir(os.path.realpath(opt.statedir))
    if opt.port: sscfg.set_listen_port(opt.port)
    if opt.nickname: sscfg.set_nickname(opt.nickname)
    
    # Agressively promote own moderations:
    sscfg.set_moderationcast_promote_own(True)

    sscfg.set_megacache(True)
    sscfg.set_overlay(True)
    # turn torrent collecting on. this will cause torrents to be distributed
    sscfg.set_torrent_collecting(True)
    sscfg.set_dialback(False)
    sscfg.set_internal_tracker(False)

    session = Session(sscfg)
    
    print >>sys.stderr, "permid: ", permid_for_user(session.get_permid())    

    if opt.rss:
        
        moderation_cast_db = session.open_dbhandler(NTFY_MODERATIONCAST)
        torrent_feed_thread = TorrentFeedThread.getInstance()
        def on_torrent_callback(rss_url, infohash, torrent_data):
            """
            A torrent file is discovered through rss. Create a new
            moderation.
            """
            if "info" in torrent_data and "name" in torrent_data["info"]:
                print >>sys.stderr, "Creating moderation for %s" % torrent_data["info"]["name"]
            else:
                print >>sys.stderr, "Creating moderation"

            moderation = {}
            moderation['infohash'] = bin2str(infohash)
            torrenthash = sha.sha(bencode(data)).digest()
            moderation['torrenthash'] = bin2str(torrenthash)

            moderation_cast_db.addOwnModeration(moderation)

        torrent_feed_thread.register(session,120,1)
        for rss in opt.rss.split(";"):
            print >>sys.stderr, "Adding RSS: %s" % rss
            torrent_feed_thread.addURL(rss, on_torrent_callback=on_torrent_callback)


        # set_moderationcast_promote_own() will ensure your moderations on
        # the RSS feed items are sent to any peer you connect to on the
        # overlay.

        torrent_feed_thread.start()

    # 22/10/08. Boudewijn: connect to a specific peer
    # connect to a specific peer using the overlay
    # def after_connect(*args):
    #     print "CONNECTED", args
    # from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
    # overlay = SecureOverlay.getInstance()
    # overlay.connect_dns(("130.161.158.24", 7762), after_connect)

    # condition variable would be prettier, but that don't listen to 
    # KeyboardInterrupt
    #time.sleep(sys.maxint/2048)
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
