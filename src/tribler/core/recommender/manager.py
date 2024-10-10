from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pony.orm import Database, db_session
from pony.orm import max as pony_max

from tribler.core.recommender.orm_query import define_binding

if TYPE_CHECKING:
    from tribler.core.recommender.orm_query import Query


class Manager:
    """
    Database manager for Query objects.
    """

    def __init__(self, db_filename: str) -> None:
        """
        Create a new database connection to retrieve and store Query objects.
        """
        self.db = Database()

        if db_filename == ":memory:":
            create_db = True
            db_path_string = ":memory:"
        else:
            create_db = not Path(db_filename).exists()
            db_path_string = str(db_filename)

        self.Query = define_binding(self.db)

        self.db.bind(provider="sqlite", filename=db_path_string, create_db=create_db, timeout=120.0)
        self.db.generate_mapping(create_tables=create_db, check_tables=True)

    def get_total_queries(self) -> int:
        """
        Get the total number of queries that we know of.
        """
        with db_session:
            return pony_max(q.rowid for q in self.Query) or 0

    def get_query(self, query_id: int) -> Query:
        """
        Get the Query with a given id.
        """
        with db_session:
            return self.Query.get(rowid=query_id)

    def add_query(self, json_data: str) -> None:
        """
        Inject data into our database.
        """
        with db_session:
            self.Query(version=1, json=json_data)
