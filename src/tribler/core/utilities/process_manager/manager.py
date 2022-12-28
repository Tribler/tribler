from __future__ import annotations

import logging
import sqlite3
import sys
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import ContextManager, List, Optional, Union

from contextlib import contextmanager

from tribler.core.utilities.process_manager import sql_scripts
from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess

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


def set_error(error: Union[str | Exception], replace: bool = False):
    process_manager = get_global_process_manager()
    if process_manager:
        process_manager.current_process.set_error(error, replace)
    else:
        logger.warning('Cannot set error for process locker: no process locker global instance is set')


def with_retry(func):
    """
    This decorator re-runs the wrapped function once in the case of sqlite3.Error` exception.

    This way, it becomes possible to handle exceptions like sqlite3.DatabaseError "database disk image is malformed".
    In case of an error, the first function invocation removes the corrupted database file, and the second invocation
    re-creates the database structure. The content of the database is not critical for Tribler's functioning,
    so it is OK for Tribler to re-create it in such cases.
    """
    @wraps(func)
    def new_func(self: ProcessManager, *args, **kwargs):
        if self.connection:
            # If we are already inside transaction just call the function without retrying
            return func(self, *args, **kwargs)

        try:
            return func(self, *args, **kwargs)
        except sqlite3.Error as e:
            logger.warning(f'Retrying after the error: {e.__class__.__name__}: {e}')
            return func(self, *args, **kwargs)
    new_func: func
    return new_func


class ProcessManager:
    def __init__(self, root_dir: Path, process_kind: ProcessKind, creator_pid: Optional[int] = None,
                 db_filename: str = DB_FILENAME):
        self.root_dir = root_dir
        self.db_filepath = root_dir / db_filename
        self.connection: Optional[sqlite3.Connection] = None
        self.current_process = TriblerProcess.current_process(self, process_kind, creator_pid)
        self.primary_process = self.atomic_get_primary_process(self.current_process)

    @contextmanager
    def connect(self) -> ContextManager[sqlite3.Connection]:
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

    def _load_primary_process(self, connection: sqlite3.Connection, kind: ProcessKind) -> Optional[TriblerProcess]:
        cursor = connection.execute("""
            SELECT * FROM processes WHERE kind = ? and "primary" = 1 ORDER BY rowid DESC LIMIT 1
        """, [kind.value])
        row = cursor.fetchone()
        if row is not None:
            process = TriblerProcess.from_row(self, row)
            if process.is_running():
                return process

            # Process is not running anymore; mark it as not primary
            process.primary = 0
            process._save(connection)  # pylint: disable=protected-access
        return None

    @with_retry
    def atomic_get_primary_process(self, current_process: TriblerProcess) -> TriblerProcess:
        with self.connect() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            primary_process = self._load_primary_process(connection, current_process.kind)
            if primary_process is None:
                current_process.primary = 1
                primary_process = current_process
            else:
                current_process.canceled = 1
            current_process._save(connection)  # pylint: disable=protected-access
            return primary_process

    @with_retry
    def save(self, process: TriblerProcess):
        with self.connect() as connection:
            process._save(connection)  # pylint: disable=protected-access

    def sys_exit(self, exit_code: Optional[int] = None, error: Optional[str | Exception] = None, replace: bool = False):
        p = self.current_process
        if error is not None:
            p.set_error(error, replace)
        p.mark_finished(exit_code)
        p.save()
        exit_code = p.exit_code
        sys.exit(exit_code)

    @with_retry
    def get_last_processes(self, limit=6) -> List[TriblerProcess]:
        with self.connect() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            cursor = connection.execute("""SELECT * FROM processes ORDER BY rowid DESC LIMIT ?""", [limit])
            result = [TriblerProcess.from_row(self, row) for row in cursor]
        result.reverse()
        return result
