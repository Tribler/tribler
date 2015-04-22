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
import binascii

from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor, reactor_thread
from Tribler.dispersy.util import call_on_reactor_thread

from Tribler.Core.simpledefs import NTFY_DISPERSY, NTFY_STARTED
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Utilities.misc_utils import compute_ratio
from Tribler.Main.Utility.Feeds.rssparser import RssParser
from Tribler.Main.Utility.Feeds.dirfeed import DirectoryFeedThread
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, LibraryManager, ChannelManager
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager
from Tribler.Main.Utility.utility import eta_value, size_format


class MetadataInjector(object):

    def __init__(self, opt):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._opt = opt
        self.session = None

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
        sscfg.set_enable_torrent_search(False)
        sscfg.set_enable_channel_search(True)

        self._logger.info(u"Starting session...")
        self.session = Session(sscfg)
        self.session.prestart()

        # add dispersy start callbacks
        self.session.add_observer(self.dispersy_started, NTFY_DISPERSY, [NTFY_STARTED])
        self.session.start()

    def init_managers(self):
        self._logger.info(u"Initializing managers...")
        torrent_manager = TorrentManager(None)
        library_manager = LibraryManager(None)
        channel_manager = ChannelManager()
        torrent_manager.connect(self.session, library_manager, channel_manager)
        library_manager.connect(self.session, torrent_manager, channel_manager)
        channel_manager.connect(self.session, library_manager, torrent_manager)

        #torrent_state_manager = TorrentStateManager()
        #torrent_state_manager.connect(torrent_manager, library_manager, channel_manager)

        self._torrent_manager = torrent_manager
        self._library_manager = library_manager
        self._channel_manager = channel_manager
        #self._torrent_state_manager = torrent_state_manager

    def shutdown(self):
        self._logger.info(u"Shutting down metadata-injector...")
        torrentfeed = RssParser.getInstance()
        torrentfeed.shutdown()

        dirfeed = DirectoryFeedThread.getInstance()
        dirfeed.shutdown()

        #self._torrent_state_manager.delInstance()
        self._channel_manager.delInstance()
        self._library_manager.delInstance()
        self._torrent_manager.delInstance()

        self.session.shutdown()

        #self._torrent_state_manager = None
        self._channel_manager = None
        self._library_manager = None
        self._torrent_manager = None
        self.session = None

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
            torrentfeed.register(self.session, my_channel_id)
            torrentfeed.addCallback(my_channel_id, self._channel_manager.createTorrentFromDef)
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
                torrent = self._torrent_manager.getTorrentByInfohash(torrentdef.infohash)
                filename = self._torrent_manager.getCollectedFilename(torrent) if torrent else None
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
                message = community._disp_create_torrent(infohash, long(time.time()), unicode(
                    item['name']), ((u'fake.file', 10),), tuple(), update=False, forward=False)

                self._logger.info("Created a new torrent")

                latest_review = None
                for modification in item['modifications']:
                    reviewmessage = community._disp_create_modification('description', unicode(
                        modification['text']), long(time.time()), message, latest_review, update=False, forward=False)

                    self._logger.info("Created a new modification")

                    if modification['revert']:
                        community._disp_create_moderation(
                            'reverted', long(time.time()), 0, reviewmessage.packet_id, update=False, forward=False)

                        self._logger.info("Reverted the last modification")
                    else:
                        latest_review = reviewmessage

        if hasattr(self._opt, 'file') and self._opt.file and new_channel_created:
            create_file_feed()


