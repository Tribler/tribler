#!/usr/bin/python

# injector.py is used to 'inject' .torrent files into the overlay
# network.
# Currently supported sources:
#  * rss feed;
#  * watched directory.

# modify the sys.stderr and sys.stdout for safe output

import codecs
import optparse
import os
import sys
import time
import logging
import logging.config
from traceback import print_exc
import binascii

from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor, reactor_thread
from Tribler.Core.simpledefs import NTFY_DISPERSY, NTFY_STARTED
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Utilities.misc_utils import compute_ratio
from Tribler.Main.Utility.utility import eta_value, size_format

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import call_on_reactor_thread


def parge_rss_config_file(file_path):
    rss_list = []

    f = codecs.open(file_path, 'r', encoding='utf-8')
    for line in f.readlines():
        line = line.strip()
        if not line:
            continue
        fields = line.split(u'\t')
        channel_name, rss_url = fields
        rss_list.append({u'channel_name': channel_name,
                         u'rss_url': rss_url})
    f.close()

    return rss_list


class MetadataInjector(TaskManager):

    def __init__(self, opt):
        super(MetadataInjector, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._opt = opt
        self.session = None

        self.rss_list = None

    def initialize(self):
        sscfg = SessionStartupConfig()
        if self._opt.statedir:
            sscfg.set_state_dir(unicode(os.path.realpath(self._opt.statedir)))
        if self._opt.port:
            sscfg.set_dispersy_port(self._opt.port)
        if self._opt.nickname:
            sscfg.set_nickname(self._opt.nickname)

        # pass rss config
        if not self._opt.rss_config:
            self._logger.error(u"rss_config unspecified")
        self.rss_list = parge_rss_config_file(self._opt.rss_config)

        sscfg.set_megacache(True)
        sscfg.set_torrent_collecting(True)
        sscfg.set_torrent_checking(True)
        sscfg.set_enable_torrent_search(True)
        sscfg.set_enable_channel_search(True)

        self._logger.info(u"Starting session...")
        self.session = Session(sscfg)
        self.session.prestart()

        # add dispersy start callbacks
        self.session.add_observer(self.dispersy_started, NTFY_DISPERSY, [NTFY_STARTED])
        self.session.start()

    def shutdown(self):
        self.cancel_all_pending_tasks()

        self._logger.info(u"Shutdown Session...")
        self.session.shutdown()
        self.session = None

        self._logger.info(u"Sleep for 10 seconds...")
        time.sleep(10)

    @call_on_reactor_thread
    def dispersy_started(self, *args):
        default_kwargs = {'tribler_session': self.session}

        dispersy = self.session.get_dispersy_instance()
        dispersy.define_auto_load(ChannelCommunity, self.session.dispersy_member, load=True, kargs=default_kwargs)
        dispersy.define_auto_load(PreviewChannelCommunity, self.session.dispersy_member, kargs=default_kwargs)

        self.register_task(u'prepare_channels', reactor.callLater(10, self._prepare_channels))

    def _prepare_channels(self):
        self._logger.info(u"Dispersy started, creating channels...")

        nickname = self._opt.nickname if hasattr(self._opt, 'nickname') else u''

        # get the channels that do not exist
        channel_list = []

        for community in self.session.get_dispersy_instance().get_communities():
            if not isinstance(community, ChannelCommunity):
                continue
            if community.master_member and community.master_member.private_key:
                channel_list.append(community)

        existing_channels = []
        channels_to_create = []
        for rss_dict in self.rss_list:
            channel_exists = False
            for channel in channel_list:
                if rss_dict[u'channel_name'] == channel.get_channel_name():
                    rss_dict[u'channel'] = channel
                    channel_exists = True
                    break

            if channel_exists:
                existing_channels.append(rss_dict)
            else:
                channels_to_create.append(rss_dict)

        self._logger.info(u"channels to create: %s", len(channels_to_create))
        self._logger.info(u"existing channels: %s", len(existing_channels))

        # attach rss feed to existing channels
        for rss_dict in existing_channels:
            self._logger.info(u"Creating RSS for existing Channel %s", rss_dict[u'channel_name'])
            self.session.lm.channel_manager.attach_rss_to_channel(rss_dict[u'channel'], rss_dict[u'rss_url'])

        # create new channels
        for rss_dict in channels_to_create:
            self._logger.info(u"Creating new Channel %s", rss_dict[u'channel_name'])
            self.session.lm.channel_manager.create_channel(rss_dict[u'channel_name'], u'', u"closed",
                                                           rss_dict[u'rss_url'])


def main():
    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string",
                                   help="Use an alternate statedir")
    command_line_parser.add_option("--port", action="store", type="int",
                                   help="Listen at this port")
    command_line_parser.add_option("--rss_config", action="store", type="string",
                                   help="The channel and rss config file")
    command_line_parser.add_option("--nickname", action="store", type="string",
                                   help="Nickname")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()

    if not opt.rss_config:
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
