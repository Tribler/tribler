import os
from multiprocessing import Process
from pathlib import Path
from time import sleep

import pytest

from tribler_common.process_checker import LOCK_FILE_NAME, ProcessChecker


@pytest.fixture
def process_checker(tmpdir):
    return ProcessChecker(state_directory=Path(tmpdir))


def process_dummy_function():
    while True:
        sleep(0.01)


@pytest.fixture
def background_process():
    process = Process(target=process_dummy_function)
    process.start()
    yield process
    process.terminate()


def create_lock_file_with_pid(tmpdir, pid):
    with open(tmpdir / LOCK_FILE_NAME, 'w') as lock_file:
        lock_file.write(str(pid))


def test_create_lock_file(tmpdir, process_checker):
    """
    Testing if lock file is created
    """
    process_checker.create_lock_file()
    assert (tmpdir / LOCK_FILE_NAME).exists()


def test_remove_lock_file(tmpdir, process_checker):
    """
    Testing if lock file is removed on calling remove_lock_file()
    """
    process_checker.create_lock_file()
    process_checker.remove_lock_file()
    assert not (tmpdir / LOCK_FILE_NAME).exists()


def test_no_lock_file(tmpdir, process_checker):
    """
    Testing whether the process checker returns false when there is no lock file
    """
    # Process checker does not create a lock file itself now, Core manager will call to create it.
    assert not (tmpdir / LOCK_FILE_NAME).exists()
    assert not process_checker.already_running


def test_invalid_pid_in_lock_file(tmpdir):
    """
    Testing pid should be -1 if the lock file is invalid
    """
    with open(tmpdir / LOCK_FILE_NAME, 'wb') as lock_file:
        lock_file.write(b"Hello world")

    process_checker = ProcessChecker(state_directory=Path(tmpdir))
    assert process_checker.get_pid_from_lock_file() == -1


def test_own_pid_in_lock_file(tmpdir):
    """
    Testing whether the process checker returns True when it finds its own pid in the lock file
    """
    create_lock_file_with_pid(tmpdir, os.getpid())
    process_checker = ProcessChecker(state_directory=Path(tmpdir))
    assert process_checker.already_running


def test_other_instance_running(tmpdir, background_process):
    """Testing whether the process checker returns true when another process is running."""
    create_lock_file_with_pid(tmpdir, background_process.pid)
    process_checker = ProcessChecker(state_directory=Path(tmpdir))
    assert process_checker.is_pid_running(background_process.pid)
    assert process_checker.already_running


def test_dead_pid_in_lock_file(tmpdir):
    """Testing whether the process checker returns false when there is a dead pid in the lock file."""
    dead_pid = 134824733
    create_lock_file_with_pid(tmpdir, dead_pid)
    process_checker = ProcessChecker(state_directory=Path(tmpdir))
    assert not process_checker.is_pid_running(dead_pid)
    assert not process_checker.already_running
