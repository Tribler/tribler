import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from tribler.core.utilities.exit_codes.tribler_exit_codes import EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING
from tribler.gui.core_manager import CoreCrashedError, CoreManager
from tribler.gui.exceptions import CoreConnectTimeoutError


@pytest.fixture(name='core_manager')
def fixture_core_manager():
    core_manager = CoreManager(root_state_dir=MagicMock(), api_port=MagicMock(), api_key=MagicMock(),
                               app_manager=MagicMock(), process_manager=MagicMock(), events_manager=MagicMock())
    core_manager.core_process = MagicMock(readAllStandardOutput=MagicMock(return_value=b'core stdout'),
                                          readAllStandardError=MagicMock(return_value=b'core stderr'))
    core_manager.check_core_api_port_timer = MagicMock()
    return core_manager


def test_on_core_started_calls_check_core_api_port(core_manager):
    assert not core_manager.core_running
    assert not core_manager.core_started
    assert core_manager.core_process_started_at is None
    with patch.object(core_manager, 'check_core_api_port') as check_core_api_port:
        core_manager.on_core_started()
        assert check_core_api_port.called


def test_check_core_api_port_not_running(core_manager):
    assert not core_manager.core_running
    core_manager.check_core_api_port()
    assert not core_manager.process_manager.current_process.get_core_process.called


def test_check_core_api_port_already_connected(core_manager):
    core_manager.core_running = True
    core_manager.core_connected = True
    core_manager.check_core_api_port()
    assert not core_manager.process_manager.current_process.get_core_process.called


def test_check_core_api_port_shutting_down(core_manager):
    core_manager.core_running = True
    core_manager.shutting_down = True
    core_manager.check_core_api_port()
    assert not core_manager.process_manager.current_process.get_core_process.called


def test_check_core_api_port_core_process_not_found(core_manager):
    core_manager.core_running = True
    core_manager.core_process_started_at = time.time()
    core_manager.process_manager.current_process.get_core_process.return_value = None
    core_manager.process_manager.get_primary_process.return_value = None
    core_manager.check_core_api_port()
    assert core_manager.process_manager.current_process.get_core_process.called
    assert core_manager.check_core_api_port_timer.start.called


def test_check_core_api_port_not_set(core_manager):
    core_manager.core_running = True
    core_manager.core_process_started_at = time.time()
    core_manager.process_manager.current_process.get_core_process().api_port = None
    core_manager.check_core_api_port()
    assert core_manager.process_manager.current_process.get_core_process.called
    assert core_manager.check_core_api_port_timer.start.called


@patch('tribler.gui.core_manager.request_manager')
def test_check_core_api_port(request_manager: MagicMock, core_manager: CoreManager):
    core_manager.core_running = True
    core_manager.core_process_started_at = time.time()
    api_port = core_manager.process_manager.current_process.get_core_process().api_port
    core_manager.check_core_api_port()
    assert core_manager.process_manager.current_process.get_core_process.called
    assert not core_manager.check_core_api_port_timer.start.called
    assert core_manager.api_port == api_port
    assert request_manager.set_api_port.called_once_with(api_port)


def test_check_core_api_port_timeout(core_manager):
    core_manager.core_running = True
    # The timeout should be 30 seconds so let's pretend the core started 31 seconds before now
    core_manager.core_process_started_at = time.time() - 121
    core_manager.process_manager.current_process.get_core_process.return_value = None
    core_manager.process_manager.get_primary_process.return_value = None
    with pytest.raises(CoreConnectTimeoutError, match="^Can't get Core API port value within 120 seconds$"):
        core_manager.check_core_api_port()


def test_on_core_finished_calls_quit_application(core_manager):
    # test that in case of `shutting_down` and `should_quit_app_on_core_finished` flags have been set to True
    # then `quit_application` method will be called and Exception will not be raised
    core_manager.shutting_down = True
    core_manager.should_quit_app_on_core_finished = True
    core_manager.on_core_finished(exit_code=1, exit_status='exit status')
    core_manager.app_manager.quit_application.assert_called_once()


def test_on_core_finished_raises_error(core_manager):
    # test that in case of flag `shutting_down` has been set to True and
    # exit_code is not equal to 0, then CoreRuntimeError should be raised
    with pytest.raises(CoreCrashedError):
        core_manager.on_core_finished(exit_code=1, exit_status='exit status')


def test_on_core_finished_with_existing_core_error(core_manager):
    # test that in case the core exited with existing core running error,
    # Core manager tries to connect to existing running core instead
    # of crashing with CoreCrashedError.
    core_manager.check_core_api_port = MagicMock()

    core_manager.on_core_finished(exit_code=EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING,
                                  exit_status='exit status')

    assert core_manager.use_existing_core
    assert core_manager.check_core_api_port.calle


@patch('builtins.print')
def test_on_core_stdout_read_ready(mocked_print, core_manager):
    # test that method `on_core_stdout_read_ready` converts byte output to a string and prints it
    core_manager.app_manager.quitting_app = False
    core_manager.on_core_stdout_read_ready()
    mocked_print.assert_called_with('core stdout')


@patch('builtins.print')
def test_on_core_stderr_read_ready(mocked_print, core_manager):
    # test that method `on_core_stdout_read_ready` converts byte output to a string and prints it
    core_manager.app_manager.quitting_app = False
    core_manager.on_core_stderr_read_ready()
    mocked_print.assert_called_with('core stderr', file=sys.stderr)


