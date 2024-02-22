from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

import psutil

from tribler.core.utilities.process_manager import sql_scripts
from tribler.core.utilities.process_manager.utils import with_retry
from tribler.core.version import version_id

if TYPE_CHECKING:
    from tribler.core.utilities.process_manager import ProcessManager


class ProcessKind(Enum):
    GUI = 'gui'
    Core = 'core'


class TriblerProcess:
    def __init__(self, manager: ProcessManager, pid: int, kind: ProcessKind, app_version: str, started_at: int,
                 row_version: int = 0, rowid: Optional[int] = None, creator_pid: Optional[int] = None,
                 primary: bool = False, canceled: bool = False, api_port: Optional[int] = None,
                 finished_at: Optional[int] = None, exit_code: Optional[int] = None, error_msg: Optional[str] = None):
        self.manager = manager
        self.rowid = rowid
        self.row_version = row_version
        self.pid = pid
        self.kind = kind
        self.primary = primary
        self.canceled = canceled
        self.app_version = app_version
        self.started_at = started_at
        self.creator_pid = creator_pid
        self.api_port = api_port
        self.finished_at = finished_at
        self.exit_code = exit_code
        self.error_msg = error_msg

    @property
    def logger(self) -> logging.Logger:
        """Used by the `with_retry` decorator"""
        return self.manager.logger

    @property
    def connection(self) -> Optional[sqlite3.Connection]:
        """Used by the `with_retry` decorator"""
        return self.manager.connection

    @with_retry
    def save(self):
        """Saves object into the database"""
        with self.manager.connect() as connection:
            if self.rowid is None:
                self._insert(connection)
            else:
                self._update(connection)

    @classmethod
    def from_row(cls, manager: ProcessManager, row: tuple) -> TriblerProcess:
        """Constructs an object from the database row"""
        rowid, row_version, pid, kind, primary, canceled, app_version, started_at, creator_pid, api_port, \
        finished_at, exit_code, error_msg = row

        return TriblerProcess(manager=manager, rowid=rowid, row_version=row_version, pid=pid, kind=ProcessKind(kind),
                              primary=primary, canceled=canceled, app_version=app_version, started_at=started_at,
                              creator_pid=creator_pid, api_port=api_port, finished_at=finished_at,
                              exit_code=exit_code, error_msg=error_msg)

    def __str__(self) -> str:
        kind = self.kind.value.capitalize()
        elements: List[str] = []
        append = elements.append
        append('finished' if self.finished_at or self.exit_code is not None else 'running')

        if self.is_current_process():
            append('current process')

        if self.primary:
            append('primary')

        if self.canceled:
            append('canceled')

        append(f'pid={self.pid}')

        if self.creator_pid is not None:
            append(f'gui_pid={self.creator_pid}')

        started = datetime.utcfromtimestamp(self.started_at)
        append(f"version='{self.app_version}'")
        append(f"started='{started.strftime('%Y-%m-%d %H:%M:%S')}'")

        if self.api_port is not None:
            append(f'api_port={self.api_port}')

        if self.finished_at:
            finished = datetime.utcfromtimestamp(self.finished_at)
            duration = finished - started
        else:
            duration = timedelta(seconds=int(time.time()) - self.started_at)
        append(f"duration='{duration}'")

        if self.exit_code is not None:
            append(f'exit_code={self.exit_code}')

        if self.error_msg:
            append(f'error={repr(self.error_msg)}')

        result = f'{kind}Process({", ".join(elements)})'
        return ''.join(result)

    @classmethod
    def current_process(cls, manager: ProcessManager, kind: ProcessKind, owns_lock: bool,
                        creator_pid: Optional[int] = None) -> TriblerProcess:
        """Constructs an object for a current process, specifying the PID value of the current process"""
        pid = os.getpid()
        psutil_process = psutil.Process(pid)
        started_at = int(psutil_process.create_time())
        return cls(manager=manager, row_version=0, pid=pid, kind=kind, primary=owns_lock,
                   app_version=version_id, started_at=started_at, creator_pid=creator_pid)

    def is_current_process(self) -> bool:
        """Returns True if the object represents the current process"""
        return self.pid == os.getpid() and self.is_running()

    def is_running(self):
        """Returns True if the object represents a running process"""
        if not psutil.pid_exists(self.pid):
            return False

        try:
            psutil_process = psutil.Process(self.pid)
            status = psutil_process.status()
        except (psutil.Error, MemoryError) as e:
            self.logger.warning(e)
            return False

        if status == psutil.STATUS_ZOMBIE:
            return False

        psutil_process_create_time = int(psutil_process.create_time())
        if psutil_process_create_time > self.started_at:
            # The same PID value was reused for a new process, so the previous process is not running anymore
            return False

        return True

    def set_api_port(self, api_port: int):
        self.api_port = api_port
        self.save()

    def set_error(self, error: Any, replace: bool = False):
        # It is expected for `error` to be str or an instance of exception, but values of other types
        # are handled gracefully as well: everything except None is converted to str
        if error is not None and not isinstance(error, str):
            error = f"{error.__class__.__name__}: {error}"

        if replace or not self.error_msg:
            self.error_msg = error

        self.save()

    def finish(self, exit_code: Optional[int] = None):
        self.primary = False
        self.finished_at = int(time.time())

        # if exit_code is specified, it overrides the previously set exit code
        if exit_code is not None:
            self.exit_code = exit_code

        # if no exit code is specified, use exit code 0 (success) as a default value
        if self.exit_code is None:
            self.exit_code = 0 if not self.error_msg else 1

        self.save()

    def _insert(self, connection: sqlite3.Connection):
        """Insert a new row into the table"""
        self.row_version = 0
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO processes (
                pid, kind, "primary", canceled, app_version, started_at,
                creator_pid, api_port, finished_at, exit_code, error_msg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [self.pid, self.kind.value, int(self.primary), int(self.canceled), self.app_version, self.started_at,
              self.creator_pid, self.api_port, self.finished_at, self.exit_code, self.error_msg])
        self.rowid = cursor.lastrowid

    def _update(self, connection: sqlite3.Connection):
        """Update an existing row in the table"""
        prev_version = self.row_version
        self.row_version += 1
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE processes
            SET row_version = ?, "primary" = ?, canceled = ?, creator_pid = ?, api_port = ?,
                finished_at = ?, exit_code = ?, error_msg = ?
            WHERE rowid = ? and row_version = ? and pid = ? and kind = ? and app_version = ? and started_at = ?
        """, [self.row_version, int(self.primary), int(self.canceled), self.creator_pid, self.api_port,
              self.finished_at, self.exit_code, self.error_msg,
              self.rowid, prev_version, self.pid, self.kind.value, self.app_version, self.started_at])
        if cursor.rowcount == 0:
            self.logger.error(f'Row {self.rowid} with row version {prev_version} was not found')

    def get_core_process(self) -> Optional[TriblerProcess]:
        """
        Returns Core process created by the current GUI process, or None if the Core process was not found in the DB.

        Under the assumption that GUI process spawns the Core process, the core process is selected from the
        process database with rowid higher than the rowid of the GUI process. The rowid is a unique autoincrement
        identifier.
        """
        if self.kind != ProcessKind.GUI:
            raise TypeError('The `get_core_process` method can only be used for a GUI process')

        with self.manager.connect() as connection:
            cursor = connection.execute(f"""
                SELECT {sql_scripts.SELECT_COLUMNS}
                FROM processes WHERE "primary" = 1 and kind = ? and creator_pid = ? and rowid > ?
            """, [ProcessKind.Core.value, self.pid, self.rowid])
            rows = cursor.fetchall()
            if len(rows) > 1:  # should not happen
                raise RuntimeError('Multiple Core processes were found for a single GUI process')
            return TriblerProcess.from_row(self.manager, rows[0]) if rows else None
