from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import ContextManager, List, Optional

import psutil
from decorator import contextmanager

from tribler.core.version import version_id

logger = logging.getLogger(__name__)

DB_FILENAME = 'processes.sqlite'

CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS processes (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        row_version INTEGER NOT NULL DEFAULT 0,
        pid INTEGER NOT NULL,
        kind TEXT NOT NULL,
        active INT NOT NULL,
        canceled INT NOT NULL,
        app_version TEXT NOT NULL,
        started_at INT NOT NULL,
        creator_pid INT,
        api_port INT,
        shutdown_request_pid INT,
        shutdown_requested_at INT, 
        finished_at INT,
        exit_code INT,
        error_msg TEXT,
        error_info JSON,
        other_params JSON
    )
"""


class ProcessKind(Enum):
    GUI = 'gui'
    Core = 'core'


class TriblerProcess:
    def __init__(self, pid: int, kind: ProcessKind, app_version: str, started_at: int,
                 rowid: Optional[int] = None, creator_pid: Optional[int] = None, active: int = 0, canceled: int = 0,
                 row_version: int = 0, api_port: Optional[int] = None, finished_at: Optional[int] = None,
                 exit_code: Optional[int] = None, error_msg: Optional[str] = None, error_info: Optional[dict] = None,
                 shutdown_request_pid: Optional[int] = None, shutdown_requested_at: Optional[int] = None,
                 other_params: Optional[dict] = None):
        self.rowid = rowid
        self.row_version = row_version
        self.pid = pid
        self.kind = kind
        self.active = active
        self.canceled = canceled
        self.app_version = app_version
        self.started_at = started_at
        self.creator_pid = creator_pid
        self.api_port = api_port
        self.finished_at = finished_at
        self.exit_code = exit_code
        self.error_msg = error_msg
        self.error_info = error_info
        self.shutdown_request_pid = shutdown_request_pid
        self.shutdown_requested_at = shutdown_requested_at
        self.other_params = other_params

    @staticmethod
    def _to_json(value) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def _from_json(value) -> Optional[dict]:
        if value is None:
            return None
        return json.loads(value)

    @classmethod
    def from_row(cls, row: tuple) -> TriblerProcess:
        rowid, row_version, pid, kind, active, canceled, app_version, started_at, creator_pid, api_port, \
            shutdown_request_pid, shutdown_requested_at, finished_at, exit_code, error_msg, error_info, \
            other_params = row

        kind = ProcessKind(kind)

        return TriblerProcess(rowid=rowid, row_version=row_version, pid=pid, kind=kind, active=active, canceled=canceled,
                              app_version=app_version, started_at=started_at, creator_pid=creator_pid,
                              api_port=api_port, shutdown_request_pid=shutdown_request_pid,
                              shutdown_requested_at=shutdown_requested_at, finished_at=finished_at,
                              exit_code=exit_code, error_msg=error_msg, error_info=cls._from_json(error_info),
                              other_params=cls._from_json(other_params))

    def describe(self):
        kind = self.kind.value.capitalize()
        flags = f"{'active, ' if self.active else ''}{'canceled, ' if self.canceled else ''}"
        result = [f'{kind}Process({flags}pid={self.pid}']
        if self.creator_pid is not None:
            result.append(f', gui_pid={self.creator_pid}')
        started = datetime.utcfromtimestamp(self.started_at)
        result.append(f", version='{self.app_version}', started='{started.strftime('%Y-%m-%d %H:%M:%S')}'")
        if self.api_port is not None:
            result.append(f', api_port={self.api_port}')
        if self.finished_at:
            finished = datetime.utcfromtimestamp(self.finished_at)
            duration = finished - started
            result.append(f", duration='{duration}'")
        if self.exit_code is not None:
            result.append(f', exit_code={self.exit_code}')
        if self.error_msg:
            result.append(f', error={repr(self.error_msg)}')
        result.append(')')
        return ''.join(result)

    @classmethod
    def current_process(cls, kind: ProcessKind, creator_pid: Optional[int] = None, **other_params) -> TriblerProcess:
        return cls(pid=os.getpid(), kind=kind, app_version=version_id, started_at=int(time.time()),
                   creator_pid=creator_pid, row_version=0, other_params=other_params or None)

    def is_current_process(self):
        return self.pid == os.getpid()

    def is_running(self):
        if not psutil.pid_exists(self.pid):
            return False

        try:
            process = psutil.Process(self.pid)
            status = process.status()
        except psutil.Error as e:
            logger.warning(e)
            return False

        if status == psutil.STATUS_ZOMBIE:
            return False

        if process.create_time() > self.started_at:
            return False

        return True

    def set_error(self, error_msg: Optional[str] = None, error_info: Optional[dict] = None,
                  exc: Optional[Exception] = None, replace: bool = False):
        if exc and not error_msg:
            error_msg = f"{exc.__class__.__name__}: {exc}"

        if replace:
            self.error_msg = error_msg
            self.error_info = error_info
        else:
            self.error_msg = self.error_msg or error_msg
            self.error_info = self.error_info or error_info

    def mark_finished(self, exit_code: Optional[int] = None):
        self.active = 0
        self.finished_at = int(time.time())

        # if exit_code is specified, it overrides the previously set exit code
        if exit_code is not None:
            self.exit_code = exit_code

        # if no exit code is specified, use exit code 0 (success) as a default value
        if self.exit_code is None:
            self.exit_code = 0 if not self.error_msg else 1

    def save(self, con: sqlite3.Connection):
        cursor = con.cursor()
        if self.rowid is None:
            self._before_insert_check()
            self.row_version = 0
            cursor.execute("""
                INSERT INTO processes (
                    pid, kind, active, canceled, app_version, started_at,
                    creator_pid, api_port, shutdown_request_pid, shutdown_requested_at,
                    finished_at, exit_code, error_msg, error_info, other_params
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [self.pid, self.kind.value, self.active, self.canceled, self.app_version, self.started_at,
                  self.creator_pid, self.api_port, self.shutdown_request_pid, self.shutdown_requested_at,
                  self.finished_at, self.exit_code, self.error_msg, self._to_json(self.error_info),
                  self._to_json(self.other_params)])
            self.rowid = cursor.lastrowid
        else:
            prev_version = self.row_version
            self.row_version += 1
            cursor.execute("""
                UPDATE processes
                SET row_version = ?, active = ?, canceled = ?, creator_pid = ?, api_port = ?,
                    shutdown_request_pid = ?, shutdown_requested_at = ?, finished_at = ?,
                    exit_code = ?, error_msg = ?, error_info = ?, other_params = ?
                WHERE rowid = ? and row_version = ? and pid = ? and kind = ? and app_version = ? and started_at = ?
            """, [self.row_version, self.active, self.canceled, self.creator_pid, self.api_port,
                  self.shutdown_request_pid, self.shutdown_requested_at, self.finished_at,
                  self.exit_code, self.error_msg, self._to_json(self.error_info),
                  self._to_json(self.other_params), self.rowid, prev_version, self.pid, self.kind.value,
                  self.app_version, self.started_at])
            if cursor.rowcount == 0:
                logger.error(f'Row {self.rowid} with row version {prev_version} was not found')

    def _before_insert_check(self):
        if self.row_version:
            logger.error(f"The `row_version` value for a new process row should not be set. Got: {self.row_version}")


