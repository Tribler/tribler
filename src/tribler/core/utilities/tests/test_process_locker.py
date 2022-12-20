import os
import re
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

from tribler.core.utilities.process_locker import logger, ProcessInfo, ProcessKind, ProcessLocker, \
    get_global_process_locker, set_api_port, set_error, set_global_process_locker


@pytest.fixture(name='process_locker')
def process_locker_fixture(tmp_path: Path):
    return ProcessLocker(tmp_path, ProcessKind.Core)


def test_process_info():
    p = ProcessInfo.current_process(ProcessKind.Core, 123, arbitrary_param=456)
    assert p.is_current_process()
    assert p.is_running()

    d = p.to_dict()
    d2 = {'active': 0, 'canceled': 0, 'kind': 'core', 'pid': os.getpid(), 'creator_pid': 123,
          'other_params': {'arbitrary_param': 456}}
    assert d2.items() <= d.items()
    assert 'app_version' in d and 'started_at' in d

    s = p.describe()
    pattern = r"^CoreProcess\(pid=\d+, gui_pid=123, version='[^']+', started='\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'\)$"
    assert re.match(pattern, s)


@patch('psutil.Process')
@patch('psutil.pid_exists')
def test_process_info_is_running(pid_exists: Mock, process_class):
    p = ProcessInfo.current_process(ProcessKind.GUI)
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


def test_process_info_set_error():
    p = ProcessInfo.current_process(ProcessKind.GUI)

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


def test_process_info_mark_finished():
    def make_process_info():
        p = ProcessInfo.current_process(ProcessKind.Core)
        p.active = 1
        p.api_port = 10000
        return p

    p = make_process_info()
    assert p.exit_code is None
    assert p.finished_at is None

    p.mark_finished(123)
    assert p.active == 0
    assert p.exit_code == 123
    assert p.finished_at is not None

    s = p.describe()
    assert s.endswith(", api_port=10000, duration='0:00:00', exit_code=123)")

    p = make_process_info()
    p.mark_finished()  # the error is not set and the exit code is not specified, and by default should be 0
    assert p.exit_code == 0

    p = make_process_info()
    p.error_msg = 'Error text'
    p.mark_finished()  # the error is set and the exit code is not specified, and by default should be 1
    assert p.exit_code == 1


@patch.object(logger, 'error')
def test_process_info_save(logger_error: Mock):
    p = ProcessInfo.current_process(ProcessKind.Core)
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

    p = ProcessInfo.current_process(ProcessKind.Core)
    p.row_version = 1
    p.save(connection)
    assert logger_error.call_args[0][0] == 'The `row_version` value for a new process row should not be set. Got: 1'


def test_connect(process_locker):
    process_locker.filename = ':memory:'
    process_locker.connect()
    connection = process_locker.connect()
    cursor = connection.execute('select * from processes')
    column_names = [column[0] for column in cursor.description]
    assert column_names == ['rowid', 'row_version', 'pid', 'kind', 'active', 'canceled', 'app_version',
                            'started_at', 'creator_pid', 'api_port', 'shutdown_request_pid', 'shutdown_requested_at',
                            'finished_at', 'exit_code', 'error_msg', 'error_info', 'other_params']

    with patch('sqlite3.connect') as connect:
        connection = Mock()
        connect.return_value = connection
        connection.execute.side_effect = ValueError
        with pytest.raises(ValueError):
            process_locker.connect()
        assert connection.close.called


def test_atomic_get_active_process(process_locker: ProcessLocker):
    assert process_locker.current_process.active == 1
    assert process_locker.active_process is process_locker.current_process

    fake_process = ProcessInfo.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    active_process = process_locker.atomic_get_active_process(ProcessKind.Core, fake_process)
    assert active_process.active == 1
    assert fake_process.active == 0

    with process_locker.transaction() as connection:
        connection.execute('update processes set pid = pid + 100')

    current_process = ProcessInfo.current_process(ProcessKind.Core)
    active_process = process_locker.atomic_get_active_process(ProcessKind.Core, current_process)
    assert current_process.active
    assert active_process is current_process

    with process_locker.transaction() as connection:
        rows = connection.execute('select rowid from processes where active = 1').fetchall()
        assert len(rows) == 1 and rows[0][0] == current_process.rowid


