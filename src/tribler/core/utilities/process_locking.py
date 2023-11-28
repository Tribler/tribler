from __future__ import annotations

from typing import Optional

from filelock import FileLock, Timeout


GUI_LOCK_FILENAME = 'tribler-gui.lock'
CORE_LOCK_FILENAME = 'tribler-core.lock'


def try_acquire_file_lock(lock_file_name) -> Optional[FileLock]:
    lock = FileLock(lock_file_name)
    try:
        lock.acquire(blocking=False)
    except Timeout:
        return None
    return lock