def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int", help="Listen at this port")
    command_line_parser.add_option("--rss", action="store", type="string",
                                   help="Url where to fetch rss feed, or several seperated with ';'")
    command_line_parser.add_option("--dir", action="store", type="string",
                                   help="Directory to watch for .torrent files, or several seperated with ';'")
    command_line_parser.add_option("--file", action="store", type="string", help="JSON file which has a community")
    command_line_parser.add_option("--nickname", action="store", type="string", help="The moderator name")
    command_line_parser.add_option("--channelname", action="store", type="string", help="The channel name")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not (opt.rss or opt.dir or opt.file):
        command_line_parser.print_help()
        print >> sys.stderr, u"\nExample: python Tribler/Main/metadata-injector.py --rss http://frayja.com/rss.php --nickname frayja --channelname goldenoldies"
        sys.exit()

    metadata_injector = MetadataInjector(opt)
    metadata_injector.initialize()

    print >> sys.stderr, u"Type Q followed by <ENTER> to stop the metadata-injector"
    # condition variable would be prettier, but that don't listen to
    # KeyboardInterrupt
    try:
        while True:
            x = sys.stdin.readline()
            if x.strip() == 'Q':
                break

            tokens = x.strip().split(" ")
            if len(tokens) == 0:
                continue

            metadata_injector.session.lm.dispersy.statistics.update()
            if tokens[0] == 'print':
                if len(tokens) < 2:
                    continue

                if tokens[1] == 'info':
                    print_info(metadata_injector.session.lm.dispersy)
                elif tokens[1] == 'community':
                    if len(tokens) == 2:
                        print_communities(metadata_injector.session.lm.dispersy)
                    elif len(tokens) == 3:
                        print_community(metadata_injector.session.lm.dispersy, tokens[2])
    except:
        print_exc()
    metadata_injector.shutdown()
    stop_reactor()

    print >> sys.stderr, u"Shutting down (wait for 5 seconds)..."
    time.sleep(5)


def print_info(dispersy):
    stats = dispersy.statistics
    print >> sys.stderr, u"\n\n===== Dispersy Info ====="
    print >> sys.stderr, u"- WAN Address %s:%d" % stats.wan_address
    print >> sys.stderr, u"- LAN Address %s:%d" % stats.lan_address
    print >> sys.stderr, u"- Connection: %s" % unicode(stats.connection_type)
    print >> sys.stderr, u"- Runtime: %s" % eta_value(stats.timestamp - stats.start)
    print >> sys.stderr, u"- Download: %s or %s/s" % (size_format(stats.total_down),
                                                      size_format(int(stats.total_down / (stats.timestamp - stats.start))))
    print >> sys.stderr, u"- Upload: %s or %s/s" % (size_format(stats.total_up),
                                                    size_format(int(stats.total_up / (stats.timestamp - stats.start))))
    print >> sys.stderr, u"- Packets Sent: %s" % compute_ratio(stats.total_send,
                                                               stats.total_received + stats.total_send)
    print >> sys.stderr, u"- Packets Received: %s" % compute_ratio(stats.total_received,
                                                                   stats.total_received + stats.total_send)
    print >> sys.stderr, u"- Packets Success: %s" % compute_ratio(stats.msg_statistics.success_count,
                                                                  stats.total_received)
    print >> sys.stderr, u"- Packets Dropped: %s" % compute_ratio(stats.msg_statistics.drop_count, stats.total_received)
    print >> sys.stderr, u"- Packets Delayed: %s" % compute_ratio(stats.msg_statistics.delay_received_count,
                                                                  stats.total_received)
    print >> sys.stderr, u"- Packets Delayed send: %s" % compute_ratio(stats.msg_statistics.delay_send_count,
                                                                       stats.msg_statistics.delay_received_count)
    print >> sys.stderr, u"- Packets Delayed success: %s" % compute_ratio(stats.msg_statistics.delay_success_count,
                                                                          stats.msg_statistics.delay_received_count)
    print >> sys.stderr, u"- Packets Delayed timeout: %s" % compute_ratio(stats.msg_statistics.delay_timeout_count,
                                                                          stats.msg_statistics.delay_received_count)
    print >> sys.stderr, u"- Walker Success: %s" % compute_ratio(stats.walk_success_count, stats.walk_attempt_count)
    print >> sys.stderr, u"- Sync-Messages Created: %s" % stats.msg_statistics.created_count
    print >> sys.stderr, u"- Bloom New: %s" % compute_ratio(sum(c.sync_bloom_new for c in stats.communities),
                                                            sum(c.sync_bloom_send + c.sync_bloom_skip
                                                                for c in stats.communities))
    print >> sys.stderr, u"- Bloom Reused: %s" % compute_ratio(sum(c.sync_bloom_reuse for c in stats.communities),
                                                               sum(c.sync_bloom_send + c.sync_bloom_skip
                                                                   for c in stats.communities))
    print >> sys.stderr, u"- Bloom Skipped: %s" % compute_ratio(sum(c.sync_bloom_skip for c in stats.communities),
                                                                sum(c.sync_bloom_send + c.sync_bloom_skip
                                                                    for c in stats.communities))
    print >> sys.stderr, u"- Debug Mode: %s" % u"yes" if __debug__ else u"no"
    print >> sys.stderr, u"====================\n\n"


