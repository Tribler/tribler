from multiprocessing import Process
from time import sleep
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest
from PyQt5.QtWidgets import QMessageBox

from tribler.core.utilities.patch_import import patch_import
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.process_checker import ProcessChecker, single_tribler_instance

TRIBLER_CMD_LINE = [
    ['usr/bin/python', 'run_tribler.py'],
    [r'c:\Program Files\Tribler\Tribler.exe'],
    [r'c:\Program Files\Tribler\Tribler.exe', 'some.torrent'],
    ['Tribler.sh'],
    ['Contents/MacOS/tribler'],
]

NOT_TRIBLER_CMD_LINE = [
    None,
    ['usr/bin/python'],
    [r'c:\Program Files\Tribler\any.exe'],
    [r'tribler\any\path'],
]


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
def checker(tmp_path):
    return ProcessChecker(directory=Path(tmp_path))


def idle():
    sleep(1)


@pytest.fixture
def process():
    process = Process(target=idle)
    process.start()
    yield psutil.Process(process.pid)
    process.kill()


def test_get_pid_lock_file(checker: ProcessChecker):
    # Test that previously saved PID can be read.
    checker.lock_file.write_text('42')
    assert checker._get_pid_from_lock() == 42


def test_get_wrong_pid_lock_file(checker: ProcessChecker):
    # Test that in the case of inconsistent PID None will be returned.
    checker.lock_file.write_text('string')
    assert checker._get_pid_from_lock() is None


@patch.object(Path, 'read_text', Mock(side_effect=PermissionError))
def test_permission_denied(checker: ProcessChecker):
    # Test that in the case of any Exception, None will be returned.
    checker.lock_file.write_text('42')

    assert checker._get_pid_from_lock() is None


def test_missed_lock_file(checker: ProcessChecker):
    # Test that in the case of a missed lock file, None will be returned.
    assert checker._get_pid_from_lock() is None


@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': None}))
def test_is_old_tribler_process_cmdline_none(checker: ProcessChecker, process: psutil.Process):
    # Test that in the case of a missed `cmdline`, False will be returned.
    assert not checker._is_old_tribler_process_running(process)


@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'some\path\tribler'}))
def test_is_old_tribler_process(checker: ProcessChecker, process: psutil.Process):
    # Test that in the case keyword 'tribler' is somewhere in `cmdline', True will be returned.
    assert checker._is_old_tribler_process_running(process)


@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'some\path'}))
def test_is_not_old_tribler_process(checker: ProcessChecker, process: psutil.Process):
    # Test that in the case keyword 'tribler' is not somewhere in `cmdline', False will be returned.
    assert not checker._is_old_tribler_process_running(process)


def test_create_lock(checker: ProcessChecker):
    # Test that the lock file can be created and read.
    assert not checker._get_pid_from_lock()

    checker.create_lock()

    assert isinstance(checker._get_pid_from_lock(), int)


def test_create_lock_sub_folder(tmp_path):
    # Test that the lock file can be created in a folder that does not exist.
    checker = ProcessChecker(directory=tmp_path / 'sub folder')
    checker.create_lock()

    assert checker._get_pid_from_lock()


@patch.object(Path, 'write_text', Mock(side_effect=PermissionError))
def test_create_lock_exception(checker: ProcessChecker):
    # Test that the lock file can not be created in the case of any Exception.
    checker.create_lock()

    assert not checker._get_pid_from_lock()


def test_remove_lock(checker: ProcessChecker):
    # Test that the lock file can be removed.
    checker.create_lock()
    assert checker._get_pid_from_lock()

    checker.remove_lock()
    assert not checker._get_pid_from_lock()


@patch.object(Path, 'unlink', Mock(side_effect=PermissionError))
def test_remove_lock_with_errors(checker: ProcessChecker):
    # Test that the lock file can not be removed in the case of any exception.
    checker.create_lock()
    checker.remove_lock()

    assert checker._get_pid_from_lock()


@patch.object(ProcessChecker, 'check_and_restart_if_necessary', Mock())
@patch.object(ProcessChecker, 'create_lock', Mock())
@patch.object(ProcessChecker, 'remove_lock', Mock())
def test_contextmanager(tmp_path):
    # Test that all necessary methods have been called during the context manager using.
    with single_tribler_instance(tmp_path) as checker:
        assert checker.check_and_restart_if_necessary.called
        assert checker.create_lock.called
        assert not checker.remove_lock.called

    assert checker.remove_lock.called


@patch.object(ProcessChecker, '_close_process', Mock())
@patch.object(ProcessChecker, '_restart_tribler', Mock())
@patch.object(ProcessChecker, '_ask_to_restart', Mock())
@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'tribler'}))
def test_check(checker: ProcessChecker, process: psutil.Process):
    # Ensure that `_restart_tribler` and `_ask_to_restart` methods have been called when
    # tribler process with a proper PID has been checked.
    # Here process is a fake process.
    assert not checker.check_and_restart_if_necessary()
    assert not checker._restart_tribler.called
    assert not checker._ask_to_restart.called
    assert not checker._close_process.called

    checker.create_lock(process.pid)

    assert checker.check_and_restart_if_necessary()
    assert checker._ask_to_restart.called
    assert not checker._restart_tribler.called
    assert not checker._close_process.called


