import sqlite3
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from tribler.core.utilities.process_manager.manager import DB_FILENAME, ProcessManager, logger
from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess


# pylint: disable=protected-access


def test_current_process_not_set(tmp_path):
    # This test verifies that the `current_process` property of the `ProcessManager` class raises a
    # RuntimeError when accessed before an actual process is set. This situation occurs immediately
    # after a new `ProcessManager` instance is created and before its initialization is finalized.
    # Once initialization is complete, `current_process` is guaranteed to be set, thus the property
    # is non-Optional to eliminate the need for redundant `None` checks. The test ensures the property
    # enforces this contract by throwing the expected exception when accessed prematurely.
    process_manager = ProcessManager(tmp_path)
    with pytest.raises(RuntimeError, match='^Current process is not set$'):
        process_manager.current_process  # pylint: disable=pointless-statement

    x = Mock()
    process_manager._current_process = x
    assert process_manager.current_process is x


def test_save(process_manager: ProcessManager):
    # Tests that saving a new process to the database correctly updates its `rowid` attribute.
    p = TriblerProcess.current_process(process_manager, ProcessKind.Core, owns_lock=False)
    p.pid = p.pid + 100
    assert p.rowid is None
    p.save()
    assert p.rowid is not None


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running')
def test_get_primary_process_1(is_running: MagicMock, tmp_path):
    # Test that `get_primary_process()` returns None when no processes are present in the database.
    pm = ProcessManager(tmp_path)

    # Validate that no primary processes are returned for both `ProcessKind` options in an empty database scenario.
    assert pm.get_primary_process(ProcessKind.Core) is None
    assert pm.get_primary_process(ProcessKind.GUI) is None

    # Ensure that the `TriblerProcess.is_running()` method was not called
    # since no primary process entries were found in the database.
    is_running.assert_not_called()


def _save_core_process(manager: ProcessManager, pid: int, primary: bool) -> TriblerProcess:
    process = TriblerProcess(manager=manager, kind=ProcessKind.Core, pid=pid, primary=primary, app_version='1',
                             started_at=int(time.time()) - 1)
    process.save()
    return process


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running')
def test_get_primary_process_2(is_running: MagicMock, tmp_path):
    # Verify `get_primary_process` returns None when the database only contains non-primary processes.
    pm = ProcessManager(tmp_path)

    # Populate the database with non-primary Core processes.
    _save_core_process(pm, pid=100, primary=False)
    _save_core_process(pm, pid=200, primary=False)

    # Assert no primary process is found for both Core and GUI process kinds.
    assert pm.get_primary_process(ProcessKind.Core) is None
    assert pm.get_primary_process(ProcessKind.GUI) is None

    # Confirm that `is_running` was not called due to the absence of primary process entries.
    is_running.assert_not_called()


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running', side_effect=[True])
def test_get_primary_process_3(is_running: MagicMock, tmp_path):
    # Test that `get_primary_process` correctly retrieves the primary process for a specified kind.
    pm = ProcessManager(tmp_path)

    # Set up the database with several non-primary and one primary Core processes.
    _save_core_process(pm, pid=100, primary=False)
    _save_core_process(pm, pid=200, primary=False)
    p3 = _save_core_process(pm, pid=300, primary=True)

    # Retrieve the primary Core process and assert that it matches the expected process.
    primary_process = pm.get_primary_process(ProcessKind.Core)
    assert primary_process and primary_process.pid == p3.pid

    # Confirm that `is_running` check was called for the process retrieved from the DB before returning it
    is_running.assert_called_once()

    # Verify no primary GUI process is retrieved when only primary process of a different kind is in the database.
    assert pm.get_primary_process(ProcessKind.GUI) is None


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running', side_effect=[False])
def test_get_primary_process_4(is_running: MagicMock, tmp_path):
    # Test that `get_primary_process` returns None when the process marked as primary in the DB is no longer running
    pm = ProcessManager(tmp_path)

    # Add a single primary Core process to the database for which process.is_running() returns False
    _save_core_process(pm, pid=100, primary=False)
    _save_core_process(pm, pid=200, primary=False)
    _save_core_process(pm, pid=300, primary=True)

    assert pm.get_primary_process(ProcessKind.Core) is None  # No primary processes should be returned from the DB
    # Checks that the previous primary process was successfully selected from the DB, but it is not running anymore
    is_running.assert_called()

    last_processes = pm.get_last_processes()
    assert len(last_processes) == 3

    # Verifies that the last call of `get_primary_process` update the state of the last process to make it non-primary
    assert last_processes[-1].pid == 300 and not last_processes[-1].primary


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running', side_effect=[True, True])
def test_get_primary_process_5(is_running: MagicMock, tmp_path):
    # Verifies that when two processes of the same kind are specified as primary in the database and actually running,
    # (an incorrect situation that should never happen), then one process should be returned from the
    # `get_primary_process` call and the error "Multiple primary processes found in the database" should be specified
    # for all such processes in the database.
    pm = ProcessManager(tmp_path)
    now = int(time.time())

    # Incorrect situation, two primary Core processes in the DB, one of them is returned
    p1 = TriblerProcess(manager=pm, kind=ProcessKind.Core, pid=100, primary=False, app_version='1', started_at=now-3)
    p2 = TriblerProcess(manager=pm, kind=ProcessKind.Core, pid=200, primary=True, app_version='1', started_at=now-2)
    p3 = TriblerProcess(manager=pm, kind=ProcessKind.Core, pid=300, primary=True, app_version='1', started_at=now-1)
    p1.save()
    p2.save()
    p3.save()

    p = pm.get_primary_process(ProcessKind.Core)
    assert p.pid == 200  # When multiple primary processes are found in the database, the first one is returned
    assert is_running.call_count == 2  # For all retrieved primary processes `is_running` check should be performed

    last_processes = pm.get_last_processes()
    assert len(last_processes) == 3

    msg = "Multiple primary processes found in the database"
    # Two last processes in the database should have the specified error message
    assert [p.error_msg for p in last_processes] == [None, msg, msg]


