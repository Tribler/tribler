from __future__ import annotations

import contextlib
import logging
import sys
import threading
import time
import traceback
from asyncio import get_event_loop
from dataclasses import dataclass
from io import StringIO
from operator import attrgetter
from pathlib import Path
from types import FrameType
from typing import Callable, Dict, Iterable, Optional, Type, TypeVar
from weakref import WeakSet

from pony import orm
from pony.orm import core
from pony.orm.core import Database, select
from pony.orm.dbproviders import sqlite
from pony.utils import cut_traceback, localbase
from tribler.core.utilities.db_corruption_handling import sqlite_replacement
from tribler.core.utilities.db_corruption_handling.base import handle_db_if_corrupted

# Inject sqlite replacement to PonyORM sqlite database provider to use augmented version of Connection and Cursor
# classes that handle database corruption errors. All connection and cursor methods, such as execute and fetchone,
# raise DatabaseIsCorrupted exception if the database is corrupted. Also, the marker file with ".is_corrupted"
# extension is created alongside the corrupted database file. As a result of exception, the Tribler Core immediately
# stops with the error code 99. Tribler GUI handles this error code by showing the message to the user and automatically
# restarting the Core. After the Core is restarted, the database is re-created from scratch.
sqlite.sqlite = sqlite_replacement


SLOW_DB_SESSION_DURATION_THRESHOLD = 1.0

logger = logging.getLogger(__name__)

databases_to_track: WeakSet[TrackedDatabase] = WeakSet()

StatDict = Dict[Optional[str], core.QueryStat]


E = TypeVar('E', bound=core.Entity)


def iterable(cls: Type[E]) -> Iterable[E]:
    return cls


