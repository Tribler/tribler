from __future__ import absolute_import

import os
import time

from six import text_type

from Tribler.Core.CacheDB.sqlitecachedb import DB_FILE_RELATIVE_PATH
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_TORRENTS

DATA_NONE = u"None"


class TriblerStatistics(object):

    def __init__(self, session):
        """
        Constructor.
        :param session: The Tribler session.
        """
        self.session = session

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
                          os.path.join(self.session.config.get_state_dir(), DB_FILE_RELATIVE_PATH))}

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
            "connection": text_type(stats.connection_type),
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

    def get_ipv8_statistics(self):
        """
        Return generic IPv8 statistics.
        """
        try:
            ipv8 = self.session.get_ipv8_instance()
        except OperationNotEnabledByConfigurationException:
            return {}

        return {
            "total_up": ipv8.endpoint.bytes_up,
            "total_down": ipv8.endpoint.bytes_down,
            "session_uptime": time.time() - self.session.lm.ipv8_start_time
        }
