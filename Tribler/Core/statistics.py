import logging
import binascii
import os

from Tribler.Core.CacheDB.sqlitecachedb import DB_FILE_RELATIVE_PATH
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_CHANNELCAST
from Tribler.dispersy.util import blocking_call_on_reactor_thread

from Tribler.Core.Utilities.misc_utils import compute_ratio


DATA_NONE = u"None"


class TriblerStatistics(object):

    def __init__(self, session):
        """
        Constructor.
        :param session: The Tribler session.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    @blocking_call_on_reactor_thread
    def dump_statistics(self):
        """
        Dumps all statistics.
        :return: A dictionary of data.
        """
        dispersy = self.session.get_dispersy_instance()
        if dispersy is None:
            # we use critical here because whoever calls this function wants to get statistics, so it
            # should be at least an error if we can't get dispersy.
            self._logger.critical(u"dispersy instance not found.")

        dispersy.statistics.update()

        data_dict = {u'communities': self._create_community_data(dispersy)}
        return data_dict

    def get_tribler_statistics(self):
        """
        Return a dictionary with some general Tribler statistics.
        """
        torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)
        channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

        torrent_stats = torrent_db_handler.getTorrentsStats()
        torrent_total_size = 0 if torrent_stats[1] is None else torrent_stats[1]

        stats_dict = {"torrents": {"num_collected": torrent_stats[0], "total_size": torrent_total_size,
                                   "num_files": torrent_stats[2]},

                      "num_channels": channel_db_handler.getNrChannels(),
                      "database_size": os.path.getsize(
                          os.path.join(self.session.get_state_dir(), DB_FILE_RELATIVE_PATH))}

        if self.session.lm.rtorrent_handler:
            torrent_queue_stats = self.session.lm.rtorrent_handler.get_queue_stats()
            torrent_queue_size_stats = self.session.lm.rtorrent_handler.get_queue_size_stats()
            torrent_queue_bandwidth_stats = self.session.lm.rtorrent_handler.get_bandwidth_stats()

            stats_dict["torrent_queue_stats"] = torrent_queue_stats
            stats_dict["torrent_queue_size_stats"] = torrent_queue_size_stats
            stats_dict["torrent_queue_bandwidth_stats"] = torrent_queue_bandwidth_stats

        return stats_dict

    def get_dispersy_statistics(self):
        """
        Return a dictionary with some general Dispersy statistics.
        """
        dispersy = self.session.get_dispersy_instance()
        dispersy.statistics.update()
        stats = dispersy.statistics
        return {
            "wan_address": "%s:%d" % stats.wan_address,
            "lan_address": "%s:%d" % stats.lan_address,
            "connection": unicode(stats.connection_type),
            "runtime": stats.timestamp - stats.start,
            "total_downloaded": stats.total_down,
            "total_uploaded": stats.total_up,
            "packets_sent": stats.total_send,
            "packets_received": stats.total_received,
            "packets_success": stats.msg_statistics.success_count,
            "packets_dropped": stats.msg_statistics.drop_count,
            "packets_delayed_sent": stats.msg_statistics.delay_send_count,
            "packets_delayed_received": stats.msg_statistics.delay_received_count,
            "packets_delayed_success": stats.msg_statistics.delay_success_count,
            "packets_delayed_timeout": stats.msg_statistics.delay_timeout_count,
            "total_walk_attempts": stats.walk_attempt_count,
            "total_walk_success": stats.walk_success_count,
            "sync_messages_created": stats.msg_statistics.created_count,
            "bloom_new": sum(c.sync_bloom_new for c in stats.communities),
            "bloom_reused": sum(c.sync_bloom_reuse for c in stats.communities),
            "bloom_skipped": sum(c.sync_bloom_skip for c in stats.communities),
        }

    def get_community_statistics(self):
        """
        Return a dictionary with general statistics of the active Dispersy communities.
        """
        communities_stats = []
        dispersy = self.session.get_dispersy_instance()
        dispersy.statistics.update()

        for community in dispersy.statistics.communities:
            if community.dispersy_enable_candidate_walker or community.dispersy_enable_candidate_walker_responses or \
                    community.candidates:
                candidate_count = "%s" % len(community.candidates)
            else:
                candidate_count = "-"

            communities_stats.append({
                "identifier": community.hex_cid,
                "member": community.hex_mid,
                "classification": community.classification,
                "global_time": community.global_time,
                "median_global_time": community.acceptable_global_time -
                                      community.dispersy_acceptable_global_time_range,
                "acceptable_global_time_range": community.dispersy_acceptable_global_time_range,
                "walk_attempts": community.msg_statistics.walk_attempt_count,
                "walk_success": community.msg_statistics.walk_success_count,
                "sync_bloom_created": community.sync_bloom_new,
                "sync_bloom_reused": community.sync_bloom_reuse,
                "sync_bloom_skipped": community.sync_bloom_skip,
                "sync_messages_created": community.msg_statistics.created_count,
                "packets_sent": community.msg_statistics.outgoing_count,
                "packets_received": community.msg_statistics.total_received_count,
                "packets_success": community.msg_statistics.success_count,
                "packets_dropped": community.msg_statistics.drop_count,
                "packets_delayed_sent": community.msg_statistics.delay_send_count,
                "packets_delayed_received": community.msg_statistics.delay_received_count,
                "packets_delayed_success": community.msg_statistics.delay_success_count,
                "packets_delayed_timeout": community.msg_statistics.delay_timeout_count,
                "candidates": candidate_count
            })

        return communities_stats

    def _create_community_data(self, dispersy):
        """
        Creates a dictionary of community statistics data.
        :param dispersy: The dispersy instance.
        :return: A dictionary of community statistics data.
        """
        community_data_dict = {}

        for community in dispersy.statistics.communities:
            median_global_time = u"%d (%d difference)" % \
                (community.acceptable_global_time - community.dispersy_acceptable_global_time_range,
                 community.acceptable_global_time - community.global_time -
                    community.dispersy_acceptable_global_time_range)

            candidate_list = None
            if community.dispersy_enable_candidate_walker or \
                    community.dispersy_enable_candidate_walker_responses:
                candidate_count = u"%d " % len(community.candidates)
                candidate_list = [(u"%s" % global_time, u"%s:%s" % lan, u"%s:%s" % wan,
                                   u"%s" % binascii.hexlify(mid) if mid else DATA_NONE)
                                  for lan, wan, global_time, mid in community.candidates]
                candidate_list.sort()
            elif community.candidates:
                candidate_count = u"%d*" % len(community.candidates)
            else:
                candidate_count = u"-"

            database_list = []
            if community.database:
                database_str = u"%d packets" % \
                    sum(count for count in community.database.itervalues())
                for name, count in sorted(community.database.iteritems(), key=lambda tup: tup[1]):
                    database_list.append((u"%s" % count, u"%s" % name))
            else:
                database_str = u"? packets"

            community_data = {
                u"Identifier": u"%s" % community.hex_cid,
                u"Member": u"%s" % community.hex_mid,
                u"Classification": u"%s" % community.classification,
                u"Database id": u"%s" % community.database_id,
                u"Global time": u"%s" % community.global_time,
                u"Median global time": u"%s" % median_global_time,
                u"Acceptable range": u"%s" % community.dispersy_acceptable_global_time_range,
                u"Sync bloom created": u"%s" % community.sync_bloom_new,
                u"Sync bloom reused": u"%s" % community.sync_bloom_reuse,
                u"Sync bloom skipped": u"%s" % community.sync_bloom_skip,
                u"Candidates": u"%s" % candidate_count,
                u"Candidate_list": candidate_list,
                u"Database": database_str,
                u"Database_list": database_list,
                u"Packets Created": u"%s" % community.msg_statistics.created_count,
                u"Packets Sent": u"%s" % compute_ratio(community.msg_statistics.outgoing_count,
                                                       community.msg_statistics.outgoing_count
                                                       + community.msg_statistics.total_received_count),
                u"Packets Received": u"%s" % compute_ratio(community.msg_statistics.total_received_count,
                                                           community.msg_statistics.outgoing_count
                                                           + community.msg_statistics.total_received_count),
                u"Packets Success": compute_ratio(community.msg_statistics.success_count,
                                                  community.msg_statistics.total_received_count),
                u"Packets Dropped": compute_ratio(community.msg_statistics.drop_count,
                                                  community.msg_statistics.total_received_count),
                u"Packets Delayed Sent": compute_ratio(community.msg_statistics.delay_send_count,
                                                       community.msg_statistics.total_received_count),
                u"Packets Delayed Received": compute_ratio(community.msg_statistics.delay_received_count,
                                                           community.msg_statistics.total_received_count),
                u"Packets Delayed Success": compute_ratio(community.msg_statistics.delay_success_count,
                                                          community.msg_statistics.delay_received_count),
                u"Packets Delayed Timeout": compute_ratio(community.msg_statistics.delay_timeout_count,
                                                          community.msg_statistics.delay_received_count),
                u"Statistics": self._get_community_rawinfo(community),
            }

            key = u"<%s>: %s" % (community.classification, community.hex_cid)
            community_data_dict[key] = community_data

        return community_data_dict

    def _get_community_rawinfo(self, community):
        categories = (u"attachment", u"endpoint_recv", u"endpoint_send",
                      u"walk_failure_dict", u"incoming_intro_dict", u"outgoing_intro_dict")
        msg_categories = (u"success", u"drop", u"created", u"delay", u"outgoing")
        ip_categories = (u"walk_failure_dict", u"incoming_intro_dict", u"outgoing_intro_dict")

        raw_info = {}
        for category in categories:
            if getattr(community, category, None):
                raw_info[category] = {}
                for key, val in getattr(community, category).items():
                    raw_info[category][key] = unicode(val)

        for category in msg_categories:
            dict_name = u"%s_dict" % category
            if getattr(community.msg_statistics, dict_name, None):
                raw_info[category] = {}
                for key, val in getattr(community.msg_statistics, dict_name).items():
                    raw_info[category][key] = unicode(val)

        return raw_info
