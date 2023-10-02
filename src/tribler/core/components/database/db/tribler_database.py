import logging
from typing import Any, Optional

from pony import orm

from tribler.core.components.database.db.layers.health_data_access_level import HealthDataAccessLayer
from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer
from tribler.core.utilities.pony_utils import TrackedDatabase, get_or_create


class TriblerDatabase:
    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = TrackedDatabase()

        self.knowledge = KnowledgeDataAccessLayer(self.instance)
        self.health = HealthDataAccessLayer(self.knowledge)

        self.Misc = self.define_binding(self.instance)

        self.Peer = self.knowledge.Peer
        self.Statement = self.knowledge.Statement
        self.Resource = self.knowledge.Resource
        self.StatementOp = self.knowledge.StatementOp

        self.HealthInfo = self.health.HealthInfo

        self.instance.bind('sqlite', filename or ':memory:', create_db=True)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def define_binding(db):
        """ Define common bindings"""

        class Misc(db.Entity):  # pylint: disable=unused-variable
            name = orm.PrimaryKey(str)
            value = orm.Optional(str)

        return Misc

    def get_misc(self, key: str, default: Optional[str] = None) -> Optional[str]:
        data = self.Misc.get(name=key)
        return data.value if data else default

    def set_misc(self, key: str, value: Any):
        key_value = get_or_create(self.Misc, name=key)
        key_value.value = str(value)

    def shutdown(self) -> None:
        self.instance.disconnect()
