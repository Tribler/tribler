from __future__ import absolute_import

import os
import time

from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException

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
        db_size = os.path.getsize(self.session.lm.mds.db_filename) if self.session.lm.mds else 0
        stats_dict = {"db_size": db_size,
                      "num_channels": self.session.lm.mds.get_num_channels(),
                      "num_torrents": self.session.lm.mds.get_num_torrents()}

        return stats_dict

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
