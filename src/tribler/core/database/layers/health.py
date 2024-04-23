from __future__ import annotations

import logging
from binascii import hexlify
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

from pony import orm

from tribler.core.database.layers.layer import EntityImpl, Layer

if TYPE_CHECKING:
    import dataclasses

    from pony.orm import Database

    from tribler.core.database.layers.knowledge import KnowledgeDataAccessLayer, Resource
    from tribler.core.torrent_checker.dataclasses import HealthInfo

    @dataclasses.dataclass
    class TorrentHealth(EntityImpl):
        """
        Database type for torrent health information.
        """

        id: int
        torrent: Resource
        seeders: int
        leechers: int
        source: int
        tracker: Tracker | None
        last_check: datetime

        def __init__(self, torrent: Resource) -> None: ...  # noqa: D107

        @staticmethod
        def get(torrent: Resource) -> TorrentHealth | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(torrent: Resource) -> TorrentHealth | None: ...  # noqa: D102

    @dataclasses.dataclass
    class Tracker(EntityImpl):
        """
        Database type for tracker definitions.
        """

        id: int
        url: str
        last_check: datetime | None
        alive: bool
        failures: int
        torrents = set[Resource]
        torrent_health_set = set[TorrentHealth]

        def __init__(self, url: str) -> None: ...  # noqa: D107

        @staticmethod
        def get(url: str) -> Tracker | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(url: str) -> Tracker | None: ...  # noqa: D102


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
    """
    A layer that stores health information.
    """

    def __init__(self, knowledge_layer: KnowledgeDataAccessLayer) -> None:
        """
        Create a new health layer and initialize its bindings.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.instance = knowledge_layer.instance
        self.Resource = knowledge_layer.Resource
        self.TorrentHealth, self.Tracker = self.define_binding(self.instance)

    def get_torrent_health(self, infohash: str) -> TorrentHealth | None:
        """
        Get the health belonging to the given infohash.
        """
        if torrent := self.Resource.get(name=infohash, type=ResourceType.TORRENT):
            return self.TorrentHealth.get(torrent=torrent)
        return None

    @staticmethod
    def define_binding(db: Database) -> tuple[type[TorrentHealth], type[Tracker]]:
        """
        Create the bindings for this layer.
        """
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

        return TorrentHealth, Tracker

    def add_torrent_health(self, health_info: HealthInfo) -> None:
        """
        Store the given health info in the database.
        """
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
        torrent_health.last_check = datetime.utcfromtimestamp(health_info.last_check)  # noqa: DTZ004
