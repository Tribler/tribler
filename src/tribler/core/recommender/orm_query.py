from __future__ import annotations

from typing import TYPE_CHECKING

from pony import orm

if TYPE_CHECKING:
    from dataclasses import dataclass
    from typing import Iterator

    from pony.orm import Database
    from pony.orm.core import Entity


    class IterQuery(type):  # noqa: D101

        def __iter__(cls) -> Iterator[Query]: ...  # noqa: D105


    @dataclass
    class Query(Entity, metaclass=IterQuery):
        """
        A generic query data object.
        """

        rowid: int
        version: int
        json: str
        """
        {
            chosen_index: int,
            timestamp: int,
            query: str,
            results: [{infohash: str, seeders: int, leechers: int}]
        }
        """


def define_binding(db: Database) -> type[Query]:
    """
    Create the Query binding.
    """

    class Query(db.Entity):
        """
        This ORM binding class is intended to store generic Query objects.
        """

        rowid = orm.PrimaryKey(int, size=64, auto=True)
        version = orm.Required(int, size=16)
        json = orm.Required(str)

    return Query
