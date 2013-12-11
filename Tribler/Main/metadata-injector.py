#!/usr/bin/python

# injector.py is used to 'inject' .torrent files into the overlay
# network.
# Currently supported sources:
#  * rss feed;
#  * watched directory.

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
import json
from hashlib import sha1

from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Main.Utility.Feeds.rssparser import RssParser
from Tribler.Main.Utility.Feeds.dirfeed import DirectoryFeedThread

from Tribler.community.channel.community import forceDispersyThread

def define_communities(session):
    from Tribler.community.allchannel.community import AllChannelCommunity
    from Tribler.community.channel.community import ChannelCommunity

    dispersy = session.get_dispersy_instance()
    dispersy.define_auto_load(AllChannelCommunity,
                                   (session.dispersy_member,),
                                   {},
                                   load=True)
    dispersy.define_auto_load(ChannelCommunity, load=True)
    print >> sys.stderr, "tribler: Dispersy communities are ready"

def dispersy_started(session, opt):
    from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, LibraryManager, ChannelManager
    torrentManager = TorrentManager(None)
    libraryManager = LibraryManager(None)
    channelManager = ChannelManager()

    torrentManager.connect(session, libraryManager, channelManager)
    channelManager.connect(session, libraryManager, torrentManager)
    libraryManager.connect(session, torrentManager, channelManager)

    myChannelName = opt.channelname or opt.nickname or 'MetadataInjector-Channel'
    myChannelName = unicode(myChannelName)

    createdNewChannel = False
    myChannelId = channelManager.channelcast_db.getMyChannelId()
    if not myChannelId:
        print >> sys.stderr, "creating a new channel"
        channelManager.createChannel(myChannelName, u'')
        createdNewChannel = True

    else:
        print >> sys.stderr, "reusing previously created channel"
        myChannel = channelManager.getChannel(myChannelId)
        if myChannel.name != myChannelName:
            print >> sys.stderr, "renaming channel to", myChannelName
            channelManager.modifyChannel(myChannelId, {'name': myChannelName})

    def createTorrentFeed():
        myChannelId = channelManager.channelcast_db.getMyChannelId()

        torrentfeed = RssParser.getInstance()
        torrentfeed.register(session, myChannelId)
        torrentfeed.addCallback(myChannelId, channelManager.createTorrentFromDef)

        for rss in opt.rss.split(";"):
            torrentfeed.addURL(rss, myChannelId)

    if opt.rss:
        createTorrentFeed()

    def createDirFeed():
        myChannelId = channelManager.channelcast_db.getMyChannelId()

        def on_torrent_callback(dirpath, infohash, torrent_data):
            torrentdef = TorrentDef.load_from_dict(torrent_data)
            channelsearch_manager.createTorrentFromDef(myChannelId, torrentdef)

            # save torrent to collectedtorrents
            filename = torrentManager.getCollectedFilenameFromDef(torrentdef)
            if not os.path.isfile(filename):
                torrentdef.save(filename)

        dirfeed = DirectoryFeedThread.getInstance()
        for dirpath in opt.dir.split(";"):
            dirfeed.addDir(dirpath, callback=on_torrent_callback)

    if opt.dir:
        createDirFeed()

    def createFileFeed():
        myChannelId = channelManager.channelcast_db.getMyChannelId()
        community = channelManager._disp_get_community_from_channel_id(myChannelId)

        print >> sys.stderr, "Using community:", community._cid.encode('HEX')

        items = json.load(open(opt.file, 'rb'))
        for item in items:
            try:
                infohash = sha1(item['name']).digest()
            except:
                infohash = sha1(str(random.randint(0, 1000000))).digest()
            message = community._disp_create_torrent(infohash, long(time.time()), unicode(item['name']), ((u'fake.file', 10),), tuple(), update=False, forward=False)

            print >> sys.stderr, "Created a new torrent"

            latest_review = None
            for modification in item['modifications']:
                reviewmessage = community._disp_create_modification('description', unicode(modification['text']), long(time.time()), message, latest_review, update=False, forward=False)

                print >> sys.stderr, "Created a new modification"

                if modification['revert']:
                    community._disp_create_moderation('reverted', long(time.time()), 0, reviewmessage.packet_id, update=False, forward=False)

                    print >> sys.stderr, "Reverted the last modification"
                else:
                    latest_review = reviewmessage

    if opt.file and createdNewChannel:
        createFileFeed()

def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--rss", action="store", type="string", help="Url where to fetch rss feed, or several seperated with ';'")
    command_line_parser.add_option("--dir", action="store", type="string", help="Directory to watch for .torrent files, or several seperated with ';'")
    command_line_parser.add_option("--file", action="store", type="string", help="JSON file which has a community")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")
    command_line_parser.add_option("--channelname", action="store", type="string", help="The channel name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not (opt.rss or opt.dir or opt.file):
        command_line_parser.print_help()
        print "\nExample: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja --channelname goldenoldies"
        sys.exit()

    print "Type Q followed by <ENTER> to stop the metadata-injector"

    sscfg = SessionStartupConfig()
    if opt.statedir:
        sscfg.set_state_dir(unicode(os.path.realpath(opt.statedir)))
    if opt.port:
        sscfg.set_dispersy_port(opt.port)
    if opt.nickname:
        sscfg.set_nickname(opt.nickname)

    sscfg.set_megacache(True)
    sscfg.set_torrent_collecting(True)

    session = Session(sscfg)
    session.start()

    dispersy = s.get_dispersy_instance()
    dispersy.callback.call(define_communities, args=(session,))
    dispersy.callback.register(dispersy_started, args=(session, opt))

    # condition variable would be prettier, but that don't listen to
    # KeyboardInterrupt
    try:
        while True:
            x = sys.stdin.readline()
            print >> sys.stderr, x
            if x.strip() == 'Q':
                break
    except:
        print_exc()

    torrentfeed = RssParser.getInstance()
    torrentfeed.shutdown()

    dirfeed = DirectoryFeedThread.getInstance()
    dirfeed.shutdown()

    session.shutdown()
    print "Shutting down..."
    time.sleep(5)

if __name__ == "__main__":
    main()
