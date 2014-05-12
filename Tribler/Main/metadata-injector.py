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
import sys
import time
import json
from hashlib import sha1
import logging
import logging.config
import binascii

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Main.Utility.Feeds.rssparser import RssParser
from Tribler.Main.Utility.Feeds.dirfeed import DirectoryFeedThread
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, LibraryManager, \
    ChannelManager
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager

from twisted.internet import reactor

logger = logging.getLogger(__name__)

@call_on_reactor_thread
def define_communities(session):
    from Tribler.community.allchannel.community import AllChannelCommunity
    from Tribler.community.channel.community import ChannelCommunity
    from Tribler.community.metadata.community import MetadataCommunity

    dispersy = session.get_dispersy_instance()
    dispersy.define_auto_load(AllChannelCommunity,
                                (session.dispersy_member,),
                                {},
                                load=True)
    dispersy.define_auto_load(ChannelCommunity, load=True)
    dispersy.define_auto_load(MetadataCommunity,
                               (session.dispersy_member,),
                               {},
                               load=True)
    logger.info(u"Dispersy communities are ready")

def dispersy_started(session, opt, torrentManager, channelManager,
        torrentStateManager):
    channelname = opt.channelname if hasattr(opt, 'chanelname') else ''
    nickname = opt.nickname if hasattr(opt, 'nickname') else ''
    my_channel_name = channelname or nickname or 'MetadataInjector-Channel'
    my_channel_name = unicode(my_channel_name)

    new_channel_created = False
    my_channel_id = channelManager.channelcast_db.getMyChannelId()
    if not my_channel_id:
        logger.info(u"Create a new channel")
        channelManager.createChannel(my_channel_name, u'')
        new_channel_created = True
    else:
        logger.info(u"Use existing channel %s", binascii.hexlify(my_channel_id))
        my_channel = channelManager.getChannel(my_channel_id)
        if my_channel.name != my_channel_name:
            logger.info(u"Rename channel to %s", my_channel_name)
            channelManager.modifyChannel(my_channel_id, {'name': my_channel_name})
    my_channel_id = channelManager.channelcast_db.getMyChannelId()
    logger.info(u"Channel ID [%s]", my_channel_id)

    def createTorrentFeed():
        logger.info(u"Creating RSS Feed...")

        torrentfeed = RssParser.getInstance()
        torrentfeed.register(session, my_channel_id)
        torrentfeed.addCallback(my_channel_id, torrentManager.createMetadataModificationFromDef)

        for rss in opt.rss.split(";"):
            torrentfeed.addURL(rss, my_channel_id)

    if hasattr(opt, 'rss') and opt.rss:
        createTorrentFeed()

    def createDirFeed():
        logger.info(u"Creating Dir Feed...")

        def on_torrent_callback(dirpath, infohash, torrent_data):
            torrentdef = TorrentDef.load_from_dict(torrent_data)
            channelManager.createTorrentFromDef(my_channel_id, torrentdef)

            # save torrent to collectedtorrents
            filename = torrentManager.getCollectedFilenameFromDef(torrentdef)
            if not os.path.isfile(filename):
                torrentdef.save(filename)

        dirfeed = DirectoryFeedThread.getInstance()
        for dirpath in opt.dir.split(";"):
            dirfeed.addDir(dirpath, callback=on_torrent_callback)

    if hasattr(opt, 'dir') and opt.dir:
        createDirFeed()

    def createFileFeed():
        logger.info(u"Creating File Feed...")
        community = channelManager._disp_get_community_from_channel_id(my_channel_id)

        logger.info("Using community: %s", community._cid.encode('HEX'))

        items = json.load(open(opt.file, 'rb'))
        for item in items:
            try:
                infohash = sha1(item['name']).digest()
            except:
                infohash = sha1(str(random.randint(0, 1000000))).digest()
            message = community._disp_create_torrent(infohash, long(time.time()), unicode(item['name']), ((u'fake.file', 10),), tuple(), update=False, forward=False)

            logger.info("Created a new torrent")

            latest_review = None
            for modification in item['modifications']:
                reviewmessage = community._disp_create_modification('description', unicode(modification['text']), long(time.time()), message, latest_review, update=False, forward=False)

                logger.info("Created a new modification")

                if modification['revert']:
                    community._disp_create_moderation('reverted', long(time.time()), 0, reviewmessage.packet_id, update=False, forward=False)

                    logger.info("Reverted the last modification")
                else:
                    latest_review = reviewmessage

    if hasattr(opt, 'file') and opt.file and new_channel_created:
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
        logger.info("\nExample: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja --channelname goldenoldies")
        sys.exit()

    logger.info("Type Q followed by <ENTER> to stop the metadata-injector")

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

    torrentManager = TorrentManager(None)
    libraryManager = LibraryManager(None)
    channelManager = ChannelManager()
    torrentManager.connect(session, libraryManager, channelManager)
    libraryManager.connect(session, torrentManager, channelManager)
    channelManager.connect(session, libraryManager, torrentManager)

    torrentStateManager = TorrentStateManager(None)
    torrentStateManager.connect(torrentManager, libraryManager, channelManager)

    dispersy = session.get_dispersy_instance()
    define_communities()
    reactor.callFromThread(dispersy_started, session, opt, torrentManager, channelManager, torrentStateManager)

    # condition variable would be prettier, but that don't listen to
    # KeyboardInterrupt
    try:
        while True:
            x = sys.stdin.readline()
            logger.info(repr(x))
            if x.strip() == 'Q':
                break
    except:
        print_exc()

    torrentfeed = RssParser.getInstance()
    torrentfeed.shutdown()

    dirfeed = DirectoryFeedThread.getInstance()
    dirfeed.shutdown()

    torrentStateManager.delInstance()
    channelManager.delInstance()
    libraryManager.delInstance()
    torrentManager.delInstance()

    session.shutdown()
    logger.info("Shutting down...")
    time.sleep(5)

if __name__ == "__main__":
    logging.config.fileConfig("logger.conf")
    main()
