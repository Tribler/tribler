from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

import psutil

from tribler.core.utilities.process_manager import sql_scripts
from tribler.core.utilities.process_manager.updating_thread import UpdatingThread
from tribler.core.utilities.process_manager.utils import with_retry
from tribler.core.version import version_id

if TYPE_CHECKING:
    from tribler.core.utilities.process_manager import ProcessManager


ALIVE_TIMEOUT = 5


class ProcessKind(Enum):
    GUI = 'gui'
    Core = 'core'


class TriblerProcess:
    def __init__(self, *,
                 manager: Optional[ProcessManager] = None,
                 rowid: Optional[int] = None,
                 row_version: int = 0,
                 uid: int,
                 pid: int,
                 creator_uid: Optional[int] = None,
                 creator_pid: Optional[int] = None,
                 kind: ProcessKind,
                 is_primary: bool = False,
                 app_version: str,
                 api_port: Optional[int] = None,
                 started_at: int,
                 last_alive_at: int,
                 is_finished: bool = False,
                 is_canceled: bool = False,
                 exit_code: Optional[int] = None,
                 error_msg: Optional[str] = None
                 ):
        self.uid = None
        self._manager = manager
        self.rowid = rowid
        self.row_version = row_version
        self.uid = uid
        self.pid = pid
        self.creator_uid = creator_uid
        self.creator_pid = creator_pid
        self.kind = kind
        self.is_primary = is_primary
        self.app_version = app_version
        self.api_port = api_port
        self.started_at = started_at
        self.last_alive_at = last_alive_at
        self.is_canceled = is_canceled
        self.is_finished = is_finished
        self.exit_code = exit_code
        self.error_msg = error_msg
        self.updating_thread: Optional[UpdatingThread] = None

    @property
    def manager(self) -> ProcessManager:
        if self._manager is None:
            raise RuntimeError('Tribler process manager is not set in process object')
        return self._manager

    @manager.setter
    def manager(self, manager: ProcessManager):
        self._manager = manager

    @property
    def is_current_process(self):
        manager = self._manager
        return manager and manager.current_process and manager.current_process.uid == self.uid

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
        rowid, row_version, uid, pid, creator_uid, creator_pid, kind, is_primary, \
            app_version, api_port, started_at, last_alive_at, is_finished, is_canceled, exit_code, error_msg = row

        return TriblerProcess(manager=manager,
                              rowid=rowid,
                              row_version=row_version,
                              uid=uid,
                              pid=pid,
                              creator_uid=creator_uid,
                              creator_pid=creator_pid,
                              kind=ProcessKind(kind),
                              is_primary=is_primary,
                              app_version=app_version,
                              api_port=api_port,
                              started_at=started_at,
                              last_alive_at=last_alive_at,
                              is_finished=is_finished,
                              is_canceled=is_canceled,
                              exit_code=exit_code,
                              error_msg=error_msg)

    def __str__(self) -> str:
        kind = self.kind.value.capitalize()
        elements: List[str] = []
        append = elements.append
        append('finished' if self.is_finished else 'running')

        manager = self._manager
        if manager and manager.current_process:

            if manager.current_process.uid == self.uid:
                append('current process')

            if manager.current_process.creator_uid == self.uid:
                append('parent process')

        if self.is_primary:
            append('primary')

        if self.is_canceled:
            append('canceled')

        append(f'uid={self.uid:x}')

        append(f'pid={self.pid}')

        if self.creator_uid is not None:
            append(f'gui_uid={self.creator_uid:x}')

        if self.creator_pid is not None:
            append(f'gui_pid={self.creator_pid}')

        started = datetime.utcfromtimestamp(self.started_at)
        append(f"version='{self.app_version}'")
        append(f"started='{started.strftime('%Y-%m-%d %H:%M:%S')}'")

        if self.api_port is not None:
            append(f'api_port={self.api_port}')

        if self.is_finished:
            finished = datetime.utcfromtimestamp(self.last_alive_at)
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
    def current_process(cls, *,
                        manager: Optional[ProcessManager] = None,
                        kind: ProcessKind,
                        creator_uid: Optional[int] = None,
                        creator_pid: Optional[int] = None,
                        ) -> TriblerProcess:
        """Constructs an object for a current process, specifying the PID value of the current process"""
        uid = secrets.randbits(32)
        pid = os.getpid()
        started_at = int(time.time())

        return cls(manager=manager,
                   row_version=0,
                   uid=uid,
                   pid=pid,
                   creator_uid=creator_uid,
                   creator_pid=creator_pid,
                   kind=kind,
                   app_version=version_id,
                   started_at=started_at,
                   last_alive_at=started_at)

    def start_updating_thread(self):
        if self.updating_thread:
            return
        self.updating_thread = UpdatingThread(process=self)
        self.updating_thread.start()

    @with_retry
    def become_primary(self) -> bool:
        """
        If there is no primary process already, makes the current process primary and returns the primary status
        """
        with self.manager.connect():
            primary_uid = self.manager.primary_process_uid(self.kind)
            if primary_uid is None or primary_uid == self.uid:
                self.is_primary = True
            else:
                self.is_canceled = True
            self.save()
        return bool(self.is_primary)

    def is_running(self):
        """Returns True if the object represents a running process"""
        if self.is_finished:
            return False

        if not psutil.pid_exists(self.pid):
            return False

        try:
            psutil_process = psutil.Process(self.pid)
            status = psutil_process.status()
        except psutil.Error as e:
            self.logger.warning(e)
            return False

        if status == psutil.STATUS_ZOMBIE:
            return False

        if int(time.time()) - self.last_alive_at > ALIVE_TIMEOUT:
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
        if self.updating_thread:
            self.updating_thread.should_stop.set()
            self.updating_thread.join()
            self.updating_thread = None

        self.is_primary = False
        self.is_finished = True
        self.last_alive_at = int(time.time())

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
                uid, pid, creator_uid, creator_pid, kind, is_primary,
                app_version, api_port, started_at, last_alive_at, is_finished, is_canceled, exit_code, error_msg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [self.uid, self.pid, self.creator_uid, self.creator_pid, self.kind.value, self.is_primary,
              self.app_version, self.api_port, self.started_at, self.last_alive_at, self.is_finished, self.is_canceled,
              self.exit_code, self.error_msg])
        self.rowid = cursor.lastrowid

    def _update(self, connection: sqlite3.Connection):
        """Update an existing row in the table"""
        prev_version = self.row_version
        self.row_version += 1
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE processes
            SET row_version = ?, is_primary = ?, api_port = ?, last_alive_at = ?,
                is_finished = ?, is_canceled = ?, exit_code = ?, error_msg = ?
            WHERE rowid = ? and row_version = ? and uid = ?
        """, [self.row_version, self.is_primary, self.api_port, self.last_alive_at,
              self.is_finished, self.is_canceled, self.exit_code, self.error_msg,
              self.rowid, prev_version, self.uid])

        if cursor.rowcount == 0:
            msg = f"Process {self} with rowid {self.rowid} and row version {prev_version} wasn't found in the database"
            raise RuntimeError(msg)

    def get_core_process(self) -> Optional[TriblerProcess]:
        """
        Returns Core process created by the current GUI process, or None if the Core process was not found in the DB.
        """
        if self.kind != ProcessKind.GUI:
            raise TypeError('The `get_core_process` method can only be used for a GUI process')

        with self.manager.connect() as connection:
            cursor = connection.execute(f"""
                SELECT {sql_scripts.SELECT_COLUMNS}
                FROM processes WHERE is_primary = 1 and kind = ? and creator_uid = ?
            """, [ProcessKind.Core.value, self.uid])
            rows = cursor.fetchall()
            if len(rows) > 1:  # should not happen
                raise RuntimeError('Multiple Core processes were found for a single GUI process')
            return TriblerProcess.from_row(self.manager, rows[0]) if rows else None
