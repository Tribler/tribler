import sqlite3
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from pony.orm.core import QueryStat, Required
from tribler.core.utilities import pony_utils
from tribler.core.utilities.pony_utils import DatabaseIsCorrupted, _mark_db_as_corrupted, get_db_version, \
    handle_db_if_corrupted, \
    marking_corrupted_db, table_exists

EMPTY_DICT = {}


def test_merge_stats_empty_iter():
    empty_iter = []
    merged_stats = pony_utils.TriblerDbSession._merge_stats(empty_iter)  # pylint: disable=protected-access
    assert merged_stats == EMPTY_DICT  # to satisfy linter


def test_merge_stats():
    stats1 = {
        None: QueryStat(None, duration=3.0),  # aggregated stats for database 1
        "SQL1": QueryStat("SQL1", duration=1.0),
        "SQL2": QueryStat("SQL2", duration=2.0),
        "SQL3": QueryStat("SQL3", duration=3.0),
    }
    stats2 = {
        None: QueryStat(None, duration=3.0),  # aggregated stats for database 2
        "SQL2": QueryStat("SQL2", duration=3.0),
        "SQL3": QueryStat("SQL3", duration=2.0),
        "SQL4": QueryStat("SQL4", duration=4.0),
    }
    stats_iter = [stats1, stats2]
    merged_stats = pony_utils.TriblerDbSession._merge_stats(stats_iter)  # pylint: disable=protected-access
    max_times = {sql: stat.max_time for sql, stat in merged_stats.items()}
    assert max_times == {
        None: pytest.approx(3.0),
        "SQL1": pytest.approx(1.0),
        "SQL2": pytest.approx(3.0),
        "SQL3": pytest.approx(3.0),
        "SQL4": pytest.approx(4.0),
    }


def test_patched_db_session(tmp_path):
    # The test is added for better coverage of TriblerDbSession methods

    with patch('tribler.core.utilities.pony_utils.TriblerDbSession.track_slow_db_sessions', True):
        db = pony_utils.TriblerDatabase()
        db.bind(provider='sqlite', filename=str(tmp_path / 'db.sqlite'), create_db=True)

        class Entity1(db.Entity):
            a = Required(int)

        db.generate_mapping(create_tables=True)

        @pony_utils.db_session(duration_threshold=0.0)
        def _perform_queries():
            for i in range(10):
                Entity1(a=i)
            db.commit()
            db.rollback()
            Entity1.select().fetch()

        with patch.object(pony_utils.TriblerDbSession, '_format_warning',
                          return_value='<warning text>') as format_warning_mock:
            _perform_queries()
        format_warning_mock.assert_called()


# As the duration threshold is not specified, on each invocation the current dynamic value
# of SLOW_DB_SESSION_DURATION_THRESHOLD should be used
@pony_utils.db_session
def perform_queries(db, entity_class):
    for i in range(10):
        entity_class(a=i)
    db.commit()
    db.rollback()
    entity_class.select().fetch()


def test_patched_db_session_default_duration_threshold(tmp_path):
    # The test checks that db_session uses the current dynamic value of SLOW_DB_SESSION_DURATION_THRESHOLD
    # if no duration_threshold was explicitly specified for db_session

    with patch('tribler.core.utilities.pony_utils.TriblerDbSession.track_slow_db_sessions', True):
        db = pony_utils.TriblerDatabase()
        db.bind(provider='sqlite', filename=str(tmp_path / 'db.sqlite'), create_db=True)

        class Entity1(db.Entity):
            a = Required(int)

        db.generate_mapping(create_tables=True)

        # We change the value of SLOW_DB_SESSION_DURATION_THRESHOLD, and the current value should be used by db_session
        with patch('tribler.core.utilities.pony_utils.SLOW_DB_SESSION_DURATION_THRESHOLD', 0.0):
            with patch.object(pony_utils.TriblerDbSession, '_format_warning',
                              return_value='<warning text>') as format_warning_mock:
                perform_queries(db, Entity1)

        format_warning_mock.assert_called()


def test_format_warning():
    warning = pony_utils.TriblerDbSession._format_warning(  # pylint: disable=protected-access
        db_session_duration=1.234, thread_name='ThreadName', formatted_stack='<Formatted Stack>',
        lock_wait_total_duration=0.1, lock_hold_total_duration=0.2,
        db_session_query_statistics='<Local Stat>', application_query_statistics='<Global Stat>'
    )
    assert warning == """Long db_session detected.
Session info:
    Thread: 'ThreadName'
    db_session duration: 1.234 seconds
    db_session waited for the exclusive lock for 0.100 seconds
    db_session held exclusive lock for 0.200 seconds
The db_session stack:
<Formatted Stack>

Queries statistics for the current db_session:
<Local Stat>

Queries statistics for the entire application:
<Global Stat>
"""


