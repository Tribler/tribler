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

    pattern = r"^CoreProcess\(running, current process, pid=\d+, gui_pid=123, version='[^']+', " \
              r"started='\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'\, duration='\d:\d{2}:\d{2}'\)$"
    assert re.match(pattern, str(p))

    p.canceled = True
    p.api_port = 123
    p.exit_code = 1

    pattern = r"^CoreProcess\(finished, current process, canceled, pid=\d+, gui_pid=123, version='[^']+', " \
              r"started='\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'\, api_port=123, duration='\d:\d{2}:\d{2}', " \
              r"exit_code=1\)$"
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
    pattern = r"^CoreProcess\(running, current process, primary, pid=\d+, version='[^']+', " \
              r"started='[^']+', duration='\d:\d{2}:\d{2}', error='ValueError: exception text'\)$"
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
    assert p.rowid == 123
    assert p.row_version == 0

    cursor.rowcount = 1
    p.save()
    assert "UPDATE" in cursor.execute.call_args[0][0]
    assert p.rowid == 123
    assert p.row_version == 1

    assert not logger_error.called
    cursor.rowcount = 0
    p.save()
    assert logger_error.called
    assert logger_error.call_args[0][0] == 'Row 123 with row version 1 was not found'


@pytest.fixture(name='gui_process')
def gui_process_fixture(process_manager):
    gui_process = TriblerProcess(pid=1, kind=ProcessKind.GUI, app_version='v1', started_at=1, manager=process_manager)
    gui_process.save()
    return gui_process


def test_get_core_process_no_core_process_found(gui_process):
    assert gui_process.get_core_process() is None  # no associated core processes were found


def test_get_core_process_non_primary(gui_process):
    core_process = TriblerProcess(pid=2, kind=ProcessKind.Core, app_version='v1', started_at=1, creator_pid=1,
                                  manager=gui_process.manager)
    core_process.save()
    assert gui_process.get_core_process() is None  # core process should be primary to be selected


def test_get_core_process(gui_process):
    core_process = TriblerProcess(pid=2, kind=ProcessKind.Core, app_version='v1', started_at=1, creator_pid=1,
                                  manager=gui_process.manager)
    core_process.primary = True
    core_process.save()
    p = gui_process.get_core_process()
    assert p is not None  # the core process was found for this GUI process
    assert p is not core_process  # it is a new object retrieved from the database, not the one created initially
    assert p.pid == core_process.pid  # it has the correct pid value
    assert p.api_port is None  # the api port is not specified yet

    core_process.set_api_port(123)
    p2 = gui_process.get_core_process()
    assert p2 is not None  # the core process was found for this GUI process
    assert p2 is not core_process
    assert p2 is not p
    assert p2.api_port == 123  # it has correct API port value

    # Second Core process for the same GUI process should lead to an error
    p3 = TriblerProcess(pid=3, kind=ProcessKind.Core, app_version='v1', started_at=1, creator_pid=1, primary=True,
                        manager=gui_process.manager)
    p3.save()
    with pytest.raises(RuntimeError, match='^Multiple Core processes were found for a single GUI process$'):
        gui_process.get_core_process()


def test_get_core_process_exception(process_manager):
    # in the process_manager fixture the current_process is a Core process
    with pytest.raises(TypeError, match='^The `get_core_process` method can only be used for a GUI process$'):
        process_manager.current_process.get_core_process()
