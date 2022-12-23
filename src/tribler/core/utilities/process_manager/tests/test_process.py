import re
from unittest.mock import Mock, patch

import psutil

from tribler.core.utilities.process_manager.process import logger, ProcessKind, TriblerProcess


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
