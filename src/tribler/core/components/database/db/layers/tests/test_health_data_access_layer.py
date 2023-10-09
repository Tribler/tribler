import os
import time
from datetime import datetime

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.database.db.tests.test_tribler_database import TestTriblerDatabase
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo, Source
from tribler.core.utilities.pony_utils import db_session


# pylint: disable=protected-access
class TestHealthAccessLayer(TestTriblerDatabase):

    @staticmethod
    def create_health_info(tracker=''):
        return HealthInfo(
            infohash=os.urandom(40),
            seeders=10,
            leechers=20,
            last_check=int(time.time()),
            self_checked=True,
            source=Source.TRACKER,
            tracker=tracker
        )

    @db_session
    def test_add_torrent_health_no_tracker(self):
        """ Test that add_torrent_health works as expected"""
        info = self.create_health_info()
        self.db.health.add_torrent_health(info)

        health = self.db.health.get_torrent_health(info.infohash_hex)

        assert health.torrent.name == info.infohash_hex
        assert health.torrent.type == ResourceType.TORRENT
        assert health.seeders == info.seeders
        assert health.leechers == info.leechers
        assert health.last_check == datetime.utcfromtimestamp(info.last_check)
        assert health.source == info.source

        assert not health.tracker

        assert not self.db.health.get_torrent_health('missed hash')

    @db_session
    def test_add_torrent_health_with_trackers(self):
        """ Test that add_torrent_health considers trackers"""

        # first add single HealthInfo with tracker
        info = self.create_health_info(tracker='tracker1')
        self.db.health.add_torrent_health(info)
        health = self.db.health.get_torrent_health(info.infohash_hex)

        assert health.tracker.url == info.tracker

        # then add another HealthInfo with the same tracker
        self.db.health.add_torrent_health(
            self.create_health_info(tracker='tracker1')
        )

        assert len(self.db.Tracker.select()) == 1
        assert len(self.db.TorrentHealth.select()) == 2

        # then add another HealthInfo with the different tracker
        self.db.health.add_torrent_health(
            self.create_health_info(tracker='tracker2')
        )

        assert len(self.db.Tracker.select()) == 2
        assert len(self.db.TorrentHealth.select()) == 3
