from unittest.mock import patch

from filelock import Timeout

from tribler.core.utilities.process_locking import try_acquire_file_lock


def test_try_acquire_file_lock(tmp_path):
    lockfile_path = tmp_path / 'lockfile.lock'
    lock = try_acquire_file_lock(lockfile_path)
    assert lock.is_locked
    lock.release()
    assert not lock.is_locked


@patch('filelock.FileLock.acquire', side_effect=[Timeout('lockfile-name')])
def test_try_acquire_file_lock_blocked(acquire, tmp_path):  # pylint: disable=unused-argument
    lockfile_path = tmp_path / 'lockfile.lock'
    lock = try_acquire_file_lock(lockfile_path)
    assert lock is None
