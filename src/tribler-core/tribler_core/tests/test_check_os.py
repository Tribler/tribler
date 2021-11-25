from logging import Logger
from unittest.mock import MagicMock, patch

import psutil

import pytest

from tribler_common.patch_import import patch_import

from tribler_core.check_os import enable_fault_handler, error_and_exit, should_kill_other_tribler_instances

# pylint: disable=import-outside-toplevel
# fmt: off

pytestmark = pytest.mark.asyncio


@patch('sys.exit')
@patch('tribler_core.check_os.show_system_popup')
async def test_error_and_exit(mocked_show_system_popup, mocked_sys_exit):
    error_and_exit('title', 'text')
    mocked_show_system_popup.assert_called_once_with('title', 'text')
    mocked_sys_exit.assert_called_once_with(1)


@patch_import(['faulthandler'], strict=True, enable=MagicMock())
@patch('tribler_core.check_os.open', new=MagicMock())
async def test_enable_fault_handler():
    import faulthandler
    enable_fault_handler(log_dir=MagicMock())
    faulthandler.enable.assert_called_once()


@patch_import(['faulthandler'], strict=True, always_raise_exception_on_import=True)
@patch.object(Logger, 'error')
@patch('tribler_core.check_os.open', new=MagicMock())
async def test_enable_fault_handler_import_error(mocked_log_error: MagicMock):
    enable_fault_handler(log_dir=MagicMock())
    mocked_log_error.assert_called_once()


@patch_import(['faulthandler'], strict=True, enable=MagicMock())
@patch('tribler_core.check_os.open', new=MagicMock())
async def test_enable_fault_handler_log_dir_not_exists():
    log_dir = MagicMock(exists=MagicMock(return_value=False),
                        mkdir=MagicMock())

    enable_fault_handler(log_dir=log_dir)
    log_dir.mkdir.assert_called_once()


@patch('tribler_core.check_os.logger.info')
@patch('sys.argv', [])
@patch('tribler_core.check_os.get_existing_tribler_pid', MagicMock(return_value=100))
@patch('os.getpid', MagicMock(return_value=200))
@patch('psutil.Process', MagicMock(return_value=MagicMock(status=MagicMock(side_effect=psutil.NoSuchProcess(100)))))
def test_should_kill_other_tribler_instances_process_not_found(
    mocked_logger_info: MagicMock
):
    root_state_dir = MagicMock()
    should_kill_other_tribler_instances(root_state_dir)
    mocked_logger_info.assert_called_with('Old process not found')


@patch('tribler_core.check_os.logger.info')
@patch('sys.argv', [])
@patch('tribler_core.check_os.get_existing_tribler_pid', MagicMock(return_value=100))
@patch('os.getpid', MagicMock(return_value=200))
@patch('psutil.Process', MagicMock(return_value=MagicMock(status=MagicMock(return_value=psutil.STATUS_ZOMBIE))))
@patch('tribler_core.check_os.kill_tribler_process')
@patch('tribler_core.check_os.restart_tribler_properly')
def test_should_kill_other_tribler_instances_zombie(
    mocked_restart_tribler_properly: MagicMock,
    mocked_kill_tribler_process: MagicMock,
    mocked_logger_info: MagicMock,
):
    root_state_dir = MagicMock()
    should_kill_other_tribler_instances(root_state_dir)
    mocked_logger_info.assert_called()
    mocked_kill_tribler_process.assert_called_once()
    mocked_restart_tribler_properly.assert_called_once()
