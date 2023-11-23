from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from sqlite3 import DataError, DatabaseError, Error, IntegrityError, InterfaceError, InternalError, NotSupportedError, \
    OperationalError, ProgrammingError, Warning, sqlite_version_info  # pylint: disable=unused-import, redefined-builtin

from tribler.core.utilities.db_corruption_handling.base import handling_malformed_db_error


# This module serves as a replacement to the sqlite3 module and handles the case when the database is corrupted.
# It provides the `connect` function that should be used instead of `sqlite3.connect` and the `Cursor` and `Connection`
# classes that replaces `sqlite3.Cursor` and `sqlite3.Connection` classes respectively. If the `connect` function or
# any Connectoin or Cursor method is called and the database is corrupted, the database is marked as corrupted and
# the DatabaseIsCorrupted exception is raised. It should be handled by terminating the Tribler Core with the exit code
# EXITCODE_DATABASE_IS_CORRUPTED (99). After the Core restarts, the `handle_db_if_corrupted` function checks the
# presense of the database corruption marker and handles it by removing the database file and the corruption marker.
# After that, the database is recreated upon the next attempt to connect to it.


def connect(db_filename: str, **kwargs) -> sqlite3.Connection:
    # Replaces the sqlite3.connect function
    kwargs['factory'] = Connection
    with handling_malformed_db_error(Path(db_filename)):
        return sqlite3.connect(db_filename, **kwargs)


def _add_method_wrapper_that_handles_malformed_db_exception(cls, method_name: str):
    # Creates a wrapper for the given method that handles the case when the database is corrupted

    def wrapper(self, *args, **kwargs):
        with handling_malformed_db_error(self._db_filepath):  # pylint: disable=protected-access
            return getattr(super(cls, self), method_name)(*args, **kwargs)

    wrapper.__name__ = method_name
    wrapper.is_wrapped = True  # for testing purposes
    setattr(cls, method_name, wrapper)


class Cursor(sqlite3.Cursor):
    # Handles the case when the database is corrupted in all relevant methods.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_filepath = self.connection._db_filepath


for method_name_ in ['execute', 'executemany', 'executescript', 'fetchall', 'fetchmany', 'fetchone', '__next__']:
    _add_method_wrapper_that_handles_malformed_db_exception(Cursor, method_name_)



class ConnectionBase(sqlite3.Connection):
    # This class simplifies testing of the Connection class by allowing mocking of base class methods.
    # Direct mocking of sqlite3.Connection methods is not possible because they are C functions.

    if sys.version_info < (3, 11):
        def blobopen(self, *args, **kwargs) -> Blob:
            raise NotImplementedError


class Connection(ConnectionBase):
    # Handles the case when the database is corrupted in all relevant methods.
    def __init__(self, db_filepath: str, *args, **kwargs):
        super().__init__(db_filepath, *args, **kwargs)
        self._db_filepath = Path(db_filepath)

    def cursor(self, factory=None) -> Cursor:
        return super().cursor(factory or Cursor)

    def iterdump(self):
        # Not implemented because it is not used in Tribler.
        # Can be added later with an iterator class that handles the malformed db error during the iteration
        raise NotImplementedError

    def blobopen(self, *args, **kwargs) -> Blob:  # Works for Python >= 3.11
        with handling_malformed_db_error(self._db_filepath):
            blob = super().blobopen(*args, **kwargs)
        return Blob(blob, self._db_filepath)


for method_name_ in ['commit', 'execute', 'executemany', 'executescript', 'backup', '__enter__', '__exit__',
                    'serialize', 'deserialize']:
    _add_method_wrapper_that_handles_malformed_db_exception(Connection, method_name_)


class Blob:  # For Python >= 3.11. Added now, so we do not forgot to add it later when upgrading to 3.11.
    def __init__(self, blob, db_filepath: Path):
        self._blob = blob
        self._db_filepath = db_filepath


for method_name_ in ['close', 'read', 'write', 'seek', '__len__', '__enter__', '__exit__', '__getitem__',
                     '__setitem__']:
    _add_method_wrapper_that_handles_malformed_db_exception(Blob, method_name_)
