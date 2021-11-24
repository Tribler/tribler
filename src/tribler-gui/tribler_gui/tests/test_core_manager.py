from unittest.mock import MagicMock, patch

import pytest

from tribler_gui.core_manager import CoreCrashedError, CoreManager

pytestmark = pytest.mark.asyncio


# fmt: off

@patch.object(CoreManager, 'on_finished')
@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
async def test_on_core_finished_call_on_finished(mocked_on_finished: MagicMock):
    # test that in case of `shutting_down` and `should_stop_on_shutdown` flags have been set to True
    # then `on_finished` function will be called and Exception will not be raised
    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    core_manager.shutting_down = True
    core_manager.should_stop_on_shutdown = True

    core_manager.on_core_finished(exit_code=1, exit_status='exit status')
    mocked_on_finished.assert_called_once()


@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
async def test_on_core_finished_raises_error():
    # test that in case of flag `shutting_down` has been set to True and
    # exit_code is not equal to 0, then CoreRuntimeError should be raised
    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())

    with pytest.raises(CoreCrashedError):
        core_manager.on_core_finished(exit_code=1, exit_status='exit status')


@patch('tribler_gui.core_manager.print')
@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
async def test_on_core_stdout_read_ready(mocked_print: MagicMock):
    # test that method `on_core_stdout_read_ready` converts byte output to a string and prints it
    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    core_manager.core_process = MagicMock(readAllStandardOutput=MagicMock(return_value=b'binary string'))
    core_manager.on_core_stdout_read_ready()
    mocked_print.assert_called_with('binary string')


@patch('tribler_gui.core_manager.print')
@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
@patch('sys.stderr')
async def test_on_core_stderr_read_ready(mocked_stderr, mocked_print: MagicMock):
    # test that method `on_core_stdout_read_ready` converts byte output to a string and prints it
    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    core_manager.core_process = MagicMock(readAllStandardError=MagicMock(return_value=b'binary string'))
    core_manager.on_core_stderr_read_ready()
    mocked_print.assert_called_with('binary string', file=mocked_stderr)


@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
@patch('builtins.print', MagicMock(side_effect=OSError()))
def test_on_core_stdout_stderr_read_ready_os_error():
    # test that OSError on writing to stdout is suppressed during shutting down

    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    core_manager.core_process = MagicMock(read_all=MagicMock(return_value=''))

    with pytest.raises(OSError):
        core_manager.on_core_stdout_read_ready()

    with pytest.raises(OSError):
        core_manager.on_core_stderr_read_ready()

    core_manager.shutting_down = True
    # no exception during shutting down
    core_manager.on_core_stdout_read_ready()
    core_manager.on_core_stderr_read_ready()
