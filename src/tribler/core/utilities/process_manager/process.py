from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime
from enum import Enum
from typing import Optional, Union

import psutil

from tribler.core.version import version_id

logger = logging.getLogger(__name__)


class ProcessKind(Enum):
    GUI = 'gui'
    Core = 'core'


class TriblerProcess:
    def __init__(self, pid: int, kind: ProcessKind, app_version: str, started_at: int,
                 rowid: Optional[int] = None, creator_pid: Optional[int] = None, primary: int = 0, canceled: int = 0,
                 row_version: int = 0, api_port: Optional[int] = None, finished_at: Optional[int] = None,
                 exit_code: Optional[int] = None, error_msg: Optional[str] = None):
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

    @classmethod
    def from_row(cls, row: tuple) -> TriblerProcess:
        rowid, row_version, pid, kind, primary, canceled, app_version, started_at, creator_pid, api_port, \
            finished_at, exit_code, error_msg = row

        kind = ProcessKind(kind)

        return TriblerProcess(rowid=rowid, row_version=row_version, pid=pid, kind=kind, primary=primary,
                              canceled=canceled, app_version=app_version, started_at=started_at,
                              creator_pid=creator_pid, api_port=api_port, finished_at=finished_at,
                              exit_code=exit_code, error_msg=error_msg)

    def describe(self):
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
    def current_process(cls, kind: ProcessKind, creator_pid: Optional[int] = None) -> TriblerProcess:
        return cls(pid=os.getpid(), kind=kind, app_version=version_id, started_at=int(time.time()),
                   creator_pid=creator_pid, row_version=0)

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

    def set_error(self, error: Union[str | Exception], replace: bool = False):
        if isinstance(error, Exception):
            error = f"{error.__class__.__name__}: {error}"
        self.error_msg = error if replace else (self.error_msg or error)

    def mark_finished(self, exit_code: Optional[int] = None):
        self.primary = 0
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
                    pid, kind, "primary", canceled, app_version, started_at,
                    creator_pid, api_port, finished_at, exit_code, error_msg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [self.pid, self.kind.value, self.primary, self.canceled, self.app_version, self.started_at,
                  self.creator_pid, self.api_port, self.finished_at, self.exit_code, self.error_msg])
            self.rowid = cursor.lastrowid
        else:
            prev_version = self.row_version
            self.row_version += 1
            cursor.execute("""
                UPDATE processes
                SET row_version = ?, "primary" = ?, canceled = ?, creator_pid = ?, api_port = ?,
                    finished_at = ?, exit_code = ?, error_msg = ?
                WHERE rowid = ? and row_version = ? and pid = ? and kind = ? and app_version = ? and started_at = ?
            """, [self.row_version, self.primary, self.canceled, self.creator_pid, self.api_port,
                  self.finished_at, self.exit_code, self.error_msg,
                  self.rowid, prev_version, self.pid, self.kind.value, self.app_version, self.started_at])
            if cursor.rowcount == 0:
                logger.error(f'Row {self.rowid} with row version {prev_version} was not found')

    def _before_insert_check(self):
        if self.row_version:
            logger.error(f"The `row_version` value for a new process row should not be set. Got: {self.row_version}")
