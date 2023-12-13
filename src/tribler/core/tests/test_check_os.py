from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from tribler.core.check_os import check_free_space, enable_fault_handler, error_and_exit, set_process_priority
from tribler.core.utilities.patch_import import patch_import
from tribler.core.utilities.path_util import Path

DISK_USAGE = 'tribler.core.check_os.psutil.disk_usage'


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
    """ Test that the enable_fault_handler calls faulthandler.enable."""
    import faulthandler
    assert enable_fault_handler(log_dir=MagicMock())
    faulthandler.enable.assert_called_once()


@patch_import(['faulthandler'], strict=True, always_raise_exception_on_import=True)
@patch('tribler.core.check_os.open', new=MagicMock())
def test_enable_fault_handler_import_error():
    """ Test that the enable_fault_handler does not re-raise an exception derived from `ImportError`"""
    assert not enable_fault_handler(log_dir=MagicMock())


@patch('tribler.core.check_os.open', new=MagicMock(side_effect=PermissionError))
def test_enable_fault_handler_os_error():
    """ Test that the enable_fault_handler does not re-raise an exception derived from `OSError`"""
    assert not enable_fault_handler(log_dir=MagicMock())


@patch_import(['faulthandler'], strict=True, enable=MagicMock())
@patch('tribler.core.check_os.open', new=MagicMock())
def test_enable_fault_handler_log_dir_not_exists():
    """ Test that the enable_fault_handler creates the log directory if it does not exist."""
    log_dir = MagicMock(exists=MagicMock(return_value=False),
                        mkdir=MagicMock())

    assert enable_fault_handler(log_dir=log_dir)
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


def test_check_free_space_sufficient():
    # Test to ensure the function works correctly when there's sufficient disk space.
    with patch(DISK_USAGE) as mock_usage:
        mock_usage.return_value = MagicMock(free=1024 * 1024 * 200)  # Simulating 200MB of free space
        check_free_space(Path("/path/to/dir"))


def test_check_free_space_insufficient():
    # Test to ensure the function raises an exception when there's insufficient disk space.
    with patch(DISK_USAGE) as mock_usage, pytest.raises(SystemExit):
        mock_usage.return_value = MagicMock(free=1024 * 1024 * 50)  # Simulating 50MB of free space
        check_free_space(Path("/path/to/dir"))


def test_check_free_space_import_error():
    # Test to check the behavior when there's an ImportError.
    with patch(DISK_USAGE, side_effect=ImportError("mock import error")), pytest.raises(SystemExit):
        check_free_space(Path("/path/to/dir"))


def test_check_free_space_os_error():
    # Test to check the behavior when there's an OSError.
    with patch(DISK_USAGE, side_effect=OSError("mock os error")):
        check_free_space(Path("/path/to/dir"))
