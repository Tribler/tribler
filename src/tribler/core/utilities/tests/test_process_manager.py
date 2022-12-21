import os
import re
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

from tribler.core.utilities.process_manager import logger, TriblerProcess, ProcessKind, ProcessManager, \
    get_global_process_manager, set_api_port, set_error, set_global_process_manager


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path):
    return ProcessManager(tmp_path, ProcessKind.Core)


def test_tribler_process():
    p = TriblerProcess.current_process(ProcessKind.Core, 123, arbitrary_param=456)
    assert p.is_current_process()
    assert p.is_running()

    s = p.describe()
    pattern = r"^CoreProcess\(pid=\d+, gui_pid=123, version='[^']+', started='\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'\)$"
    assert re.match(pattern, s)


@patch('psutil.Process')
@patch('psutil.pid_exists')
def test_tribler_process_is_running(pid_exists: Mock, process_class):
    p = TriblerProcess.current_process(ProcessKind.GUI)
    assert not pid_exists.called

    # if the pid does not exist, the process is not running
    pid_exists.return_value = False
    assert p.is_running() is False
    assert pid_exists.called

    # if the instantiation of the Process instance lead to psutil.Error, the process is not running
    pid_exists.return_value = True
    process_class.side_effect = psutil.Error
    assert p.is_running() is False
    assert process_class.called

    # if the process is zombie, it is not considered to be running
    process = Mock()
    process.status.return_value = psutil.STATUS_ZOMBIE
    process_class.side_effect = None
    process_class.return_value = process
    assert p.is_running() is False

    # if the process with the specified pid was created after the specified time, it is a different process
    process.status.return_value = psutil.STATUS_RUNNING
    process.create_time.return_value = p.started_at + 1
    assert p.is_running() is False

    # if the process exists, it is not a zombie, and its creation time matches the recorded value, it is running
    process.create_time.return_value = p.started_at
    assert p.is_running() is True


def test_tribler_process_set_error():
    p = TriblerProcess.current_process(ProcessKind.GUI)

    # Initially there is no exception
    assert p.error_msg is None and p.error_info is None

    # In simplest case, just specify an
    p.set_error('Error text 1')

    assert p.error_msg == 'Error text 1' and p.error_info is None
    # By default, the second exception does not override the first one (as the first exception may be the root case)

    p.set_error('Error text 2')
    assert p.error_msg == 'Error text 1' and p.error_info is None

    # But it is possible to override exception explicitly
    p.set_error('Error text 2', replace=True)
    assert p.error_msg == 'Error text 2' and p.error_info is None

    # It is possible to specify an additional dict with arbitrary JSON-serializable information about the error
    p.set_error('Error text 3', error_info={'error3_param': 'error3_value'}, replace=True)
    assert p.error_msg == 'Error text 3' and p.error_info == {'error3_param': 'error3_value'}

    # If the error is replaced, then the entire error_info dict is replaced as well, the dicts are not mixed together
    p.set_error('Error text 4', error_info={'error4_param': 'error4_value'}, replace=True)
    assert p.error_msg == 'Error text 4' and p.error_info == {'error4_param': 'error4_value'}

    # If error_info is not specified, the previous error_info is still replaced
    p.set_error('Error text 5', replace=True)
    assert p.error_msg == 'Error text 5' and p.error_info is None

    # It is possible to specify an exception
    p.set_error(exc=ValueError('exception text'), error_info={'some_param': 'some_value'}, replace=True)
    assert p.error_msg == 'ValueError: exception text' and p.error_info == {'some_param': 'some_value'}

    # The error text is included in ProcessInfo.describe() output
    s = p.describe()
    pattern = r"^GuiProcess\(pid=\d+, version='[^']+', started='[^']+', error='ValueError: exception text'\)$"
    assert re.match(pattern, s)


def test_tribler_process_mark_finished():
    def make_tribler_process():
        p = TriblerProcess.current_process(ProcessKind.Core)
        p.primary = 1
        p.api_port = 10000
        return p

    p = make_tribler_process()
    assert p.exit_code is None
    assert p.finished_at is None

    p.mark_finished(123)
    assert p.primary == 0
    assert p.exit_code == 123
    assert p.finished_at is not None

    s = p.describe()
    assert s.endswith(", api_port=10000, duration='0:00:00', exit_code=123)")

    p = make_tribler_process()
    p.mark_finished()  # the error is not set and the exit code is not specified, and by default should be 0
    assert p.exit_code == 0

    p = make_tribler_process()
    p.error_msg = 'Error text'
    p.mark_finished()  # the error is set and the exit code is not specified, and by default should be 1
    assert p.exit_code == 1


@patch.object(logger, 'error')
def test_tribler_process_save(logger_error: Mock):
    p = TriblerProcess.current_process(ProcessKind.Core)
    assert p.rowid is None and p.row_version == 0

    cursor = Mock(lastrowid=123)
    connection = Mock()
    connection.cursor.return_value = cursor

    p.save(connection)
    assert "INSERT INTO" in cursor.execute.call_args[0][0]
    assert p.rowid == 123 and p.row_version == 0

    cursor.rowcount = 1
    p.save(connection)
    assert "UPDATE" in cursor.execute.call_args[0][0]
    assert p.rowid == 123 and p.row_version == 1

    assert not logger_error.called
    cursor.rowcount = 0
    p.save(connection)
    assert logger_error.called
    assert logger_error.call_args[0][0] == 'Row 123 with row version 1 was not found'

    p = TriblerProcess.current_process(ProcessKind.Core)
    p.row_version = 1
    p.save(connection)
    assert logger_error.call_args[0][0] == 'The `row_version` value for a new process row should not be set. Got: 1'


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

    set_api_port(12345)
    assert warning.call_args[0][0] == 'Cannot set api_port for process locker: no process locker global instance is set'

    set_error('Error text')
    assert warning.call_args[0][0] == 'Cannot set error for process locker: no process locker global instance is set'

    set_global_process_manager(process_manager)
    assert get_global_process_manager() is process_manager

    set_api_port(12345)
    set_error('Error text')

    assert process_manager.current_process.api_port == 12345
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
