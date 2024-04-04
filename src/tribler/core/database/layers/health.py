import logging
from binascii import hexlify
from datetime import datetime
from enum import IntEnum
from typing import Optional

from pony import orm

from tribler.core.database.layers.knowledge import KnowledgeDataAccessLayer
from tribler.core.database.layers.layer import Layer
from tribler.core.torrent_checker.dataclasses import HealthInfo


class ResourceType(IntEnum):
    """
    Description of available resources within the Knowledge Graph.
    These types are also using as a predicate for the statements.

    Based on https://en.wikipedia.org/wiki/Dublin_Core
    """
    CONTRIBUTOR = 1
    COVERAGE = 2
    CREATOR = 3
    DATE = 4
    DESCRIPTION = 5
    FORMAT = 6
    IDENTIFIER = 7
    LANGUAGE = 8
    PUBLISHER = 9
    RELATION = 10
    RIGHTS = 11
    SOURCE = 12
    SUBJECT = 13
    TITLE = 14
    TYPE = 15

    # this is a section for extra types
    TAG = 101
    TORRENT = 102
    CONTENT_ITEM = 103


class HealthDataAccessLayer(Layer):
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
        torrent = self.get_or_create(
            self.Resource,
            name=hexlify(health_info.infohash),
            type=ResourceType.TORRENT
        )

        torrent_health = self.get_or_create(
            self.TorrentHealth,
            torrent=torrent
        )

        torrent_health.seeders = health_info.seeders
        torrent_health.leechers = health_info.leechers
        if health_info.tracker:
            torrent_health.tracker = self.get_or_create(
                self.Tracker,
                url=health_info.tracker
            )

        torrent_health.source = health_info.source
        torrent_health.last_check = datetime.utcfromtimestamp(health_info.last_check)
