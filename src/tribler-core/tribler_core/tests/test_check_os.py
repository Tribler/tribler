from unittest.mock import Mock, patch

import psutil

import pytest

from tribler_core.check_os import error_and_exit, should_kill_other_tribler_instances

pytestmark = pytest.mark.asyncio


# fmt: off
@patch('sys.exit')
@patch('tribler_core.check_os.show_system_popup')
async def test_error_and_exit(mocked_show_system_popup, mocked_sys_exit):
    error_and_exit('title', 'text')
    mocked_show_system_popup.assert_called_once_with('title', 'text')
    mocked_sys_exit.assert_called_once_with(1)


@patch('tribler_core.check_os.logger.info')
@patch('sys.argv', [])
@patch('tribler_core.check_os.get_existing_tribler_pid', Mock(return_value=100))
@patch('os.getpid', Mock(return_value=200))
@patch('psutil.Process', Mock(return_value=Mock(status=Mock(side_effect=psutil.NoSuchProcess(100)))))
def test_should_kill_other_tribler_instances_process_not_found(
    mocked_logger_info: Mock
):
    root_state_dir = Mock()
    should_kill_other_tribler_instances(root_state_dir)
    mocked_logger_info.assert_called_with('Old process not found')


@patch('tribler_core.check_os.logger.info')
@patch('sys.argv', [])
@patch('tribler_core.check_os.get_existing_tribler_pid', Mock(return_value=100))
@patch('os.getpid', Mock(return_value=200))
@patch('psutil.Process', Mock(return_value=Mock(status=Mock(return_value=psutil.STATUS_ZOMBIE))))
@patch('tribler_core.check_os.kill_tribler_process')
@patch('tribler_core.check_os.restart_tribler_properly')
def test_should_kill_other_tribler_instances_zombie(
    mocked_restart_tribler_properly: Mock,
    mocked_kill_tribler_process: Mock,
    mocked_logger_info: Mock,
):
    root_state_dir = Mock()
    should_kill_other_tribler_instances(root_state_dir)
    mocked_logger_info.assert_called()
    mocked_kill_tribler_process.assert_called_once()
    mocked_restart_tribler_properly.assert_called_once()