@patch('tribler.core.utilities.process_manager.process.TriblerProcess.is_running', return_value=True)
def test_setup_current_process(is_running: MagicMock, tmp_path):  # pylint: disable=unused-argument
    pm = ProcessManager(tmp_path)
    now = int(time.time())

    # Add a primary Core process to the database for which process.is_running() returns True
    p1 = TriblerProcess(manager=pm, kind=ProcessKind.Core, pid=100, primary=True, app_version='1', started_at=now-1)
    p1.save()

    with pytest.raises(RuntimeError, match="^Previous primary process still active: .* Current process: .*"):
        pm.setup_current_process(kind=ProcessKind.Core, owns_lock=True)


def test_set_api_port(process_manager: ProcessManager):
    process_manager.current_process.set_api_port(12345)
    assert process_manager.current_process.api_port == 12345
    with process_manager.connect() as connection:
        rows = connection.execute('select rowid from processes where api_port = 12345').fetchall()
        assert len(rows) == 1 and rows[0][0] == process_manager.current_process.rowid


@patch('sys.exit')
def test_sys_exit(sys_exit: Mock, process_manager: ProcessManager):
    process_manager.sys_exit(123, 'Error text')

    with process_manager.connect() as connection:
        rows = connection.execute('select "primary", error_msg from processes where rowid = ?',
                                  [process_manager.current_process.rowid]).fetchall()
        assert len(rows) == 1 and rows[0] == (0, 'Error text')
    assert sys_exit.called and sys_exit.call_args[0][0] == 123


def test_get_last_processes(process_manager: ProcessManager):
    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 1 and last_processes[0].rowid == process_manager.current_process.rowid

    fake_process = TriblerProcess.current_process(manager=process_manager, kind=ProcessKind.Core, owns_lock=False)
    fake_process.pid = fake_process.pid + 1
    fake_process.save()

    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 2
    assert last_processes[0].rowid == process_manager.current_process.rowid
    assert last_processes[1].rowid == fake_process.rowid


