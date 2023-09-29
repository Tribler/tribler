import time

from tribler.core.components.database.db.tests.test_tribler_database import TestTriblerDatabase
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo, Source
from tribler.core.utilities.pony_utils import db_session


# pylint: disable=protected-access
class TestHealthAccessLayer(TestTriblerDatabase):

    @db_session
    def test_add_torrent_health(self):
        """ Test that add_torrent_health works as expected"""
        health_info = HealthInfo(
            infohash=b'0' * 20,
            seeders=10,
            leechers=20,
            last_check=int(time.time()),
            self_checked=True,
            source=Source.POPULARITY_COMMUNITY
        )

        self.db.health.add_torrent_health(health_info)

        assert self.db.health.get_torrent_health(health_info.infohash_hex)  # add fields validation
        assert not self.db.health.get_torrent_health('missed hash')
