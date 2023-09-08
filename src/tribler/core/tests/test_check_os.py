from logging import Logger
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from tribler.core.check_os import enable_fault_handler, error_and_exit, set_process_priority
from tribler.core.utilities.patch_import import patch_import


# pylint: disable=import-outside-toplevel
# fmt: off

@patch('sys.exit')
@patch('tribler.core.check_os.show_system_popup')
def test_error_and_exit(mocked_show_system_popup, mocked_sys_exit):
    error_and_exit('title', 'text')
    mocked_show_system_popup.assert_called_once_with('title', 'text')
    mocked_sys_exit.assert_called_once_with(1)


@patch_import(['faulthandler'], strict=True, enable=MagicMock())
@patch('tribler.core.check_os.open', new=MagicMock())
def test_enable_fault_handler():
    import faulthandler
    enable_fault_handler(log_dir=MagicMock())
    faulthandler.enable.assert_called_once()


@patch_import(['faulthandler'], strict=True, always_raise_exception_on_import=True)
@patch.object(Logger, 'error')
@patch('tribler.core.check_os.open', new=MagicMock())
def test_enable_fault_handler_import_error(mocked_log_error: MagicMock):
    enable_fault_handler(log_dir=MagicMock())
    mocked_log_error.assert_called_once()


@patch_import(['faulthandler'], strict=True, enable=MagicMock())
@patch('tribler.core.check_os.open', new=MagicMock())
def test_enable_fault_handler_log_dir_not_exists():
    log_dir = MagicMock(exists=MagicMock(return_value=False),
                        mkdir=MagicMock())

    enable_fault_handler(log_dir=log_dir)
    log_dir.mkdir.assert_called_once()


@patch.object(psutil.Process, 'nice')
def test_set_process_priority_supported_platform(mocked_nice: Mock):
    """ Test that the process priority is set on supported platforms."""
    set_process_priority()
    assert mocked_nice.called


@patch('sys.platform', 'freebsd7')
@patch.object(psutil.Process, 'nice')
def test_set_process_priority_unsupported_platform(mocked_nice: Mock):
    """ Test that the process priority is not set on unsupported platforms."""
    set_process_priority()
    assert not mocked_nice.called


def test_set_process_exception():
    """ Test that the set_process_priority does not re-raise an exception derived from `psutil.Error`
    but re-raise all other exceptions"""

    # psutil.Error
    with patch.object(psutil.Process, 'nice', new=Mock(side_effect=psutil.AccessDenied)):
        set_process_priority()

    # any other error
    with patch.object(psutil.Process, 'nice', new=Mock(side_effect=FileNotFoundError)):
        with pytest.raises(FileNotFoundError):
            set_process_priority()
