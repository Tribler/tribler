import logging
from datetime import datetime
from typing import Optional

from pony import orm

from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.knowledge_db import ResourceType
from tribler.core.utilities.pony_utils import get_or_create


# pylint: disable=redefined-outer-name


class HealthDataAccessLayer:
    def __init__(self, knowledge_layer: KnowledgeDataAccessLayer):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.instance = knowledge_layer.instance
        self.Resource = knowledge_layer.Resource
        self.TorrentHealth, self.Tracker, self.get_torrent_health = self.define_binding(self.instance)

    @staticmethod
    def define_binding(db):
        class TorrentHealth(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            torrent = orm.Required(lambda: db.Resource, index=True)

            seeders = orm.Required(int, default=0)
            leechers = orm.Required(int, default=0)
            source = orm.Required(int, default=0)  # Source enum
            tracker = orm.Optional(lambda: Tracker)
            last_check = orm.Required(datetime, default=datetime.utcnow)

        class Tracker(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            url = orm.Required(str, unique=True)
            last_check = orm.Optional(datetime)
            alive = orm.Required(bool, default=True)
            failures = orm.Required(int, default=0)

            torrents = orm.Set(lambda: db.Resource)
            torrent_health_set = orm.Set(lambda: TorrentHealth, reverse='tracker')

        def get_torrent_health(infohash: str) -> Optional[TorrentHealth]:
            if torrent := db.Resource.get(name=infohash, type=ResourceType.TORRENT):
                return TorrentHealth.get(torrent=torrent)
            return None

        return TorrentHealth, Tracker, get_torrent_health

    def add_torrent_health(self, health_info: HealthInfo):
        torrent = get_or_create(
            self.Resource,
            name=health_info.infohash_hex,
            type=ResourceType.TORRENT
        )

        torrent_health = get_or_create(
            self.TorrentHealth,
            torrent=torrent
        )

        torrent_health.seeders = health_info.seeders
        torrent_health.leechers = health_info.leechers
        if health_info.tracker:
            torrent_health.tracker = get_or_create(
                self.Tracker,
                url=health_info.tracker
            )

        torrent_health.source = health_info.source
        torrent_health.last_check = datetime.utcfromtimestamp(health_info.last_check)
