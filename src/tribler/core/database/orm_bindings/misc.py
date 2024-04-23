from __future__ import annotations

from typing import TYPE_CHECKING

from pony import orm

if TYPE_CHECKING:
    import dataclasses

    from pony.orm import Database


    @dataclasses.dataclass
    class MiscData:
        """
        A miscellaneous key value mapping in the database.
        """

        name: str
        value: str | None

        def __init__(self, name: str) -> None: ...  # noqa: D107

        @staticmethod
        def get(name: str) -> MiscData | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(name: str) -> MiscData | None: ...  # noqa: D102


def define_binding(db: Database) -> type[MiscData]:
    """
    Define the misc data binding.
    """

    class MiscData(db.Entity):
        """
        This binding is used to store all kinds of values, like DB version, counters, etc.
        """

        name = orm.PrimaryKey(str)
        value = orm.Optional(str)

    return MiscData
