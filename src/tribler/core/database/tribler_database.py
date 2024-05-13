from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pony import orm
from pony.orm import Database, db_session

from tribler.core.database.layers.health import HealthDataAccessLayer
from tribler.core.database.layers.knowledge import KnowledgeDataAccessLayer
from tribler.core.database.layers.user_activity import UserActivityLayer

if TYPE_CHECKING:
    import dataclasses


    @dataclasses.dataclass
    class Misc:
        """
        A miscellaneous key value mapping in the database.
        """

        name: str
        value: str | None

        def __init__(self, name: str) -> None: ...  # noqa: D107

        @staticmethod
        def get(name: str) -> Misc | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(name: str) -> Misc | None: ...  # noqa: D102

MEMORY = ":memory:"


class TriblerDatabase:
    """
    A wrapper for the Tribler database.
    """

    CURRENT_VERSION = 1
    _SCHEME_VERSION_KEY = "scheme_version"

    def __init__(self, filename: str | None = None, *, create_tables: bool = True, **generate_mapping_kwargs) -> None:
        """
        Create a new tribler database.
        """
        self.instance = Database()

        self.knowledge = KnowledgeDataAccessLayer(self.instance)
        self.health = HealthDataAccessLayer(self.knowledge)
        self.user_activity = UserActivityLayer(self.instance)

        self.Misc = self.define_binding(self.instance)

        self.Peer = self.knowledge.Peer
        self.Statement = self.knowledge.Statement
        self.Resource = self.knowledge.Resource
        self.StatementOp = self.knowledge.StatementOp

        self.TorrentHealth = self.health.TorrentHealth
        self.Tracker = self.health.Tracker

        filename = filename or MEMORY
        db_does_not_exist = filename == MEMORY or not os.path.isfile(filename)

        if filename != MEMORY:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)

        self.instance.bind(provider='sqlite', filename=filename, create_db=db_does_not_exist)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        if db_does_not_exist:
            self.fill_default_data()

    @staticmethod
    def define_binding(db: Database) -> type[Misc]:
        """
        Define common bindings.
        """

        class Misc(db.Entity):
            name = orm.PrimaryKey(str)
            value = orm.Optional(str)

        return Misc

    @db_session
    def fill_default_data(self) -> None:
        """
        Add a misc entry for the database version.
        """
        self.logger.info("Filling the DB with the default data")
        self.set_misc(self._SCHEME_VERSION_KEY, str(self.CURRENT_VERSION))

    def get_misc(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieve a value from the database or return the default value if it is not found.
        """
        data = self.Misc.get(name=key)
        return data.value if data else default

    def set_misc(self, key: str, value: str) -> None:
        """
        Set or add the value of a given key.
        """
        obj = self.Misc.get_for_update(name=key) or self.Misc(name=key)
        obj.value = value

    @property
    def version(self) -> int:
        """
        Get the database version.
        """
        return int(cast(str, self.get_misc(key=self._SCHEME_VERSION_KEY, default="0")))

    @version.setter
    def version(self, value: int) -> None:
        """
        Set the database version.
        """
        if not isinstance(value, int):
            msg = "DB version should be integer"
            raise TypeError(msg)

        self.set_misc(key=self._SCHEME_VERSION_KEY, value=str(value))

    def shutdown(self) -> None:
        """
        Disconnect from the database.
        """
        self.instance.disconnect()
