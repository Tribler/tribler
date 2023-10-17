import logging
import os
from typing import Any, Optional

from pony import orm

from tribler.core.components.database.db.layers.health_data_access_layer import HealthDataAccessLayer
from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer
from tribler.core.utilities.pony_utils import TrackedDatabase, db_session, get_or_create

MEMORY = ':memory:'


class TriblerDatabase:
    CURRENT_VERSION = 1
    _SCHEME_VERSION_KEY = 'scheme_version'

    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = TrackedDatabase()

        self.knowledge = KnowledgeDataAccessLayer(self.instance)
        self.health = HealthDataAccessLayer(self.knowledge)

        self.Misc = self.define_binding(self.instance)

        self.Peer = self.knowledge.Peer
        self.Statement = self.knowledge.Statement
        self.Resource = self.knowledge.Resource
        self.StatementOp = self.knowledge.StatementOp

        self.TorrentHealth = self.health.TorrentHealth
        self.Tracker = self.health.Tracker

        filename = filename or MEMORY
        db_does_not_exist = filename == MEMORY or not os.path.isfile(filename)

        self.instance.bind('sqlite', filename, create_db=db_does_not_exist)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        if db_does_not_exist:
            self.fill_default_data()

    @staticmethod
    def define_binding(db):
        """ Define common bindings"""
        class Misc(db.Entity):
            name = orm.PrimaryKey(str)
            value = orm.Optional(str)

        return Misc

    @db_session
    def fill_default_data(self):
        self.logger.info('Filling the DB with the default data')
        self.set_misc(self._SCHEME_VERSION_KEY, self.CURRENT_VERSION)

    def get_misc(self, key: str, default: Optional[str] = None) -> Optional[str]:
        data = self.Misc.get(name=key)
        return data.value if data else default

    def set_misc(self, key: str, value: Any):
        key_value = get_or_create(self.Misc, name=key)
        key_value.value = str(value)

    @property
    def version(self) -> int:
        """ Get the database version"""
        return int(self.get_misc(key=self._SCHEME_VERSION_KEY, default=0))

    @version.setter
    def version(self, value: int):
        """ Set the database version"""
        if not isinstance(value, int):
            raise TypeError('DB version should be integer')

        self.set_misc(key=self._SCHEME_VERSION_KEY, value=value)

    def shutdown(self) -> None:
        self.instance.disconnect()