def table_exists(cursor: sqlite_replacement.Cursor, table_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def get_db_version(db_path, default: int = None) -> int:
    handle_db_if_corrupted(db_path)
    version = None

    if db_path.exists():
        with contextlib.closing(sqlite_replacement.connect(db_path)) as connection:
            with connection:
                cursor = connection.cursor()
                if table_exists(cursor, 'MiscData'):
                    cursor.execute("SELECT value FROM MiscData WHERE name == 'db_version'")
                    row = cursor.fetchone()
                    version = int(row[0]) if row else None

    if version is not None:
        return version

    if default is not None:
        return default

    raise RuntimeError(f'The version value is not found in database {db_path}')


# pylint: disable=bad-staticmethod-argument
def get_or_create(cls: Type[E], create_kwargs=None, **kwargs) -> E:
    """Get or create db entity.
    Args:
        cls: Entity's class, eg: `self.instance.Peer`
        create_kwargs: Additional arguments for creating new entity
        **kwargs: Arguments for selecting or for creating in case of missing entity

    Returns: Entity's instance
    """
    obj = cls.get_for_update(**kwargs)
    if not obj:
        if create_kwargs:
            kwargs.update(create_kwargs)
        obj = cls(**kwargs)
    return obj


def get_max(cls: Type[core.Entity], column_name='rowid') -> int:
    """Get max row ID of an db.Entity.
    Args:
        cls: Entity's class, eg: `self.instance.Peer`
        column_name: Name of the column to aggregate
    Returns: Max row ID or 0.
    """
    return select(max(getattr(obj, column_name)) for obj in cls).get() or 0


async def run_threaded(db: Database, func: Callable, *args, **kwargs):
    """Run `func` threaded and close DB connection at the end of the execution.

    Args:
        db: the DB to be closed
        func: the function to be executed threaded
        *args: args for the function call
        **kwargs: kwargs for the function call

    Returns: a result of the func call.

    You should use `run_threaded` to wrap all functions that should be executed from a separate thread and work with
    the database. The `run_threaded` function ensures that all database connections opened in worker threads are
    properly closed before the Tribler shutdown.

    The Asyncio `run_in_executor` method executes its argument in a separate worker thread. After the db_session is
    over, PonyORM caches the connection to the database to re-use it again later in the same thread. It was previously
    reported that some obscure problems could be observed during the Tribler shutdown if connections in the Tribler
    worker threads are not closed properly.
    """

    def wrapper():
        try:
            return func(*args, **kwargs)
        finally:
            # @ichorid: this is a workaround for closing threadpool connections
            # Remark: maybe subclass ThreadPoolExecutor to handle this automatically?
            is_main_thread = isinstance(threading.current_thread(), threading._MainThread)  # pylint: disable=W0212
            if not is_main_thread:
                db.disconnect()

    return await get_event_loop().run_in_executor(None, wrapper)


class Local(localbase):
    def __init__(self):
        self.db_session_info: Optional[DbSessionInfo] = None


local = Local()


@dataclass
class DbSessionInfo:
    current_db_session_stack: traceback.StackSummary
    start_time: float
    acquire_count: int = 0
    # A single db_session can work with several databases, and for each database it can sequentially create several
    # transactions. `lock_wait_total_duration` is a sum of the time the db_session thread awaited the locks.
    lock_wait_total_duration: float = 0
    # A single db_session can work with several databases, and for each database, it can sequentially create several
    # transactions. `lock_hold_total_duration` is the sum of the time the db_session thread awaits the locks.
    # If a single db_session processed two parallel transactions in two different databases, the resulting duration
    # may be greater than the entire db_session duration. Anyway, this aggregated duration can be helpful
    # when debugging slow db_sessions.
    lock_hold_total_duration: float = 0


_warning_template = """Long db_session detected.
Session info:
    Thread: '{current_thread_name}'
    db_session duration: {db_session_duration:.3f} seconds
    db_session waited for the exclusive lock for {lock_wait_total_duration:.3f} seconds
    db_session held exclusive lock for {lock_hold_total_duration:.3f} seconds
The db_session stack:
{db_session_stack}

Queries statistics for the current db_session:
{db_session_query_statistics}

Queries statistics for the entire application:
{application_query_statistics}
"""


class TriblerDbSession(core.DBSessionContextManager):
    track_slow_db_sessions = False

    def __init__(self, *args, duration_threshold: Optional[float] = None, **kwargs):
        super().__init__(*args, **kwargs)
        # `duration_threshold` specifies how long db_session should be to trigger the long db_session warning.
        # When `duration_threshold` is None, `SLOW_DB_SESSION_DURATION_THRESHOLD` value is used instead.
        self.duration_threshold = duration_threshold

    def _enter(self):
        is_top_level_db_session = core.local.db_session is None  # None means that no db_session was started before
        super()._enter()  # if core.local.db_session is None, this call assigns a value to it
        if is_top_level_db_session:
            self._start_tracking()

    def __exit__(self, exc_type=None, exc=None, tb=None):
        try:
            super().__exit__(exc_type, exc, tb)
        finally:
            was_top_level_db_session = core.local.db_session is None
            if was_top_level_db_session:
                self._stop_tracking()

    def _start_tracking(self):
        for db in databases_to_track:
            # Clear the local statistics for all databases, so we can accumulate new local statistics in db session
            db.merge_local_stats()

        # If the tracking of slow db_sessions is not enabled, we still create the DbSessionInfo instance, but without
        # the current db session stack. It is fast, and this way it is easier to avoid race conditions for the case
        # when the track_slow_db_sessions value is changed on the fly during the db session execution.
        local.db_session_info = DbSessionInfo(
            current_db_session_stack=self._extract_stack() if self.track_slow_db_sessions else None,
            start_time=time.time()
        )

    def _stop_tracking(self):
        info: DbSessionInfo = local.db_session_info
        local.db_session_info = None

        if info.current_db_session_stack is None:
            # The tracking of slow db sessions was not enabled when the db session was started, so we skip analyzing it
            return

        start_time = info.start_time
        db_session_duration = time.time() - start_time

        threshold = SLOW_DB_SESSION_DURATION_THRESHOLD if self.duration_threshold is None else self.duration_threshold
        if db_session_duration > threshold:
            self._log_warning(db_session_duration, info)

    @staticmethod
    def _extract_stack() -> traceback.StackSummary:
        current_frame: FrameType = sys._getframe() # pylint: disable=protected-access
        # The stack layout at that moment:
        # * An interesting Tribler frame that we want to see in the stacktrace
        # * (an optional frame of the autogenerated code block if @db_session is used as a decorator)
        # * Line `db_session._enter()` in `DBSessionContextManager.__enter__()`
        # * Line `self._start_tracking()` in `DBSessionContextManager._enter()`
        # * Line `current_db_session_stack=self._extract_stack()` in `TriblerDbSession._start_tracking()`
        # * The current line inside `TriblerDbSession._extract_stack()`
        # So, we do .f_back.f_back.f_back.f_back to remove the four uninteresting frames at the end,
        # and then optionally perform .f_back one more time if the frame is related to the autogenerated code
        db_session_frame: FrameType = current_frame.f_back.f_back.f_back.f_back
        if db_session_frame.f_code.co_filename == '<string>':
            # When @db_session is used as a decorator applied to a function, one frame corresponds to an
            # auto-generated function wrapper created by a `@decorator` decorator that copies the function signature.
            # To show the frame where the @db_session-decorated function is called, we need to remove this frame.
            db_session_frame = db_session_frame.f_back

        stack = traceback.StackSummary.extract(traceback.walk_stack(db_session_frame), limit=2,
                                               capture_locals=False, lookup_lines=False)
        stack.reverse()
        return stack

    def _log_warning(self, db_session_duration: float, info: DbSessionInfo):
        db_session_query_statistics = self._summarize_stat(db.local_stats for db in databases_to_track)

        for db in databases_to_track:
            db.merge_local_stats()
        application_query_statistics = self._summarize_stat(db.global_stats for db in databases_to_track)

        thread_name = threading.current_thread().name
        formatted_stack = self._format_stack(info.current_db_session_stack).rstrip()
        message = self._format_warning(db_session_duration, thread_name, formatted_stack,
                                       info.lock_wait_total_duration, info.lock_hold_total_duration,
                                       db_session_query_statistics, application_query_statistics)
        logger.warning(message)

    @staticmethod
    def _format_warning(db_session_duration: float, thread_name: str, formatted_stack: str,
                        lock_wait_total_duration: float, lock_hold_total_duration: float,
                        db_session_query_statistics: str, application_query_statistics: str) -> str:
        return _warning_template.format(**dict(
            db_session_duration=db_session_duration,
            current_thread_name=thread_name,
            db_session_stack=formatted_stack,
            lock_wait_total_duration=lock_wait_total_duration,
            lock_hold_total_duration=lock_hold_total_duration,
            db_session_query_statistics=db_session_query_statistics,
            application_query_statistics=application_query_statistics
        ))

    @staticmethod
    def _format_stack(stack_summary: traceback.StackSummary) -> str:
        memory_stream = StringIO()
        traceback.print_list(stack_summary, file=memory_stream)
        return memory_stream.getvalue()

    def _summarize_stat(self, stats_iter: Iterable[StatDict]) -> str:
        stats = self._merge_stats(stats_iter)
        total_stat = stats.get(None)  # With the None key, stats keep aggregated statistics for all queries
        if total_stat is None or total_stat.db_count == 0:
            return 'No database queries performed'

        def query_count(n: int) -> str:
            return '1 query' if n == 1 else f'{n} queries'

        def indent(sql: str) -> str:
            return '\n'.join('    ' + line for line in sql.split('\n'))

        result = f'{query_count(total_stat.db_count)} executed in a total of {total_stat.sum_time:.3f} seconds'
        if len(stats) > 1:
            slowest = max((stat for stat in stats.values() if stat.sql), key=attrgetter('max_time'))
            result += f';\nThe slowest query ({slowest.max_time:.3f} seconds) is:\n{indent(slowest.sql)}'
        return result

    @staticmethod
    def _merge_stats(stats_iter: Iterable[StatDict]) -> StatDict:
        result: StatDict = {}
        for stats in stats_iter:
            for sql, stat in stats.items():
                if sql not in result:
                    result[sql] = stat.copy()
                else:
                    result[sql].merge(stat)
        return result


class TriblerSQLiteProvider(sqlite.SQLiteProvider):

    # It is impossible to override the __init__ method without breaking the `SQLiteProvider.get_pool` method's logic.
    # Therefore, we don't initialize a new attribute `_acquire_time` inside a class constructor method.
    # Instead, we set its initial value at a class level.
    _acquire_time: float = 0  # A time when the current provider were able to acquire the database lock

    def acquire_lock(self):
        # Adds tracking of a db_session's lock wait duration and lock acquire count
        t1 = time.time()
        super().acquire_lock()
        info = local.db_session_info
        if info is not None:
            t2 = time.time()
            self._acquire_time = t2
            info.acquire_count += 1
            lock_wait_duration = t2 - t1
            info.lock_wait_total_duration += lock_wait_duration

    def release_lock(self):
        # Adds tracking of a db_session's total lock hold duration
        super().release_lock()
        info = local.db_session_info
        if info is not None:
            acquire_time = self._acquire_time
            lock_hold_duration = time.time() - acquire_time
            info.lock_hold_total_duration += lock_hold_duration


db_session = TriblerDbSession()
orm.db_session = orm.core.db_session = db_session


class TrackedDatabase(Database):
    # TriblerDatabase extends the functionality of the Database class in the following ways:
    # * It adds handling the case when the database file is corrupted
    # * It accumulates and shows statistics on slow database queries

    def __init__(self):
        databases_to_track.add(self)
        super().__init__()

    @cut_traceback
    def bind(self, **kwargs):
        provider = kwargs.pop('provider', None)
        if provider and provider != 'sqlite':
            raise TypeError(f"Invalid 'provider' argument for TriblerDatabase: {provider!r}")

        filename = kwargs.get('filename', None)
        if filename and filename not in {':memory:', ':sharedmemory:'}:
            db_path = Path(filename)
            if not db_path.absolute():
                raise ValueError(f"The 'filename' attribute is expected to be an absolute path. Got: {filename}")

            handle_db_if_corrupted(db_path)

        self._bind(TriblerSQLiteProvider, **kwargs)


def track_slow_db_sessions():
    TriblerDbSession.track_slow_db_sessions = True
