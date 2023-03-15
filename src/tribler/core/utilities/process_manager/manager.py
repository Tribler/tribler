from __future__ import annotations

import logging
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import ContextManager, List, Optional

from tribler.core.utilities.process_manager import sql_scripts
from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess
from tribler.core.utilities.process_manager.utils import with_retry

logger = logging.getLogger(__name__)

DB_FILENAME = 'processes.sqlite'

global_process_manager: Optional[ProcessManager] = None

_lock = Lock()


def set_global_process_manager(process_manager: Optional[ProcessManager]):
    global global_process_manager  # pylint: disable=global-statement
    with _lock:
        global_process_manager = process_manager


def get_global_process_manager() -> Optional[ProcessManager]:
    with _lock:
        return global_process_manager


class ProcessManager:
    def __init__(self, root_dir: Path, current_process: TriblerProcess, db_filename: str = DB_FILENAME):
        self.logger = logger  # Used by the `with_retry` decorator
        self.root_dir = root_dir
        self.db_filepath = root_dir / db_filename
        self.connection: Optional[sqlite3.Connection] = None
        self.current_process = current_process
        current_process.manager = self

    @contextmanager
    def connect(self) -> ContextManager[sqlite3.Connection]:
        """
        A context manager opens a connection to the database and handles the transaction.

        The opened connection is stored inside the ProcessManager instance. It allows to recursively
        the context manager, the inner invocation re-uses the connection opened in the outer context manager.

        In the case of a sqlite3.DatabaseError exception, the database is deleted to handle possible database
        corruption. The database content is not critical for Tribler's functioning, so its loss is tolerable.
        """

        if self.connection is not None:
            yield self.connection
            return

        connection = None
        try:
            self.connection = connection = sqlite3.connect(str(self.db_filepath))
            try:
                connection.execute('BEGIN EXCLUSIVE TRANSACTION')
                connection.execute(sql_scripts.CREATE_TABLES)
                connection.execute(sql_scripts.DELETE_OLD_RECORDS)
                yield connection
            finally:
                self.connection = None
            connection.execute('COMMIT')
            connection.close()

        except Exception as e:
            logger.exception(f'{e.__class__.__name__}: {e}')
            if connection:
                connection.close()
            if isinstance(e, sqlite3.DatabaseError):
                self.db_filepath.unlink(missing_ok=True)
            raise

    def primary_process_rowid(self, kind: ProcessKind) -> Optional[int]:
        """
        A helper method to load the current primary process of the specified kind from the database.

        Returns rowid of the existing process or None.
        """
        with self.connect() as connection:
            cursor = connection.execute(f"""
                SELECT {sql_scripts.SELECT_COLUMNS}
                FROM processes WHERE kind = ? and "primary" = 1 ORDER BY rowid DESC LIMIT 1
            """, [kind.value])
            row = cursor.fetchone()
            if row is not None:
                process = TriblerProcess.from_row(self, row)
                if process.is_running():
                    return process.rowid

                # Process is not running anymore; mark it as not primary
                process.primary = False
                process.save()
            return None

    def sys_exit(self, exit_code: Optional[int] = None, error: Optional[str | Exception] = None, replace: bool = False):
        """
        Calls sys.exit(exit_code) and stores exit code & error information (if provided) to the processes' database.

        Developers should use this method instead of a direct calling of sys.exit().
        """
        process = self.current_process
        if error is not None:
            process.set_error(error, replace)
        process.finish(exit_code)
        exit_code = process.exit_code
        sys.exit(exit_code)

    @with_retry
    def get_last_processes(self, limit=6) -> List[TriblerProcess]:
        """
        Returns last `limit` processes from the database. They are used during the formatting of the error report.
        """
        with self.connect() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            cursor = connection.execute(f"""
                SELECT {sql_scripts.SELECT_COLUMNS}
                FROM processes ORDER BY rowid DESC LIMIT ?
            """, [limit])
            result = [TriblerProcess.from_row(self, row) for row in cursor]
        result.reverse()
        return result
