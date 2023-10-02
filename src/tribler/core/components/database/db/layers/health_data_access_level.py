import datetime
import logging

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
        self.HealthInfo = self.define_binding(self.instance)

    @staticmethod
    def define_binding(db):
        class HealthInfo(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            torrent = orm.Required(lambda: db.Resource, index=True)

            seeders = orm.Required(int, default=0)
            leechers = orm.Required(int, default=0)
            source = orm.Required(int, default=0)  # Source enum
            last_check = orm.Required(datetime.datetime, default=datetime.datetime.utcnow)

        return HealthInfo

    def add_torrent_health(self, torrent_health: HealthInfo):
        torrent = get_or_create(
            self.Resource,
            name=torrent_health.infohash_hex,
            type=ResourceType.TORRENT
        )

        health_info_entity = get_or_create(
            self.HealthInfo,
            torrent=torrent
        )

        health_info_entity.seeders = torrent_health.seeders
        health_info_entity.leechers = torrent_health.leechers
        health_info_entity.source = torrent_health.source
        health_info_entity.last_check = datetime.datetime.utcfromtimestamp(torrent_health.last_check)

    def get_torrent_health(self, infohash: str):
        if torrent := self.Resource.get(name=infohash, type=ResourceType.TORRENT):
            return self.HealthInfo.get(torrent=torrent)
        return None