def print_communities(dispersy):
    stats = dispersy.statistics
    community_list = sorted(stats.communities,
                            key=lambda community:
                            (not community.dispersy_enable_candidate_walker,
                             community.classification, community.cid)
                            )

    print >> sys.stderr, u"\n\n===== Dispersy Communities ====="
    print >> sys.stderr, u"- %15s | %7s | %7s | %5s | %7s | %5s | %5s | %14s | %14s | %14s | %14s" %\
                         (u"Class", u"ID", u"Member", u"DB ID", u"GTime", u"Cands",
                          u"PK_cr", u"PK_sent", u"PK_recv", u"PK_succ", u"PK_drop")

    for community in community_list:
        print >> sys.stderr, u"- %15s | %7s | %7s | %5s | %7s | %5s | %5s | %14s | %14s | %14s | %14s" %\
                             (community.classification.replace('Community', ''),
                              community.hex_cid[:7],
                              community.hex_mid[:7],
                              community.database_id,
                              str(community.global_time)[:7], len(community.candidates),
                              community.msg_statistics.created_count,
                              compute_ratio(community.msg_statistics.outgoing_count,
                                            community.msg_statistics.outgoing_count
                                            + community.msg_statistics.total_received_count),
                              compute_ratio(community.msg_statistics.total_received_count,
                                            community.msg_statistics.outgoing_count
                                            + community.msg_statistics.total_received_count),
                              compute_ratio(community.msg_statistics.success_count,
                                            community.msg_statistics.total_received_count),
                              compute_ratio(community.msg_statistics.drop_count,
                                            community.msg_statistics.total_received_count),)
    print >> sys.stderr, u"====================\n\n"


def print_community(dispersy, cid):
    stats = dispersy.statistics
    community = None
    for comm in stats.communities:
        if comm.hex_cid.startswith(cid):
            community = comm
            break

    if not community:
        print >> sys.stderr, u"Community not found"
        return

    print >> sys.stderr, u"\n\n===== Dispersy Community ====="

    FORMAT = u"- %20s: %20s"
    print >> sys.stderr, FORMAT % (u"Classification", community.classification.replace('Community', ''))
    print >> sys.stderr, FORMAT % (u"ID", community.hex_cid)
    print >> sys.stderr, FORMAT % (u"Member", community.hex_mid)
    print >> sys.stderr, FORMAT % (u"Database ID", community.database_id)
    print >> sys.stderr, FORMAT % (u"Global Time", community.global_time)

    print >> sys.stderr, FORMAT % (u"Candidates", len(community.candidates))
    print >> sys.stderr, u"--- %20s | %21s | %21s | %20s" % (u"GTime", u"LAN", u"WAN", u"MID")
    for candidate in community.candidates:
        lan, wan, global_time, mid = candidate
        lan = u"%s:%s" % lan
        wan = u"%s:%s" % wan
        print >> sys.stderr, u"--- %20s | %21s | %21s | %20s" % (global_time, lan, wan,
                                                                 binascii.hexlify(mid) if mid else None)
    print >> sys.stderr, u"====================\n\n"


if __name__ == "__main__":
    logging.config.fileConfig(u"logger.conf")
    main()
