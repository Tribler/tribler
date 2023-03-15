import sqlite3
from functools import wraps
from logging import Logger
from typing import Optional, Protocol


class ClassWithOptionalConnection(Protocol):
    connection: Optional[sqlite3.Connection]
    logger: Logger


def with_retry(method):
    """
    This decorator re-runs the wrapped ProcessManager method once in the case of sqlite3.Error` exception.

    This way, it becomes possible to handle exceptions like sqlite3.DatabaseError "database disk image is malformed".
    In case of an error, the first function invocation removes the corrupted database file, and the second invocation
    re-creates the database structure. The content of the database is not critical for Tribler's functioning,
    so it is OK for Tribler to re-create it in such cases.
    """

    @wraps(method)
    def new_method(self: ClassWithOptionalConnection, *args, **kwargs):
        if self.connection:
            # If we are already inside transaction just call the function without retrying
            return method(self, *args, **kwargs)

        try:
            return method(self, *args, **kwargs)
        except sqlite3.Error as e:
            self.logger.warning(f'Retrying after the error: {e.__class__.__name__}: {e}')
            return method(self, *args, **kwargs)

    new_method: method
    return new_method