@patch.object(logger, 'warning')
@patch.object(logger, 'exception')
def test_corrupted_database(logger_exception: Mock, logger_warning: Mock, process_manager: ProcessManager):
    db_content = process_manager.db_filepath.read_bytes()
    assert len(db_content) > 2000
    process_manager.db_filepath.write_bytes(db_content[:1500])  # corrupt the database file

    # no exception, the database is silently re-created:
    process_manager2 = ProcessManager(process_manager.root_dir)
    process_manager2.setup_current_process(kind=ProcessKind.Core, owns_lock=False)

    assert logger_exception.call_args[0][0] == 'DatabaseError: database disk image is malformed'
    assert logger_warning.call_args[0][0] == 'Retrying after the error: DatabaseError: database disk image is malformed'

    processes = process_manager2.get_last_processes()
    assert len(processes) == 1


def test_delete_old_records_1(process_manager):
    # Let's check that records of processes finished more than 30 days ago are deleted from the database
    now = int(time.time())
    day = 60 * 60 * 24
    with process_manager.connect() as connection:
        # At that moment we have only the current process
        assert connection.execute("select count(*) from processes").fetchone()[0] == 1

        # Let's add 100 processes finished in previous days
        for i in range(1, 101):
            p = TriblerProcess(manager=process_manager, pid=i, kind=ProcessKind.Core, app_version='',
                               started_at=now - day * i - 60, finished_at=now - day * i + 60)
            p.save()
        assert connection.execute("select count(*) from processes").fetchone()[0] == 101

    with process_manager.connect() as connection:
        # Only the current primary process and processes finished during the last 30 days should remain
        assert connection.execute("select count(*) from processes").fetchone()[0] == 31


def test_delete_old_records_2(process_manager):
    # Let's check that at most 100 non-primary processes are kept in the database
    now = int(time.time())
    with process_manager.connect() as connection:
        # At that moment we have only the current process
        assert connection.execute("select count(*) from processes").fetchone()[0] == 1

        # Let's add 200 processes
        for i in range(200):
            p = TriblerProcess(manager=process_manager, pid=i, kind=ProcessKind.Core, app_version='',
                               started_at=now - 120)
            p.save()
        assert connection.execute("select count(*) from processes").fetchone()[0] == 201

    with process_manager.connect() as connection:
        # Only the current primary process and the last 100 processes should remain
        assert connection.execute("select count(*) from processes").fetchone()[0] == 101


def test_unable_to_open_db_file_get_reason_unknown_reason(process_manager):
    reason = process_manager._unable_to_open_db_file_get_reason()
    assert reason == 'unknown reason'


def test_unable_to_open_db_file_get_reason_unable_to_write(process_manager):
    class TestException(Exception):
        pass

    with patch('pathlib.Path.open', side_effect=TestException('exception text')):
        reason = process_manager._unable_to_open_db_file_get_reason()
        assert reason == 'TestException: exception text'


def test_unable_to_open_db_file_get_reason_no_write_permissions(process_manager):
    with patch('os.access', return_value=False):
        reason = process_manager._unable_to_open_db_file_get_reason()
        assert reason.startswith('the process does not have write permissions to the directory')


def test_unable_to_open_db_file_get_reason_directory_does_not_exist(process_manager):
    process_manager.root_dir /= 'non_existent_subdir'
    process_manager.db_filepath = process_manager.root_dir / DB_FILENAME
    reason = process_manager._unable_to_open_db_file_get_reason()
    assert reason.startswith('parent directory') and reason.endswith('does not exist')


def test_unable_to_open_db_file_reason_added(process_manager):
    process_manager.root_dir /= 'non_existent_subdir'
    process_manager.db_filepath = process_manager.root_dir / DB_FILENAME
    with pytest.raises(sqlite3.OperationalError,
                       match=r'^unable to open database file: parent directory.*does not exist$'):
        with process_manager.connect():
            pass
