from __future__ import annotations

import time
from asyncio import Handle

from tribler.core.utilities.slow_coro_detection import logger
from tribler.core.utilities.slow_coro_detection.utils import format_info
from tribler.core.utilities.slow_coro_detection.watching_thread import SLOW_CORO_DURATION_THRESHOLD, current, lock

# pylint: disable=protected-access

_original_handle_run = Handle._run


def patch_asyncio():
    """
    Patches the asyncio internal methods to be able to track the current coroutine executed by the loop.
    You also need to call `start_watching_thread()` to run a separate thread that detects and reports slow coroutines.
    """
    with lock:
        if getattr(Handle._run, 'patched', False):
            return  # the _run method is already patched

        Handle._run = patched_handle_run
        Handle._run.patched = True


def patched_handle_run(self: Handle):
    """
    Remembers the current asyncio handle object and its starting time globally, so it becomes possible
    to access it from the separate thread and detect slow coroutines.
    """
    start_time = time.time()
    with lock:
        current.handle, current.start_time = self, start_time
    try:
        _original_handle_run(self)
    finally:
        with lock:
            current.handle = current.start_time = None

        duration = time.time() - start_time
        if duration > SLOW_CORO_DURATION_THRESHOLD:
            # The coroutine step is finished successfully (without freezing), but the execution time was too long
            _report_long_duration(self, duration)

        self = None  # Needed to break cycles when an exception occurs (copied from the original Handle._run method)


def _report_long_duration(handle: Handle, duration: float):
    info_str = format_info(handle)
    logger.warning(f'Slow coroutine step execution (duration={duration:.3f} seconds): {info_str}')
