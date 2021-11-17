from logging import Logger
from unittest.mock import MagicMock, patch

import pytest

from tribler_common.patch_import import patch_import

from tribler_core.check_os import enable_fault_handler, error_and_exit

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