@pytest.fixture(name='db_path')
def db_path_fixture(tmp_path: Path):
    db_path = tmp_path / 'test.db'
    db_path.touch()
    return db_path


@patch('tribler.core.utilities.pony_utils._handle_corrupted_db')
def test_handle_db_if_corrupted__not_corrupted(handle_corrupted_db: Mock, db_path: Path):
    # If the corruption marker is not found, the handling of the database is not performed
    handle_db_if_corrupted(db_path)
    handle_corrupted_db.assert_not_called()


def test_handle_db_if_corrupted__corrupted(db_path: Path):
    # If the corruption marker is found, the corrupted database file is removed
    marker_path = Path(str(db_path) + '.is_corrupted')
    marker_path.touch()

    handle_db_if_corrupted(db_path)
    assert not db_path.exists()
    assert not marker_path.exists()


def test_marking_corrupted_db__not_malformed(db_path: Path):
    # When the context manger encounters an exception not related to database corruption, it does nothing
    with pytest.raises(ZeroDivisionError):
        with marking_corrupted_db(db_path):
            raise ZeroDivisionError()

    assert not Path(str(db_path) + '.is_corrupted').exists()


def test_marking_corrupted_db__malformed(db_path: Path):
    # When the context manger encounters an exception not related to database corruption, it adds a corruption marker
    with pytest.raises(DatabaseIsCorrupted):
        with marking_corrupted_db(db_path):
            raise sqlite3.DatabaseError('database disk image is malformed')

    assert Path(str(db_path) + '.is_corrupted').exists()


def test_get_db_version__db_does_not_exist(tmp_path: Path):
    # When the database does not exist, the call to get_db_version generates RuntimeError
    db_path = tmp_path / 'doesnotexist.db'

    with pytest.raises(RuntimeError, match='^The version value is not found in database .*doesnotexist.db$'):
        get_db_version(db_path)


def test_get_db_version__db_does_not_exist_default_version(tmp_path: Path):
    # When the database does not exist, and the default is specified, get_db_version returns the default value
    db_path = tmp_path / 'doesnotexist.db'

    default_version = 123
    version = get_db_version(db_path, default=default_version)
    assert version == default_version


def test_get_db_version__version_table_does_not_exist(db_path: Path):
    # When the version table does not exist, the call to get_db_version generates RuntimeError
    with pytest.raises(RuntimeError, match='^The version value is not found in database .*test.db$'):
        get_db_version(db_path)


def test_get_db_version__version_table_does_not_exist_default_version(db_path: Path):
    # When the version table does not exist, and the default is specified, get_db_version returns the default value
    default_version = 123
    version = get_db_version(db_path, default=default_version)
    assert version == default_version


def test_get_db_version(db_path: Path):
    # Tests that if the database schema version is specified in the database, the default value is completely ignored.

    with sqlite3.connect(db_path) as connection:
        connection.execute('create table MiscData(name text primary key, value text)')
        connection.execute("insert into MiscData(name, value) values('db_version', '100')")

    version = get_db_version(db_path)
    assert version == 100

    version = get_db_version(db_path, default=99)
    assert version == 100

    version = get_db_version(db_path, default=101)
    assert version == 100


def test_get_db_version__corrupted_db(tmp_path: Path):
    # Tests that if the database file is marked as corrupted, then the version from the db is ignored,
    # and default version is used after the database file is re-created.

    db_path = tmp_path / 'test.db'

    connection = sqlite3.connect(db_path)
    connection.execute('create table MiscData(name text primary key, value text)')
    connection.execute("insert into MiscData(name, value) values('db_version', '100')")
    connection.commit()
    assert table_exists(connection.cursor(), 'MiscData')
    connection.close()

    marker_path = Path(str(db_path) + '.is_corrupted')
    marker_path.touch()

    default_version = 10
    version = get_db_version(db_path, default=default_version)
    assert version == default_version

    with sqlite3.connect(db_path) as connection:
        assert not table_exists(connection.cursor(), 'MiscData')


def test_mark_db_as_corrupted_file_does_not_exist(tmp_path: Path):
    # The database file apparently was corrupted, and `_mark_db_as_corrupted(db_path)` is called to mark it as such.
    # But the function was not able to find the database file at the specified path. In this unnormal situation,
    # it raises an exception.

    db_path = tmp_path / 'doesnotexist.db'
    with pytest.raises(RuntimeError, match='^Corrupted database file not found: .*doesnotexist.db$'):
        _mark_db_as_corrupted(db_path)
