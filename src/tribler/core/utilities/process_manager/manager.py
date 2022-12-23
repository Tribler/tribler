from __future__ import annotations

import logging
import sqlite3
import sys
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import ContextManager, List, Optional

from decorator import contextmanager

from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess
from tribler.core.utilities.process_manager.sql_scripts import CREATE_TABLES

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


def set_error(error_msg: Optional[str] = None, error_info: Optional[dict] = None,
              exc: Optional[Exception] = None, replace: bool = False):
    process_manager = get_global_process_manager()
    if process_manager is None:
        logger.warning('Cannot set error for process locker: no process locker global instance is set')
    else:
        process_manager.current_process.set_error(error_msg, error_info, exc, replace)
        process_manager.save(process_manager.current_process)


def with_retry(func):
    @wraps(func)
    def new_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            logger.warning(f'Retrying after the error: {e.__class__.__name__}: {e}')
            return func(*args, **kwargs)
    new_func: func
    return new_func


class ProcessManager:
    def __init__(self, root_dir: Path, process_kind: ProcessKind, creator_pid: Optional[int] = None, **other_params):
        self.root_dir = root_dir
        self.filename = self._get_file_name(root_dir)
        self.current_process = TriblerProcess.current_process(process_kind, creator_pid, **other_params)
        self.primary_process = self.atomic_get_primary_process(process_kind, self.current_process)

    @classmethod
    def _get_file_name(cls, root_dir: Path) -> Path:  # The method is added for easier testing
        return root_dir / DB_FILENAME

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.filename))
        try:
            connection.execute('BEGIN EXCLUSIVE TRANSACTION')
            connection.execute(CREATE_TABLES)
            return connection
        except:  # noqa: E722
            connection.close()
            raise

    @contextmanager
    def transaction(self) -> ContextManager[sqlite3.Connection]:
        connection = None
        try:
            connection = self.connect()
            yield connection
            connection.execute('COMMIT')
            connection.close()

        except Exception as e:
            logger.exception(f'{e.__class__.__name__}: {e}')
            if connection:
                connection.close()  # pragma: no cover
            if isinstance(e, sqlite3.DatabaseError):
                self.filename.unlink(missing_ok=True)
            raise

    @with_retry
    def atomic_get_primary_process(self, kind: ProcessKind,
                                  current_process: Optional[TriblerProcess] = None) -> Optional[TriblerProcess]:
        primary_process = None
        with self.transaction() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            cursor = connection.execute("""
                SELECT * FROM processes WHERE kind = ? and "primary" = 1 ORDER BY rowid DESC LIMIT 1
            """, [kind.value])
            row = cursor.fetchone()
            if row is not None:
                previous_primary_process = TriblerProcess.from_row(row)
                if previous_primary_process.is_running():
                    primary_process = previous_primary_process
                else:
                    previous_primary_process.primary = 0
                    previous_primary_process.save(connection)

            if current_process is not None:
                if primary_process is None:
                    current_process.primary = 1
                    primary_process = current_process
                else:
                    current_process.primary = 0
                    current_process.canceled = 1
                current_process.save(connection)

            return primary_process

    @with_retry
    def save(self, process: TriblerProcess):
        with self.transaction() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            process.save(connection)

    def set_api_port(self, api_port: int):
        self.current_process.api_port = api_port
        self.save(self.current_process)

    def set_error(self, error_msg: Optional[str] = None, error_info: Optional[dict] = None,
                  exc: Optional[Exception] = None, replace: bool = False):
        self.current_process.set_error(error_msg, error_info, exc, replace)
        self.save(self.current_process)

    def sys_exit(self, exit_code: Optional[int] = None, error_msg: Optional[str] = None,
                 error_info: Optional[dict] = None, exc: Optional[Exception] = None, replace: bool = False):
        if error_msg is not None:
            self.current_process.set_error(error_msg, error_info, exc, replace)
        self.current_process.mark_finished(exit_code)
        self.save(self.current_process)
        exit_code = self.current_process.exit_code
        sys.exit(exit_code)

    @with_retry
    def get_last_processes(self, limit=6) -> List[TriblerProcess]:
        with self.transaction() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            cursor = connection.execute("""SELECT * FROM processes ORDER BY rowid DESC LIMIT ?""", [limit])
            result = [TriblerProcess.from_row(row) for row in cursor]
        result.reverse()
        return result
