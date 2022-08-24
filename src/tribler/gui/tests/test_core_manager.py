import errno
import sys
from unittest.mock import MagicMock, patch

import pytest

from tribler.gui.core_manager import CoreCrashedError, CoreManager


@pytest.fixture(name='core_manager')
def fixture_core_manager():
    core_manager = CoreManager(root_state_dir=MagicMock(), api_port=MagicMock(), api_key=MagicMock(),
                               app_manager=MagicMock(),
                               events_manager=MagicMock())
    core_manager.core_process = MagicMock(readAllStandardOutput=MagicMock(return_value=b'core stdout'),
                                          readAllStandardError=MagicMock(return_value=b'core stderr'))
    return core_manager


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


@patch('builtins.print', MagicMock(side_effect=OSError()))
def test_on_core_read_ready_os_error_suppressed(core_manager):
    # OSError exceptions when writing to stdout and stderr are suppressed
    core_manager.app_manager.quitting_app = False
    core_manager.on_core_stdout_read_ready()
    core_manager.on_core_stderr_read_ready()
    assert print.call_count == 2

    # if app is quitting, core_manager does not write to stdout/stderr at all, and so the call counter does not grow
    core_manager.app_manager.quitting_app = True
    core_manager.on_core_stdout_read_ready()
    core_manager.on_core_stderr_read_ready()
    assert print.call_count == 2


def test_decode_raw_core_output(core_manager):
    assert core_manager.decode_raw_core_output(b'test') == 'test'
    assert core_manager.decode_raw_core_output('test привет'.encode('utf-8')) == 'test привет'
    assert core_manager.decode_raw_core_output('test привет'.encode('cp1251')) == r'test \xef\xf0\xe8\xe2\xe5\xf2'


def test_format_error_message():
    actual = CoreManager.format_error_message(exit_code=errno.ENOENT, exit_status=1, last_core_output='last\noutput')
    expected = '''The Tribler core has unexpectedly finished with exit code 2 and status: 1.

Error message: No such file or directory

Last core output:
> last
> output'''

    assert actual == expected
