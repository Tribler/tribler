import time
from pathlib import Path

DATA_NONE = "None"


class TriblerStatistics:

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
        db_size = Path(str(self.session.mds.db_filename)).stat().st_size if self.session.mds else 0
        stats_dict = {"db_size": db_size,
                      "num_channels": self.session.mds.get_num_channels(),
                      "num_torrents": self.session.mds.get_num_torrents()}

        return stats_dict

    def get_ipv8_statistics(self):
        """
        Return generic IPv8 statistics.
        """

        if not self.session.ipv8:
            return {}

        return {
            "total_up": self.session.ipv8.endpoint.bytes_up,
            "total_down": self.session.ipv8.endpoint.bytes_down,
            "session_uptime": time.time() - self.session.ipv8_start_time
        }