@patch.object(ProcessChecker, '_close_process', Mock())
@patch.object(ProcessChecker, '_restart_tribler', Mock())
@patch.object(ProcessChecker, '_ask_to_restart', Mock())
@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'tribler'}))
@patch.object(psutil.Process, 'status', Mock(return_value=psutil.STATUS_ZOMBIE))
def test_check_zombie(checker: ProcessChecker, process: psutil.Process):
    # Ensure that the `_restart_tribler` method has been called when
    # tribler process with a proper PID has been checked.
    # Here process is a fake process.
    assert not checker.check_and_restart_if_necessary()
    assert not checker._restart_tribler.called
    assert not checker._ask_to_restart.called
    assert not checker._close_process.called

    checker.create_lock(process.pid)

    assert checker.check_and_restart_if_necessary()
    assert not checker._ask_to_restart.called
    assert checker._restart_tribler.called
    assert checker._close_process.called


@patch.object(psutil.Process, 'status', Mock(side_effect=psutil.Error))
def test_check_psutil_error(checker: ProcessChecker):
    # Ensure that the `check` method don`t raise an exception in the case `psutil.Process.status()`
    # raises `psutil.Error` exception.
    assert not checker.check_and_restart_if_necessary()


@pytest.mark.parametrize('cmd_line', TRIBLER_CMD_LINE)
def test_is_tribler_cmd(cmd_line, checker: ProcessChecker):
    assert checker._is_tribler_cmd(cmd_line)


@pytest.mark.parametrize('cmd_line', NOT_TRIBLER_CMD_LINE)
def test_not_is_tribler_cmd(cmd_line, checker: ProcessChecker):
    assert not checker._is_tribler_cmd(cmd_line)


@patch.object(ProcessChecker, '_restart_tribler', Mock())
@patch.object(ProcessChecker, '_close_process', Mock())
def test_ask_to_restart_yes(checker: ProcessChecker, process: psutil.Process):
    # Ensure that when a user choose "Yes" in the message box from the `_ask_to_restart` method,
    # `_restart_tribler` is called.
    mocked_QApplication = Mock()
    mocked_QMessageBox = MagicMock(Yes=QMessageBox.Yes,
                                   return_value=MagicMock(exec_=Mock(return_value=QMessageBox.Yes)))
    with patch_import('PyQt5.QtWidgets', strict=True, QApplication=mocked_QApplication, QMessageBox=mocked_QMessageBox):
        checker._ask_to_restart(process)

    assert mocked_QMessageBox.called
    assert mocked_QApplication.called
    assert checker._restart_tribler.called
    assert checker._close_process.called


@patch.object(ProcessChecker, '_restart_tribler', Mock())
@patch.object(ProcessChecker, '_close_process', Mock())
def test_ask_to_restart_no(checker: ProcessChecker, process: psutil.Process):
    # Ensure that when a user choose "No" in the message box from the `_ask_to_restart` method,
    # `_close_process` is called.
    mocked_QApplication = Mock()
    mocked_QMessageBox = MagicMock(No=QMessageBox.No,
                                   return_value=MagicMock(exec_=Mock(return_value=QMessageBox.No)))
    with patch_import('PyQt5.QtWidgets', strict=True, QApplication=mocked_QApplication, QMessageBox=mocked_QMessageBox):
        checker._ask_to_restart(process)

    assert mocked_QMessageBox.called
    assert mocked_QApplication.called
    assert checker._close_process.called
    assert not checker._restart_tribler.called


@patch.object(ProcessChecker, '_restart_tribler', Mock())
@patch.object(ProcessChecker, '_close_process', Mock())
def test_ask_to_restart_error(checker: ProcessChecker, process: psutil.Process):
    # Ensure that in the case of an error in `_ask_to_restart` method,
    # `_close_process` is called.
    checker._restart_tribler = MagicMock()
    checker._close_process = Mock()
    with patch_import('PyQt5.QtWidgets', always_raise_exception_on_import=True):
        checker._ask_to_restart(process)

    assert not checker._restart_tribler.called
    assert checker._close_process.called


@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'tribler'}))
@patch('os.kill')
def test_close_process(mocked_kill: Mock, checker: ProcessChecker, process: psutil.Process):
    checker._close_process(process)
    assert mocked_kill.called


@patch.object(psutil.Process, 'as_dict', Mock(return_value={'cmdline': r'tribler'}))
@patch('os.kill', Mock(side_effect=OSError))
@patch('os.close', Mock(side_effect=OSError))
def test_close_process_errors(checker: ProcessChecker, process: psutil.Process):
    # Ensure that in the case `os.kill` or `os.close` raises an exception, the `_close_process`
    # will never throw it further.
    checker._close_process(process)


@patch('os.execl')
def test_restart_tribler(mocked_execl: Mock, checker: ProcessChecker):
    checker._restart_tribler()
    assert mocked_execl.called
