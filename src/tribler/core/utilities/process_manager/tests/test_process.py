import re
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

from tribler.core.utilities.process_manager.manager import ProcessManager, logger
from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess


def test_tribler_process():
    p = TriblerProcess.current_process(ProcessKind.Core, 123, manager=Mock())
    assert p.is_current_process()
    assert p.is_running()

    pattern = r"^CoreProcess\(pid=\d+, gui_pid=123, version='[^']+', started='\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'\)$"
    assert re.match(pattern, str(p))


@pytest.fixture(name='manager')
def manager_fixture(tmp_path: Path) -> ProcessManager:
    current_process = TriblerProcess.current_process(ProcessKind.Core)
    process_manager = ProcessManager(tmp_path, current_process)
    process_manager.connection = Mock()
    return process_manager


@pytest.fixture(name='current_process')
def current_process_fixture(process_manager):
    process_manager.connection = Mock()
    return process_manager.current_process


@patch('psutil.pid_exists')
def test_is_running_pid_does_not_exists(pid_exists: Mock, current_process):
    pid_exists.return_value = False
    # if the pid does not exist, the process is not running
    assert not pid_exists.called
    assert current_process.is_running() is False
    assert pid_exists.called


@patch('psutil.Process')
def test_is_running_process_not_running(process_class: Mock, current_process):
    process_class.side_effect = psutil.Error
    # if the instantiation of the Process instance lead to psutil.Error, the process is not running
    assert current_process.is_running() is False
    assert process_class.called


@patch('psutil.Process')
def test_is_running_zombie_process(process_class: Mock, current_process):
    process_class.return_value.status.return_value = psutil.STATUS_ZOMBIE
    # if the process is zombie, it is not considered to be running
    assert current_process.is_running() is False


@patch('psutil.Process')
def test_is_running_incorrect_process_create_time(process_class: Mock, current_process):
    process = process_class.return_value
    process.status.return_value = psutil.STATUS_RUNNING
    process.create_time.return_value = current_process.started_at + 1
    # if the process with the specified pid was created after the specified time, it is a different process
    assert current_process.is_running() is False


@patch('psutil.Process')
def test_is_running(process_class: Mock, current_process):
    process = process_class.return_value
    process.status.return_value = psutil.STATUS_RUNNING
    process.create_time.return_value = current_process.started_at
    # if the process exists, it is not a zombie, and its creation time matches the recorded value, it is running
    assert current_process.is_running() is True


def test_tribler_process_set_error(current_process):
    assert current_process.error_msg is None

    current_process.set_error('Error text 1')
    assert current_process.error_msg == 'Error text 1'

    current_process.set_error('Error text 2')
    # By default, the second exception does not override the first one (as the first exception may be the root case)
    assert current_process.error_msg == 'Error text 1'

    # But it is possible to override exception explicitly
    current_process.set_error('Error text 2', replace=True)
    assert current_process.error_msg == 'Error text 2'

    # It is also possible to specify an exception
    current_process.set_error(ValueError('exception text'), replace=True)
    assert current_process.error_msg == 'ValueError: exception text'

    # The error text is included in ProcessInfo.__str__() output
    pattern = r"^CoreProcess\(primary, pid=\d+, version='[^']+', started='[^']+', error='ValueError: exception text'\)$"
    assert re.match(pattern, str(current_process))


def test_tribler_process_mark_finished(current_process):
    p = current_process  # for brevity
    assert p.exit_code is None
    assert p.finished_at is None
    p.primary = True
    p.api_port = 10000
    p.finish(123)
    assert not p.primary
    assert p.exit_code == 123
    assert p.finished_at is not None
    assert str(p).endswith(", api_port=10000, duration='0:00:00', exit_code=123)")


def test_tribler_process_mark_finished_no_exit_code(current_process):
    current_process.finish()  # the error is not set and the exit code is not specified, and by default should be 0
    assert current_process.exit_code == 0


def test_tribler_process_mark_finished_error_text(current_process):
    current_process.error_msg = 'Error text'
    current_process.finish()  # the error is set and the exit code is not specified, and by default should be 1
    assert current_process.exit_code == 1


@patch.object(logger, 'error')
def test_tribler_process_save(logger_error: Mock, current_process):
    p = current_process  # for brevity

    cursor = p.manager.connection.cursor.return_value
    cursor.lastrowid = 123

    p.rowid = None
    p.save()
    assert "INSERT INTO" in cursor.execute.call_args[0][0]
    assert p.rowid == 123 and p.row_version == 0

    cursor.rowcount = 1
    p.save()
    assert "UPDATE" in cursor.execute.call_args[0][0]
    assert p.rowid == 123 and p.row_version == 1

    assert not logger_error.called
    cursor.rowcount = 0
    p.save()
    assert logger_error.called
    assert logger_error.call_args[0][0] == 'Row 123 with row version 1 was not found'