global_process_manager: Optional[ProcessManager] = None

_lock = Lock()


def set_global_process_manager(process_manager: Optional[ProcessManager]):
    global global_process_manager  # pylint: disable=global-statement
    with _lock:
        global_process_manager = process_manager


def get_global_process_manager() -> Optional[ProcessManager]:
    with _lock:
        return global_process_manager


def set_api_port(api_port: int):
    process_manager = get_global_process_manager()
    if process_manager is None:
        logger.warning('Cannot set api_port for process locker: no process locker global instance is set')
    else:
        process_manager.set_api_port(api_port)


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
    filename: Path
    current_process: TriblerProcess
    active_process: TriblerProcess

    def __init__(self, root_dir: Path, process_kind: ProcessKind, creator_pid: Optional[int] = None, **other_params):
        self.root_dir = root_dir
        self.filename = self._get_file_name(root_dir)
        self.current_process = TriblerProcess.current_process(process_kind, creator_pid, **other_params)
        self.active_process = self.atomic_get_active_process(process_kind, self.current_process)

    @classmethod
    def _get_file_name(cls, root_dir: Path) -> Path:  # The method is added for easier testing
        return root_dir / DB_FILENAME

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.filename))
        try:
            connection.execute('BEGIN EXCLUSIVE TRANSACTION')
            connection.execute(CREATE_SQL)
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
    def atomic_get_active_process(self, kind: ProcessKind,
                                  current_process: Optional[TriblerProcess] = None) -> Optional[TriblerProcess]:
        active_process = None
        with self.transaction() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            cursor = connection.execute("""
                SELECT * FROM processes WHERE kind = ? and active = 1 ORDER BY rowid DESC LIMIT 1
            """, [kind.value])
            row = cursor.fetchone()
            if row is not None:
                previous_active_process = TriblerProcess.from_row(row)
                if previous_active_process.is_running():
                    active_process = previous_active_process
                else:
                    previous_active_process.active = 0
                    previous_active_process.save(connection)

            if current_process is not None:
                if active_process is None:
                    current_process.active = 1
                    active_process = current_process
                else:
                    current_process.active = 0
                    current_process.canceled = 1
                current_process.save(connection)

            return active_process

    @with_retry
    def save(self, process: TriblerProcess):
        with self.transaction() as connection:  # pylint: disable=not-context-manager  # false Pylint alarm
            process.save(connection)

    def set_api_port(self, api_port: int):
        self.current_process.api_port = api_port
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