def test_save(process_locker: ProcessLocker):
    p = ProcessInfo.current_process(ProcessKind.Core)
    p.pid = p.pid + 100
    process_locker.save(p)
    assert p.rowid is not None


def test_set_api_port(process_locker: ProcessLocker):
    process_locker.set_api_port(12345)
    with process_locker.transaction() as connection:
        rows = connection.execute('select rowid from processes where api_port = 12345').fetchall()
        assert len(rows) == 1 and rows[0][0] == process_locker.current_process.rowid


@patch('sys.exit')
def test_sys_exit(sys_exit: Mock, process_locker: ProcessLocker):
    process_locker.sys_exit(123, 'Error text')

    with process_locker.transaction() as connection:
        rows = connection.execute('select active, error_msg from processes where rowid = ?',
                                  [process_locker.current_process.rowid]).fetchall()
        assert len(rows) == 1 and rows[0] == (0, 'Error text')
    assert sys_exit.called and sys_exit.call_args[0][0] == 123


def test_get_last_processes(process_locker: ProcessLocker):
    last_processes = process_locker.get_last_processes()
    assert len(last_processes) == 1 and last_processes[0].rowid == process_locker.current_process.rowid

    fake_process = ProcessInfo.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    process_locker.atomic_get_active_process(ProcessKind.Core, fake_process)

    last_processes = process_locker.get_last_processes()
    assert len(last_processes) == 2
    assert last_processes[0].rowid == process_locker.current_process.rowid
    assert last_processes[1].rowid == fake_process.rowid


@patch.object(logger, 'warning')
def test_global_process_locker(warning: Mock, process_locker: ProcessLocker):
    assert get_global_process_locker() is None

    set_api_port(12345)
    assert warning.call_args[0][0] == 'Cannot set api_port for process locker: no process locker global instance is set'

    set_error('Error text')
    assert warning.call_args[0][0] == 'Cannot set error for process locker: no process locker global instance is set'

    set_global_process_locker(process_locker)
    assert get_global_process_locker() is process_locker

    set_api_port(12345)
    set_error('Error text')

    assert process_locker.current_process.api_port == 12345
    assert process_locker.current_process.error_msg == 'Error text'

    set_global_process_locker(None)
    assert get_global_process_locker() is None


def test_json_fields(process_locker: ProcessLocker):
    p = process_locker.current_process
    p.set_error('Error text', {'arbitrary_key': 'arbitrary_value'})
    p.other_params = {'some_key': 'some_value'}
    process_locker.save(p)  # should serialize `error_info` and `other_params` to JSON
    processes = process_locker.get_last_processes()
    assert len(processes) == 1
    p2 = processes[0]
    assert p is not p2  # p2 is a new instance constructed from the database row
    assert processes[0].error_info == {'arbitrary_key': 'arbitrary_value'}  # parsed from the database
    assert processes[0].other_params == {'some_key': 'some_value'}


@patch.object(logger, 'warning')
@patch.object(logger, 'exception')
def test_corrupted_database(logger_exception: Mock, logger_warning: Mock, process_locker: ProcessLocker):
    db_content = process_locker.filename.read_bytes()
    assert len(db_content) > 2000
    process_locker.filename.write_bytes(db_content[:1500])  # corrupt the database file

    # no exception, the database is silently re-created:
    process_locker2 = ProcessLocker(process_locker.root_dir, ProcessKind.Core)
    assert logger_exception.call_args[0][0] == 'DatabaseError: database disk image is malformed'
    assert logger_warning.call_args[0][0] == 'Retrying after the error: DatabaseError: database disk image is malformed'

    processes = process_locker2.get_last_processes()
    assert len(processes) == 1
