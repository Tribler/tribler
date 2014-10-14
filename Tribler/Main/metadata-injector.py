#!/usr/bin/python

# injector.py is used to 'inject' .torrent files into the overlay
# network.
# Currently supported sources:
#  * rss feed;
#  * watched directory.

# modify the sys.stderr and sys.stdout for safe output

import optparse
import os
import random
import sys
import time
import json
from hashlib import sha1
import logging
import logging.config
from traceback import print_exc

from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor, reactor_thread
from Tribler.dispersy.util import call_on_reactor_thread

from Tribler.Core.simpledefs import NTFY_DISPERSY, NTFY_STARTED
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Main.Utility.Feeds.rssparser import RssParser
from Tribler.Main.Utility.Feeds.dirfeed import DirectoryFeedThread
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, LibraryManager, ChannelManager
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager


class MetadataInjector(object):

    def __init__(self, opt):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._opt = opt
        self._session = None

        self._torrent_manager = None
        self._library_manager = None
        self._channel_manager = None
        self._torrent_state_manager = None

    def initialize(self):
        sscfg = SessionStartupConfig()
        if self._opt.statedir:
            sscfg.set_state_dir(unicode(os.path.realpath(self._opt.statedir)))
        if self._opt.port:
            sscfg.set_dispersy_port(self._opt.port)
        if self._opt.nickname:
            sscfg.set_nickname(self._opt.nickname)

        sscfg.set_megacache(True)
        sscfg.set_torrent_collecting(True)

        self._logger.info(u"Starting session...")
        self._session = Session(sscfg)
        # add dispersy start callbacks
        #self._session.add_observer(self.init_managers, NTFY_DISPERSY, [NTFY_STARTED])
        self._session.add_observer(self.define_communities, NTFY_DISPERSY, [NTFY_STARTED])
        self._session.add_observer(self.dispersy_started, NTFY_DISPERSY, [NTFY_STARTED])
        self._session.start()

    def init_managers(self):
        self._logger.info(u"Initializing managers...")
        torrent_manager = TorrentManager(None)
        library_manager = LibraryManager(None)
        channel_manager = ChannelManager()
        torrent_manager.connect(self._session, library_manager, channel_manager)
        library_manager.connect(self._session, torrent_manager, channel_manager)
        channel_manager.connect(self._session, library_manager, torrent_manager)

        torrent_state_manager = TorrentStateManager()
        torrent_state_manager.connect(torrent_manager, library_manager, channel_manager)

        self._torrent_manager = torrent_manager
        self._library_manager = library_manager
        self._channel_manager = channel_manager
        self._torrent_state_manager = torrent_state_manager

    def shutdown(self):
        self._logger.info(u"Shutting down metadata-injector...")
        torrentfeed = RssParser.getInstance()
        torrentfeed.shutdown()

        dirfeed = DirectoryFeedThread.getInstance()
        dirfeed.shutdown()

        self._torrent_state_manager.delInstance()
        self._channel_manager.delInstance()
        self._library_manager.delInstance()
        self._torrent_manager.delInstance()

        self._session.shutdown()

        self._torrent_state_manager = None
        self._channel_manager = None
        self._library_manager = None
        self._torrent_manager = None
        self._session = None

    @call_on_reactor_thread
    def define_communities(self, *args):
        from Tribler.community.allchannel.community import AllChannelCommunity
        from Tribler.community.channel.community import ChannelCommunity
        from Tribler.community.metadata.community import MetadataCommunity

        dispersy = self._session.get_dispersy_instance()
        dispersy.define_auto_load(AllChannelCommunity,
                                  self._session.dispersy_member,
                                  load=True)
        dispersy.define_auto_load(ChannelCommunity,
                                  self._session.dispersy_member,
                                  load=True)
        dispersy.define_auto_load(MetadataCommunity,
                                  self._session.dispersy_member,
                                  load=True)
        self._logger.info(u"Dispersy communities are ready")

    def dispersy_started(self, *args):
        self._logger.info(u"Dispersy started, initializing bot...")
        self.init_managers()

        channelname = self._opt.channelname if hasattr(self._opt, 'channelname') else ''
        nickname = self._opt.nickname if hasattr(self._opt, 'nickname') else ''
        my_channel_name = channelname or nickname or 'MetadataInjector-Channel'
        my_channel_name = unicode(my_channel_name)

        new_channel_created = False
        my_channel_id = self._channel_manager.channelcast_db.getMyChannelId()
        if not my_channel_id:
            self._logger.info(u"Create a new channel")
            self._channel_manager.createChannel(my_channel_name, u'')
            new_channel_created = True
        else:
            self._logger.info(u"Use existing channel %s", str(my_channel_id))
            my_channel = self._channel_manager.getChannel(my_channel_id)
            if my_channel.name != my_channel_name:
                self._logger.info(u"Rename channel to %s", my_channel_name)
                self._channel_manager.modifyChannel(my_channel_id, {'name': my_channel_name})
        my_channel_id = self._channel_manager.channelcast_db.getMyChannelId()
        self._logger.info(u"Channel ID [%s]", my_channel_id)

        def create_torrent_feed():
            self._logger.info(u"Creating RSS Feed...")

            torrentfeed = RssParser.getInstance()
            torrentfeed.register(self._session, my_channel_id)
            torrentfeed.addCallback(my_channel_id, self._torrent_manager.createMetadataModificationFromDef)

            for rss in self._opt.rss.split(";"):
                torrentfeed.addURL(rss, my_channel_id)

        if hasattr(self._opt, 'rss') and self._opt.rss:
            create_torrent_feed()

        def create_dir_feed():
            self._logger.info(u"Creating Dir Feed...")

            def on_torrent_callback(dirpath, infohash, torrent_data):
                torrentdef = TorrentDef.load_from_dict(torrent_data)
                self._channel_manager.createTorrentFromDef(my_channel_id, torrentdef)

                # save torrent to collectedtorrents
                filename = self._torrent_manager.getCollectedFilenameFromDef(torrentdef)
                if not os.path.isfile(filename):
                    torrentdef.save(filename)

            dirfeed = DirectoryFeedThread.getInstance()
            for dirpath in self._opt.dir.split(";"):
                dirfeed.addDir(dirpath, callback=on_torrent_callback)

        if hasattr(self._opt, 'dir') and self._opt.dir:
            create_dir_feed()

        def create_file_feed():
            self._logger.info(u"Creating File Feed...")
            community = self._channel_manager._disp_get_community_from_channel_id(my_channel_id)

            self._logger.info("Using community: %s", community._cid.encode('HEX'))

            items = json.load(open(self._opt.file, 'rb'))
            for item in items:
                try:
                    infohash = sha1(item['name']).digest()
                except:
                    infohash = sha1(str(random.randint(0, 1000000))).digest()
                message = community._disp_create_torrent(infohash, long(time.time()), unicode(item['name']), ((u'fake.file', 10),), tuple(), update=False, forward=False)

                self._logger.info("Created a new torrent")

                latest_review = None
                for modification in item['modifications']:
                    reviewmessage = community._disp_create_modification('description', unicode(modification['text']), long(time.time()), message, latest_review, update=False, forward=False)

                    self._logger.info("Created a new modification")

                    if modification['revert']:
                        community._disp_create_moderation('reverted', long(time.time()), 0, reviewmessage.packet_id, update=False, forward=False)

                        self._logger.info("Reverted the last modification")
                    else:
                        latest_review = reviewmessage

        if hasattr(self._opt, 'file') and self._opt.file and new_channel_created:
            create_file_feed()


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
        print >> sys.stderr, "\nExample: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja --channelname goldenoldies"
        sys.exit()

    metadata_injector = MetadataInjector(opt)
    metadata_injector.initialize()

    print >> sys.stderr, "Type Q followed by <ENTER> to stop the metadata-injector"
    # condition variable would be prettier, but that don't listen to
    # KeyboardInterrupt
    try:
        while True:
            x = sys.stdin.readline()
            if x.strip() == 'Q':
                break
    except:
        print_exc()
    metadata_injector.shutdown()
    stop_reactor()

    print >> sys.stderr, "Shutting down (wait for 5 seconds)..."
    time.sleep(5)


if __name__ == "__main__":
    logging.config.fileConfig("logger.conf")
    main()
