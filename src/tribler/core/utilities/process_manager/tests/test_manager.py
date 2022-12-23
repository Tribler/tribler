from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess
from tribler.core.utilities.process_manager.manager import logger, ProcessManager, \
    get_global_process_manager, set_error, set_global_process_manager


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path):
    return ProcessManager(tmp_path, ProcessKind.Core)


def test_connect(process_manager):
    process_manager.filename = ':memory:'
    process_manager.connect()
    connection = process_manager.connect()
    cursor = connection.execute('select * from processes')
    column_names = [column[0] for column in cursor.description]
    assert column_names == ['rowid', 'row_version', 'pid', 'kind', 'primary', 'canceled', 'app_version',
                            'started_at', 'creator_pid', 'api_port', 'shutdown_request_pid', 'shutdown_requested_at',
                            'finished_at', 'exit_code', 'error_msg', 'error_info', 'other_params']

    with patch('sqlite3.connect') as connect:
        connection = Mock()
        connect.return_value = connection
        connection.execute.side_effect = ValueError
        with pytest.raises(ValueError):
            process_manager.connect()
        assert connection.close.called


def test_atomic_get_primary_process(process_manager: ProcessManager):
    assert process_manager.current_process.primary == 1
    assert process_manager.primary_process is process_manager.current_process

    fake_process = TriblerProcess.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    primary_process = process_manager.atomic_get_primary_process(ProcessKind.Core, fake_process)
    assert primary_process.primary == 1
    assert fake_process.primary == 0

    with process_manager.transaction() as connection:
        connection.execute('update processes set pid = pid + 100')

    current_process = TriblerProcess.current_process(ProcessKind.Core)
    primary_process = process_manager.atomic_get_primary_process(ProcessKind.Core, current_process)
    assert current_process.primary
    assert primary_process is current_process

    with process_manager.transaction() as connection:
        rows = connection.execute('select rowid from processes where "primary" = 1').fetchall()
        assert len(rows) == 1 and rows[0][0] == current_process.rowid


def test_save(process_manager: ProcessManager):
    p = TriblerProcess.current_process(ProcessKind.Core)
    p.pid = p.pid + 100
    process_manager.save(p)
    assert p.rowid is not None


def test_set_api_port(process_manager: ProcessManager):
    process_manager.set_api_port(12345)
    assert process_manager.current_process.api_port == 12345
    with process_manager.transaction() as connection:
        rows = connection.execute('select rowid from processes where api_port = 12345').fetchall()
        assert len(rows) == 1 and rows[0][0] == process_manager.current_process.rowid


@patch('sys.exit')
def test_sys_exit(sys_exit: Mock, process_manager: ProcessManager):
    process_manager.sys_exit(123, 'Error text')

    with process_manager.transaction() as connection:
        rows = connection.execute('select "primary", error_msg from processes where rowid = ?',
                                  [process_manager.current_process.rowid]).fetchall()
        assert len(rows) == 1 and rows[0] == (0, 'Error text')
    assert sys_exit.called and sys_exit.call_args[0][0] == 123


def test_get_last_processes(process_manager: ProcessManager):
    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 1 and last_processes[0].rowid == process_manager.current_process.rowid

    fake_process = TriblerProcess.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    process_manager.atomic_get_primary_process(ProcessKind.Core, fake_process)

    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 2
    assert last_processes[0].rowid == process_manager.current_process.rowid
    assert last_processes[1].rowid == fake_process.rowid


@patch.object(logger, 'warning')
def test_global_process_manager(warning: Mock, process_manager: ProcessManager):
    assert get_global_process_manager() is None

    set_error('Error text')
    assert warning.call_args[0][0] == 'Cannot set error for process locker: no process locker global instance is set'

    set_global_process_manager(process_manager)
    assert get_global_process_manager() is process_manager

    set_error('Error text')
    assert process_manager.current_process.error_msg == 'Error text'

    set_global_process_manager(None)
    assert get_global_process_manager() is None


def test_json_fields(process_manager: ProcessManager):
    p = process_manager.current_process
    p.set_error('Error text', {'arbitrary_key': 'arbitrary_value'})
    p.other_params = {'some_key': 'some_value'}
    process_manager.save(p)  # should serialize `error_info` and `other_params` to JSON
    processes = process_manager.get_last_processes()
    assert len(processes) == 1
    p2 = processes[0]
    assert p is not p2  # p2 is a new instance constructed from the database row
    assert processes[0].error_info == {'arbitrary_key': 'arbitrary_value'}  # parsed from the database
    assert processes[0].other_params == {'some_key': 'some_value'}


@patch.object(logger, 'warning')
@patch.object(logger, 'exception')
def test_corrupted_database(logger_exception: Mock, logger_warning: Mock, process_manager: ProcessManager):
    db_content = process_manager.filename.read_bytes()
    assert len(db_content) > 2000
    process_manager.filename.write_bytes(db_content[:1500])  # corrupt the database file

    # no exception, the database is silently re-created:
    process_manager2 = ProcessManager(process_manager.root_dir, ProcessKind.Core)
    assert logger_exception.call_args[0][0] == 'DatabaseError: database disk image is malformed'
    assert logger_warning.call_args[0][0] == 'Retrying after the error: DatabaseError: database disk image is malformed'

    processes = process_manager2.get_last_processes()
    assert len(processes) == 1