@patch('builtins.print', new_callable=MagicMock, side_effect=OSError())
def test_on_core_read_ready_os_error_suppressed(mocked_print: MagicMock, core_manager):
    # OSError exceptions when writing to stdout and stderr are suppressed
    core_manager.app_manager.quitting_app = False
    core_manager.on_core_stdout_read_ready()
    core_manager.on_core_stderr_read_ready()
    assert mocked_print.call_count == 2

    # if app is quitting, core_manager does not write to stdout/stderr at all, and so the call counter does not grow
    core_manager.app_manager.quitting_app = True
    core_manager.on_core_stdout_read_ready()
    core_manager.on_core_stderr_read_ready()
    assert mocked_print.call_count == 2


def test_decode_raw_core_output(core_manager):
    assert core_manager.decode_raw_core_output(b'test') == 'test'
    assert core_manager.decode_raw_core_output('test привет'.encode('utf-8')) == 'test привет'
    assert core_manager.decode_raw_core_output('test привет'.encode('cp1251')) == r'test \xef\xf0\xe8\xe2\xe5\xf2'


def test_format_error_message():
    actual = CoreManager.format_error_message(exit_code=99, exit_status=1)
    expected = '''The Tribler core has unexpectedly finished with exit code 99 (0x63) and status: 1.

Error message: EXITCODE_DATABASE_IS_CORRUPTED'''

    assert actual == expected


@patch('tribler.core.utilities.exit_codes.check_win_errors', True)
def test_format_error_message_windows():
    actual = CoreManager.format_error_message(exit_code=-1073741819, exit_status=1)
    expected = '''The Tribler core has unexpectedly finished with exit code -1073741819 (0xc0000005) and status: 1.

Error message: STATUS_ACCESS_VIOLATION'''
    assert actual == expected


@patch('tribler.core.utilities.exit_codes.check_win_errors', False)
@patch('os.strerror', MagicMock(side_effect=ValueError))
def test_format_error_message_windows_error_not_on_windows():
    actual = CoreManager.format_error_message(exit_code=-1073741819, exit_status=1)
    expected = '''The Tribler core has unexpectedly finished with exit code -1073741819 (0xc0000005) and status: 1.

Error message: Unknown error'''
    assert actual == expected


def test_error_code_to_hex_negative():
    actual = CoreManager.error_code_to_hex(-1073741819)
    expected = '0xc0000005'

    assert actual == expected


def test_error_code_to_hex_positive():
    actual = CoreManager.error_code_to_hex(2)
    expected = '0x2'

    assert actual == expected


def test_on_core_started(core_manager):
    assert not core_manager.core_restart_logs
    core_manager.on_core_started()
    assert core_manager.core_restart_logs


def test_on_core_finished_during_shutdown(core_manager):
    core_manager.shutting_down = True
    core_manager.log_core_finished = MagicMock()

    # Case 1: Shouldn't quit app on core finished
    core_manager.should_quit_app_on_core_finished = False
    core_manager.on_core_finished(exit_code=0, exit_status='OK')

    assert not core_manager.app_manager.quit_application.called
    assert core_manager.log_core_finished.called

    # Case 2: should quit app on core finished
    core_manager.should_quit_app_on_core_finished = True
    core_manager.log_core_finished.reset_mock()
    core_manager.on_core_finished(exit_code=0, exit_status='OK')

    assert core_manager.app_manager.quit_application.called
    assert core_manager.log_core_finished.called


def test_on_core_finished_during_core_restart(core_manager):
    core_manager.wait_for_finished_to_restart_core = True
    core_manager.start_tribler_core = MagicMock()
    core_manager.log_core_finished = MagicMock()

    core_manager.on_core_finished(exit_code=0, exit_status='OK')

    assert core_manager.log_core_finished.called
    assert not core_manager.is_restarting
    assert core_manager.start_tribler_core.called


def test_update_last_core_process_log_on_core_finished(core_manager):
    with pytest.raises(CoreCrashedError):
        core_manager.on_core_finished(exit_code=0, exit_status='OK')
        last_core_restart_log = core_manager.core_restart_logs[-1]
        assert last_core_restart_log.exit_code == 0
        assert last_core_restart_log.exit_status == 'OK'


def test_restart_core(core_manager):
    core_manager.restart_core()

    assert core_manager.is_restarting
    assert not core_manager.should_quit_app_on_core_finished
    assert not core_manager.shutting_down


def test_restart_core_on_core_finished(core_manager):
    core_manager.core_finished = True
    core_manager.start_tribler_core = MagicMock()

    core_manager.restart_core()

    assert core_manager.start_tribler_core.called


def test_restart_core_on_core_connected(core_manager):
    core_manager.core_finished = False
    core_manager.core_connected = True
    core_manager.send_shutdown_request = MagicMock()

    core_manager.restart_core()

    assert core_manager.send_shutdown_request.called
    assert not core_manager.events_manager.shutting_down


def test_restart_core_on_core_not_connected(core_manager):
    core_manager.core_finished = False
    core_manager.core_connected = False
    core_manager.kill_core_process = MagicMock()

    core_manager.restart_core()

    assert core_manager.kill_core_process.called
