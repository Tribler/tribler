from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING, Union

import psutil

from tribler.core.utilities.process_manager.utils import with_retry
from tribler.core.version import version_id

if TYPE_CHECKING:
    from tribler.core.utilities.process_manager import ProcessManager


class ProcessKind(Enum):
    GUI = 'gui'
    Core = 'core'


class TriblerProcess:
    def __init__(self, pid: int, kind: ProcessKind, app_version: str, started_at: int,
                 row_version: int = 0, rowid: Optional[int] = None, creator_pid: Optional[int] = None,
                 primary: bool = False, canceled: bool = False, api_port: Optional[int] = None,
                 finished_at: Optional[int] = None, exit_code: Optional[int] = None, error_msg: Optional[str] = None,
                 manager: Optional[ProcessManager] = None):
        self._manager = manager
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
    def manager(self) -> ProcessManager:
        if self._manager is None:
            raise RuntimeError('Tribler process manager is not set in process object')
        return self._manager

    @manager.setter
    def manager(self, manager: ProcessManager):
        self._manager = manager

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
        flags = f"{'primary, ' if self.primary else ''}{'canceled, ' if self.canceled else ''}"
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
    def current_process(cls, kind: ProcessKind,
                        creator_pid: Optional[int] = None,
                        manager: Optional[ProcessManager] = None) -> TriblerProcess:
        """Constructs an object for a current process, specifying the PID value of the current process"""
        return cls(manager=manager, row_version=0, pid=os.getpid(), kind=kind,
                   app_version=version_id, started_at=int(time.time()), creator_pid=creator_pid)

    def is_current_process(self) -> bool:
        """Returns True if the object represents the current process"""
        return self.pid == os.getpid() and self.is_running()

    @with_retry
    def become_primary(self) -> bool:
        """
        If there is no primary process already, makes the current process primary and returns the primary status
        """
        with self.manager.connect():
            # for a new process object self.rowid is None
            primary_rowid = self.manager.primary_process_rowid(self.kind)
            if primary_rowid is None or primary_rowid == self.rowid:
                self.primary = True
            else:
                self.canceled = True
            self.save()
        return bool(self.primary)

    def is_running(self):
        """Returns True if the object represents a running process"""
        if not psutil.pid_exists(self.pid):
            return False

        try:
            process = psutil.Process(self.pid)
            status = process.status()
        except psutil.Error as e:
            self.logger.warning(e)
            return False

        if status == psutil.STATUS_ZOMBIE:
            return False

        if process.create_time() > self.started_at:
            return False

        return True

    def set_api_port(self, api_port: int):
        self.api_port = api_port
        self.save()

    def set_error(self, error: Union[str | Exception], replace: bool = False):
        if isinstance(error, Exception):
            error = f"{error.__class__.__name__}: {error}"
        self.error_msg = error if replace else (self.error_msg or error)
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
